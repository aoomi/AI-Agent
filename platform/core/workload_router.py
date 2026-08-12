"""Health-aware routing and backpressure for horizontally scaled workers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import RLock
import time
from typing import Iterable


class WorkloadRoutingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WorkerSnapshot:
    worker_id: str
    service_scope: str
    resource_classes: tuple[str, ...]
    capacity: int
    active: int
    queue_depth: int
    available_memory: int
    heartbeat_at: float
    generation: int = 1
    endpoint: str = ""


class WorkloadRouter:
    """Select the least-loaded healthy worker without binding to discovery storage."""

    def __init__(self, *, heartbeat_timeout: float = 30.0, max_queue_depth: int = 32) -> None:
        if heartbeat_timeout <= 0 or max_queue_depth <= 0:
            raise ValueError("heartbeat_timeout and max_queue_depth must be positive")
        self.heartbeat_timeout = heartbeat_timeout
        self.max_queue_depth = max_queue_depth
        self._workers: dict[str, WorkerSnapshot] = {}
        self._lock = RLock()

    def heartbeat(self, worker: WorkerSnapshot) -> WorkerSnapshot:
        if not worker.worker_id.strip() or not worker.service_scope.strip() or not worker.resource_classes:
            raise WorkloadRoutingError("invalid worker identity")
        if worker.capacity <= 0 or worker.active < 0 or worker.active > worker.capacity or worker.queue_depth < 0 or worker.available_memory < 0 or worker.generation < 1:
            raise WorkloadRoutingError("invalid worker capacity")
        with self._lock:
            previous = self._workers.get(worker.worker_id)
            if previous and worker.generation < previous.generation:
                raise WorkloadRoutingError("stale worker generation")
            if previous and worker.generation == previous.generation and worker.heartbeat_at < previous.heartbeat_at:
                return previous
            self._workers[worker.worker_id] = worker
        return worker

    def remove(self, worker_id: str, *, generation: int | None = None) -> bool:
        worker_id = worker_id.strip()
        if not worker_id or generation is not None and (isinstance(generation, bool) or generation < 1):
            raise WorkloadRoutingError("invalid worker removal")
        with self._lock:
            current = self._workers.get(worker_id)
            if not current or generation is not None and current.generation != generation:
                return False
            del self._workers[worker_id]
            return True

    def reap(self, *, now: float | None = None) -> int:
        """Remove heartbeat-expired workers from the in-memory routing view."""
        moment = time.time() if now is None else now
        with self._lock:
            stale = [worker_id for worker_id, worker in self._workers.items() if moment - worker.heartbeat_at > self.heartbeat_timeout]
            for worker_id in stale:
                del self._workers[worker_id]
            return len(stale)

    def route(self, resource_class: str, *, estimated_memory: int = 0, service_scope: str = "", worker_id: str = "", now: float | None = None) -> WorkerSnapshot:
        resource_class, service_scope, worker_id = resource_class.strip(), service_scope.strip(), worker_id.strip()
        if not resource_class or estimated_memory < 0:
            raise WorkloadRoutingError("invalid worker route")
        moment = time.time() if now is None else now
        with self._lock:
            eligible = [
                worker for worker in self._workers.values()
                if resource_class in worker.resource_classes
                and (not service_scope or worker.service_scope == service_scope)
                and (not worker_id or worker.worker_id == worker_id)
                and moment - worker.heartbeat_at <= self.heartbeat_timeout
                and worker.active < worker.capacity
                and worker.queue_depth < self.max_queue_depth
                and worker.available_memory >= estimated_memory
            ]
        if not eligible:
            raise WorkloadRoutingError("no healthy worker capacity; apply backpressure")
        return min(eligible, key=lambda worker:(worker.active / worker.capacity, worker.queue_depth, -worker.available_memory, worker.worker_id))

    def snapshot(self, *, now: float | None = None) -> list[dict[str, object]]:
        moment = time.time() if now is None else now
        with self._lock:
            workers: Iterable[WorkerSnapshot] = tuple(self._workers.values())
        return [{**asdict(worker), "healthy":moment - worker.heartbeat_at <= self.heartbeat_timeout} for worker in sorted(workers, key=lambda item:item.worker_id)]
