"""SQLite worker discovery provider for same-host multi-process deployments."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import sqlite3
import time

from .workload_router import WorkerSnapshot, WorkloadRoutingError


class WorkerRegistry:
    def __init__(self, database: Path) -> None:
        if not isinstance(database,Path):raise WorkloadRoutingError("worker database must be a Path")
        self.database = database.resolve(); self.database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database, timeout=30, isolation_level=None) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("CREATE TABLE IF NOT EXISTS workers (worker_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, heartbeat_at REAL NOT NULL, generation INTEGER NOT NULL)")
                connection.execute("""CREATE TABLE IF NOT EXISTS worker_reservations (
                    request_id TEXT PRIMARY KEY, worker_id TEXT NOT NULL, worker_generation INTEGER NOT NULL,
                    resource_class TEXT NOT NULL, estimated_memory INTEGER NOT NULL, service_scope TEXT NOT NULL DEFAULT '',
                    owner_scope TEXT NOT NULL DEFAULT '',
                    reserved_at REAL NOT NULL, expires_at REAL NOT NULL
                )""")
                columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(worker_reservations)")}
                if "service_scope" not in columns:
                    connection.execute("ALTER TABLE worker_reservations ADD COLUMN service_scope TEXT NOT NULL DEFAULT ''")
                if "owner_scope" not in columns:
                    connection.execute("ALTER TABLE worker_reservations ADD COLUMN owner_scope TEXT NOT NULL DEFAULT ''")
                connection.execute("CREATE INDEX IF NOT EXISTS worker_reservations_worker ON worker_reservations(worker_id,expires_at)")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def heartbeat(self, worker: WorkerSnapshot) -> WorkerSnapshot:
        if (not isinstance(worker,WorkerSnapshot) or not isinstance(worker.worker_id,str) or not isinstance(worker.service_scope,str)
                or not worker.worker_id.strip() or not worker.service_scope.strip() or not isinstance(worker.resource_classes,tuple)
                or not worker.resource_classes or any(not isinstance(value,str) or not value.strip() for value in worker.resource_classes)):
            raise WorkloadRoutingError("invalid worker identity")
        if not isinstance(worker.endpoint,str):raise WorkloadRoutingError("invalid worker endpoint")
        integer_fields=(worker.capacity,worker.active,worker.queue_depth,worker.available_memory,worker.generation)
        if (any(isinstance(value,bool) or not isinstance(value,int) for value in integer_fields)
                or worker.capacity <= 0 or worker.active < 0 or worker.active > worker.capacity or worker.queue_depth < 0 or worker.available_memory < 0 or worker.generation < 1
                or isinstance(worker.heartbeat_at,bool) or not isinstance(worker.heartbeat_at,(int,float)) or not math.isfinite(worker.heartbeat_at)):
            raise WorkloadRoutingError("invalid worker capacity")
        worker=replace(worker,worker_id=worker.worker_id.strip(),service_scope=worker.service_scope.strip(),resource_classes=tuple(value.strip() for value in worker.resource_classes),endpoint=worker.endpoint.strip())
        payload = json.dumps(asdict(worker), ensure_ascii=False, sort_keys=True)
        with sqlite3.connect(self.database, timeout=30) as connection:
            previous=connection.execute("SELECT payload_json,generation FROM workers WHERE worker_id=?",(worker.worker_id,)).fetchone()
            if previous and worker.generation<int(previous[1]):
                raise WorkloadRoutingError("stale worker generation")
            if previous and worker.generation==int(previous[1]):
                current=self._worker(previous[0])
                if worker.heartbeat_at<=current.heartbeat_at:
                    return current
                if (worker.service_scope,worker.resource_classes,worker.capacity,worker.endpoint)!=(current.service_scope,current.resource_classes,current.capacity,current.endpoint):raise WorkloadRoutingError("worker identity requires a new generation")
            connection.execute("""INSERT INTO workers VALUES(?,?,?,?) ON CONFLICT(worker_id) DO UPDATE SET
                payload_json=excluded.payload_json,heartbeat_at=excluded.heartbeat_at,generation=excluded.generation
                WHERE excluded.generation>workers.generation OR (
                    excluded.generation=workers.generation AND excluded.heartbeat_at>=workers.heartbeat_at
                )""", (worker.worker_id, payload, worker.heartbeat_at, worker.generation))
            connection.execute("""DELETE FROM worker_reservations WHERE worker_id=? AND worker_generation<>(
                SELECT generation FROM workers WHERE worker_id=?
            )""", (worker.worker_id, worker.worker_id))
        return worker

    def list(self, *, heartbeat_timeout: float = 30, service_scope: str = "", now: float | None = None) -> list[WorkerSnapshot]:
        if not isinstance(service_scope,str):raise WorkloadRoutingError("invalid worker service scope")
        service_scope=service_scope.strip()
        if isinstance(heartbeat_timeout,bool) or not isinstance(heartbeat_timeout,(int,float)) or not math.isfinite(heartbeat_timeout) or heartbeat_timeout <= 0: raise WorkloadRoutingError("invalid worker heartbeat timeout")
        moment = time.time() if now is None else now
        if isinstance(moment,bool) or not isinstance(moment,(int,float)) or not math.isfinite(moment): raise WorkloadRoutingError("invalid worker clock")
        with sqlite3.connect(self.database, timeout=30) as connection:
            rows = connection.execute("SELECT payload_json FROM workers WHERE heartbeat_at>=?", (moment - heartbeat_timeout,)).fetchall()
        workers = []
        for row in rows:
            workers.append(self._worker(row[0]))
        return [worker for worker in workers if not service_scope or worker.service_scope == service_scope]

    def remove(self, worker_id: str, generation: int) -> bool:
        if not isinstance(worker_id,str):raise WorkloadRoutingError("invalid worker removal")
        worker_id = worker_id.strip()
        if not worker_id or isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise WorkloadRoutingError("invalid worker removal")
        with sqlite3.connect(self.database, timeout=30) as connection:
            connection.execute("DELETE FROM worker_reservations WHERE worker_id=? AND worker_generation=?", (worker_id, generation))
            result = connection.execute("DELETE FROM workers WHERE worker_id=? AND generation=?", (worker_id, generation))
            return result.rowcount == 1

    def reserve(self, request_id: str, resource_class: str, *, estimated_memory: int = 0,
                service_scope: str = "", heartbeat_timeout: float = 30, reservation_ttl: float = 15,
                owner_scope: str = "",
                now: float | None = None) -> WorkerSnapshot:
        """Atomically reserve one dispatch slot across all registry instances."""
        if any(not isinstance(value,str) for value in (request_id,resource_class,service_scope,owner_scope)):
            raise WorkloadRoutingError("invalid worker reservation")
        request_id, resource_class, service_scope, owner_scope = (value.strip() for value in (request_id,resource_class,service_scope,owner_scope))
        if (not request_id or not resource_class
                or isinstance(estimated_memory,bool) or not isinstance(estimated_memory,int) or estimated_memory < 0
                or isinstance(heartbeat_timeout,bool) or not isinstance(heartbeat_timeout,(int,float)) or not math.isfinite(heartbeat_timeout) or heartbeat_timeout <= 0
                or isinstance(reservation_ttl,bool) or not isinstance(reservation_ttl,(int,float)) or not math.isfinite(reservation_ttl) or reservation_ttl <= 0):
            raise WorkloadRoutingError("invalid worker reservation")
        moment = time.time() if now is None else now
        if isinstance(moment,bool) or not isinstance(moment,(int,float)) or not math.isfinite(moment): raise WorkloadRoutingError("invalid worker clock")
        with sqlite3.connect(self.database, timeout=30, isolation_level=None) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute("DELETE FROM worker_reservations WHERE expires_at<=?", (moment,))
                connection.execute("""DELETE FROM worker_reservations WHERE NOT EXISTS (
                    SELECT 1 FROM workers w WHERE w.worker_id=worker_reservations.worker_id
                    AND w.generation=worker_reservations.worker_generation
                )""")
                existing = connection.execute("""SELECT w.payload_json,r.resource_class,r.estimated_memory,r.service_scope,r.owner_scope
                    FROM worker_reservations r JOIN workers w
                    ON w.worker_id=r.worker_id AND w.generation=r.worker_generation
                    WHERE r.request_id=? AND r.expires_at>? AND w.heartbeat_at>=?""",
                    (request_id, moment, moment - heartbeat_timeout)).fetchone()
                if existing:
                    if (str(existing[1]), int(existing[2]), str(existing[3]), str(existing[4])) != (resource_class, estimated_memory, service_scope, owner_scope):
                        raise WorkloadRoutingError("worker reservation request_id contract conflict")
                    connection.commit(); return self._worker(existing[0])
                rows = connection.execute("SELECT payload_json FROM workers WHERE heartbeat_at>=?", (moment - heartbeat_timeout,)).fetchall()
                reservations = connection.execute("""SELECT r.worker_id,COUNT(*),COALESCE(SUM(r.estimated_memory),0)
                    FROM worker_reservations r JOIN workers w ON w.worker_id=r.worker_id AND w.generation=r.worker_generation
                    WHERE r.expires_at>? GROUP BY r.worker_id""", (moment,)).fetchall()
                occupied = {str(worker_id):(int(count), int(memory)) for worker_id, count, memory in reservations}
                eligible = []
                for row in rows:
                    worker = self._worker(row[0]); reserved_count, reserved_memory = occupied.get(worker.worker_id, (0, 0))
                    effective_active = worker.active + reserved_count
                    if resource_class not in worker.resource_classes or service_scope and worker.service_scope != service_scope:
                        continue
                    if effective_active >= worker.capacity or worker.available_memory - reserved_memory < estimated_memory:
                        continue
                    eligible.append((effective_active / worker.capacity, worker.queue_depth, -worker.available_memory + reserved_memory, worker.worker_id, worker))
                if not eligible:
                    raise WorkloadRoutingError("no healthy worker reservation capacity; apply backpressure")
                worker = min(eligible)[-1]
                connection.execute("""INSERT INTO worker_reservations
                    (request_id,worker_id,worker_generation,resource_class,estimated_memory,service_scope,owner_scope,reserved_at,expires_at)
                    VALUES(?,?,?,?,?,?,?,?,?)""", (
                    request_id, worker.worker_id, worker.generation, resource_class, estimated_memory, service_scope,
                    owner_scope,
                    moment, moment + reservation_ttl,
                ))
                connection.commit(); return worker
            except Exception:
                connection.rollback(); raise

    def release_reservation(self, request_id: str) -> bool:
        if not isinstance(request_id,str):raise WorkloadRoutingError("invalid worker reservation release")
        request_id = request_id.strip()
        if not request_id: raise WorkloadRoutingError("invalid worker reservation release")
        with sqlite3.connect(self.database, timeout=30) as connection:
            result = connection.execute("DELETE FROM worker_reservations WHERE request_id=?", (request_id,))
            return result.rowcount == 1

    def reservation_snapshot(self, *, now: float | None = None) -> list[dict[str, object]]:
        moment = time.time() if now is None else now
        if isinstance(moment,bool) or not isinstance(moment,(int,float)) or not math.isfinite(moment): raise WorkloadRoutingError("invalid worker clock")
        with sqlite3.connect(self.database, timeout=30) as connection:
            rows = connection.execute("""SELECT r.request_id,r.worker_id,r.worker_generation,r.resource_class,
                r.estimated_memory,r.service_scope,r.owner_scope,r.reserved_at,r.expires_at FROM worker_reservations r JOIN workers w
                ON w.worker_id=r.worker_id AND w.generation=r.worker_generation
                WHERE r.expires_at>? ORDER BY r.reserved_at,r.request_id""", (moment,)).fetchall()
        keys = ("request_id", "worker_id", "worker_generation", "resource_class", "estimated_memory", "service_scope", "owner_scope", "reserved_at", "expires_at")
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def reap(self, *, heartbeat_timeout: float = 30, now: float | None = None) -> int:
        if isinstance(heartbeat_timeout,bool) or not isinstance(heartbeat_timeout,(int,float)) or not math.isfinite(heartbeat_timeout) or heartbeat_timeout <= 0: raise WorkloadRoutingError("invalid worker heartbeat timeout")
        moment = time.time() if now is None else now
        if isinstance(moment,bool) or not isinstance(moment,(int,float)) or not math.isfinite(moment): raise WorkloadRoutingError("invalid worker clock")
        with sqlite3.connect(self.database, timeout=30) as connection:
            connection.execute("DELETE FROM worker_reservations WHERE expires_at<=? OR worker_id IN (SELECT worker_id FROM workers WHERE heartbeat_at<?)", (moment, moment - heartbeat_timeout))
            result = connection.execute("DELETE FROM workers WHERE heartbeat_at<?", (moment - heartbeat_timeout,))
            return result.rowcount

    @staticmethod
    def _worker(payload_json: str) -> WorkerSnapshot:
        try:payload = json.loads(payload_json,parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
        except (json.JSONDecodeError,ValueError,TypeError) as error:raise WorkloadRoutingError("worker registry record is invalid") from error
        if not isinstance(payload,dict):raise WorkloadRoutingError("worker registry record is invalid")
        payload["resource_classes"] = tuple(payload.get("resource_classes") or ())
        try:worker=WorkerSnapshot(**payload)
        except (TypeError,ValueError) as error:raise WorkloadRoutingError("worker registry record is invalid") from error
        if (not isinstance(worker.worker_id,str) or not worker.worker_id.strip() or not isinstance(worker.service_scope,str) or not worker.service_scope.strip()
                or not isinstance(worker.endpoint,str) or not isinstance(worker.resource_classes,tuple) or not worker.resource_classes
                or any(not isinstance(value,str) or not value.strip() for value in worker.resource_classes)):
            raise WorkloadRoutingError("worker registry record is invalid")
        integers=(worker.capacity,worker.active,worker.queue_depth,worker.available_memory,worker.generation)
        if (any(isinstance(value,bool) or not isinstance(value,int) for value in integers) or worker.capacity<=0 or worker.active<0
                or worker.active>worker.capacity or worker.queue_depth<0 or worker.available_memory<0 or worker.generation<1
                or isinstance(worker.heartbeat_at,bool) or not isinstance(worker.heartbeat_at,(int,float)) or not math.isfinite(worker.heartbeat_at)):
            raise WorkloadRoutingError("worker registry record is invalid")
        return worker
