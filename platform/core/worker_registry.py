"""SQLite worker discovery provider for same-host multi-process deployments."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import time

from .workload_router import WorkerSnapshot


class WorkerRegistry:
    def __init__(self, database: Path) -> None:
        self.database = database.resolve(); self.database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS workers (worker_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, heartbeat_at REAL NOT NULL, generation INTEGER NOT NULL)")

    def heartbeat(self, worker: WorkerSnapshot) -> WorkerSnapshot:
        payload = json.dumps(asdict(worker), ensure_ascii=False, sort_keys=True)
        with sqlite3.connect(self.database, timeout=30) as connection:
            connection.execute("""INSERT INTO workers VALUES(?,?,?,?) ON CONFLICT(worker_id) DO UPDATE SET
                payload_json=excluded.payload_json,heartbeat_at=excluded.heartbeat_at,generation=excluded.generation
                WHERE excluded.generation>=workers.generation""", (worker.worker_id, payload, worker.heartbeat_at, worker.generation))
        return worker

    def list(self, *, heartbeat_timeout: float = 30, service_scope: str = "", now: float | None = None) -> list[WorkerSnapshot]:
        moment = time.time() if now is None else now
        with sqlite3.connect(self.database, timeout=30) as connection:
            rows = connection.execute("SELECT payload_json FROM workers WHERE heartbeat_at>=?", (moment - heartbeat_timeout,)).fetchall()
        workers = []
        for row in rows:
            payload = json.loads(row[0]); payload["resource_classes"] = tuple(payload.get("resource_classes") or ())
            workers.append(WorkerSnapshot(**payload))
        return [worker for worker in workers if not service_scope or worker.service_scope == service_scope]

    def remove(self, worker_id: str, generation: int) -> bool:
        with sqlite3.connect(self.database, timeout=30) as connection:
            result = connection.execute("DELETE FROM workers WHERE worker_id=? AND generation=?", (worker_id, generation))
            return result.rowcount == 1

    def reap(self, *, heartbeat_timeout: float = 30, now: float | None = None) -> int:
        moment = time.time() if now is None else now
        with sqlite3.connect(self.database, timeout=30) as connection:
            result = connection.execute("DELETE FROM workers WHERE heartbeat_at<?", (moment - heartbeat_timeout,))
            return result.rowcount
