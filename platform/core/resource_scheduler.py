"""Fair, priority-aware admission control for heavyweight AI workloads."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from threading import Condition, RLock
import time
from typing import Iterator
from uuid import uuid4


RESOURCE_PRIORITIES = {"control": 0, "text": 10, "audit": 20, "image": 30, "audio": 40, "video": 50, "3d": 60, "upscale": 70}


class ResourceSchedulerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ResourceTicket:
    ticket_id: str
    job_id: str
    resource_class: str
    priority: int
    estimated_memory: int
    queued_at: float
    pool: str = "global"
    tenant_id: str = ""
    user_id: str = ""
    project_id: str = ""


class ResourceScheduler:
    """Priority admission across configurable resource pools.

    The default remains a single serialized pool for backwards compatibility.
    Deployments may isolate accelerator, CPU-media and control traffic so cheap
    work is not blocked behind a long GPU generation while each pool still
    applies its own capacity, priority, timeout and cancellation rules.
    """

    def __init__(
        self,
        execution_lock: RLock | None = None,
        *,
        resource_pools: dict[str, str] | None = None,
        pool_capacities: dict[str, int] | None = None,
        pool_queue_limits: dict[str, int] | None = None,
        tenant_queue_limits: dict[str, int] | None = None,
        project_queue_limits: dict[str, int] | None = None,
        serialized_pools: set[str] | None = None,
    ) -> None:
        self.execution_lock = execution_lock or RLock()
        self.resource_pools = {resource: (resource_pools or {}).get(resource, "global") for resource in RESOURCE_PRIORITIES}
        self.pool_capacities = dict(pool_capacities or {"global": 1})
        for pool in set(self.resource_pools.values()):
            self.pool_capacities.setdefault(pool, 1)
        self.pool_queue_limits = dict(pool_queue_limits or {})
        for pool in set(self.resource_pools.values()):
            self.pool_queue_limits.setdefault(pool, 1024)
        self.tenant_queue_limits = dict(tenant_queue_limits or self.pool_queue_limits)
        self.project_queue_limits = dict(project_queue_limits or self.pool_queue_limits)
        for pool in set(self.resource_pools.values()):
            self.tenant_queue_limits.setdefault(pool, self.pool_queue_limits[pool])
            self.project_queue_limits.setdefault(pool, self.tenant_queue_limits[pool])
        if any(not pool.strip() for pool in self.resource_pools.values()) or any(capacity <= 0 for capacity in self.pool_capacities.values()) or any(limit <= 0 for limits in (self.pool_queue_limits, self.tenant_queue_limits, self.project_queue_limits) for limit in limits.values()):
            raise ValueError("resource pool names and capacities must be valid")
        self.serialized_pools = set(serialized_pools if serialized_pools is not None else {"global"})
        self._condition = Condition(RLock())
        self._queue: list[ResourceTicket] = []
        self._active: dict[str, ResourceTicket] = {}
        self._cancelled: set[str] = set()

    @contextmanager
    def claim(self, resource_class: str, job_id: str, *, estimated_memory: int = 0, timeout: float | None = None,
              tenant_id: str = "", user_id: str = "", project_id: str = "") -> Iterator[ResourceTicket]:
        if resource_class not in RESOURCE_PRIORITIES or not str(job_id).strip() or estimated_memory < 0:
            raise ResourceSchedulerError("invalid resource request")
        pool = self.resource_pools[resource_class]
        scope = tuple(str(value or "").strip() for value in (tenant_id, user_id, project_id))
        if any(scope) and not all(scope):
            raise ResourceSchedulerError("tenant_id, user_id and project_id must be supplied together")
        ticket = ResourceTicket(f"resource-{uuid4().hex}", str(job_id), resource_class, RESOURCE_PRIORITIES[resource_class], estimated_memory, time.time(), pool, *scope)
        deadline = time.monotonic() + timeout if timeout is not None else None
        with self._condition:
            if sum(1 for item in self._queue if item.pool == pool) >= self.pool_queue_limits[pool]:
                raise ResourceSchedulerError(f"resource pool backpressure: {pool}")
            if ticket.tenant_id and sum(1 for item in self._queue if item.pool == pool and item.tenant_id == ticket.tenant_id) >= self.tenant_queue_limits[pool]:
                raise ResourceSchedulerError(f"tenant resource backpressure: {pool}")
            if ticket.project_id and sum(1 for item in self._queue if item.pool == pool and (item.tenant_id, item.user_id, item.project_id) == (ticket.tenant_id, ticket.user_id, ticket.project_id)) >= self.project_queue_limits[pool]:
                raise ResourceSchedulerError(f"project resource backpressure: {pool}")
            self._queue.append(ticket)
            while True:
                if ticket.ticket_id in self._cancelled:
                    self._queue = [item for item in self._queue if item.ticket_id != ticket.ticket_id]
                    self._cancelled.discard(ticket.ticket_id)
                    raise ResourceSchedulerError("resource request cancelled")
                pool_queue = sorted((item for item in self._queue if item.pool == pool), key=lambda item:(item.priority, item.queued_at, item.ticket_id))
                active_count = sum(1 for item in self._active.values() if item.pool == pool)
                available = self.pool_capacities[pool] - active_count
                if available > 0 and ticket in pool_queue[:available]:
                    self._queue.remove(ticket); self._active[ticket.ticket_id] = ticket; break
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    self._queue = [item for item in self._queue if item.ticket_id != ticket.ticket_id]
                    raise ResourceSchedulerError("resource request timed out")
                self._condition.wait(remaining)
        try:
            lock = self.execution_lock if pool in self.serialized_pools else nullcontext()
            with lock:
                yield ticket
        finally:
            with self._condition:
                self._active.pop(ticket.ticket_id, None)
                self._condition.notify_all()

    def cancel_job(self, job_id: str) -> int:
        with self._condition:
            targets = [ticket.ticket_id for ticket in self._queue if ticket.job_id == job_id]
            self._cancelled.update(targets); self._condition.notify_all(); return len(targets)

    def snapshot(self) -> dict[str, object]:
        with self._condition:
            active_items = sorted(self._active.values(), key=lambda item:(item.pool, item.queued_at, item.ticket_id))
            return {
                "active": self._ticket(active_items[0]) if active_items else None,
                "active_items": [self._ticket(ticket) for ticket in active_items],
                "queued": [self._ticket(ticket) for ticket in sorted(self._queue, key=lambda item:(item.priority, item.queued_at, item.ticket_id))],
                "pools": {pool:{"capacity":capacity,"queue_limit":self.pool_queue_limits[pool],"tenant_queue_limit":self.tenant_queue_limits[pool],"project_queue_limit":self.project_queue_limits[pool],"active":sum(1 for item in active_items if item.pool == pool),"queued":sum(1 for item in self._queue if item.pool == pool)} for pool, capacity in sorted(self.pool_capacities.items())},
            }

    @staticmethod
    def _ticket(ticket: ResourceTicket) -> dict[str, object]:
        return {"ticket_id":ticket.ticket_id, "job_id":ticket.job_id, "resource_class":ticket.resource_class, "pool":ticket.pool, "priority":ticket.priority, "estimated_memory":ticket.estimated_memory, "queued_at":ticket.queued_at, "tenant_id":ticket.tenant_id, "user_id":ticket.user_id, "project_id":ticket.project_id}
