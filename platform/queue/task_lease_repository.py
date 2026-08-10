"""Atomic SQLite task ownership leases with fencing generations."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from threading import RLock
import time


class TaskLeaseError(RuntimeError):
    pass


class TaskLeaseRepository:
    def __init__(self, database: Path) -> None:
        self.database = database.resolve(); self.database.parent.mkdir(parents=True, exist_ok=True); self._lock = RLock()
        with self._connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS task_leases (
                job_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, generation INTEGER NOT NULL,
                lease_expires_at REAL NOT NULL, heartbeat_at REAL NOT NULL
            )""")

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database, timeout=30, isolation_level="IMMEDIATE"); connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE"); yield connection; connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            connection.close()

    def acquire(self, job_id: str, owner_id: str, *, ttl: float = 30.0, now: float | None = None) -> dict[str, object]:
        if not job_id.strip() or not owner_id.strip() or ttl <= 0:
            raise TaskLeaseError("invalid lease request")
        moment = time.time() if now is None else now
        with self._lock, self._connection() as connection:
            current = connection.execute("SELECT * FROM task_leases WHERE job_id=?", (job_id,)).fetchone()
            if current and current["owner_id"] != owner_id and current["lease_expires_at"] > moment:
                raise TaskLeaseError("task lease already owned")
            generation = int(current["generation"]) if current and current["owner_id"] == owner_id else int(current["generation"]) + 1 if current else 1
            connection.execute("""INSERT INTO task_leases(job_id,owner_id,generation,lease_expires_at,heartbeat_at) VALUES(?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET owner_id=excluded.owner_id,generation=excluded.generation,
                lease_expires_at=excluded.lease_expires_at,heartbeat_at=excluded.heartbeat_at""", (job_id, owner_id, generation, moment + ttl, moment))
        return {"job_id":job_id, "owner_id":owner_id, "generation":generation, "lease_expires_at":moment + ttl, "heartbeat_at":moment}

    def renew(self, job_id: str, owner_id: str, generation: int, *, ttl: float = 30.0, now: float | None = None) -> bool:
        moment = time.time() if now is None else now
        with self._lock, self._connection() as connection:
            result = connection.execute("""UPDATE task_leases SET lease_expires_at=?,heartbeat_at=?
                WHERE job_id=? AND owner_id=? AND generation=? AND lease_expires_at>?""", (moment + ttl, moment, job_id, owner_id, generation, moment))
            return result.rowcount == 1

    def release(self, job_id: str, owner_id: str, generation: int) -> bool:
        with self._lock, self._connection() as connection:
            result = connection.execute("DELETE FROM task_leases WHERE job_id=? AND owner_id=? AND generation=?", (job_id, owner_id, generation))
            return result.rowcount == 1

    def owns(self, job_id: str, owner_id: str, generation: int, *, now: float | None = None) -> bool:
        moment = time.time() if now is None else now
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT owner_id,generation,lease_expires_at FROM task_leases WHERE job_id=?", (job_id,)).fetchone()
        return bool(row and row["owner_id"] == owner_id and row["generation"] == generation and row["lease_expires_at"] > moment)

    def reap_expired(self, *, now: float | None = None) -> int:
        moment = time.time() if now is None else now
        with self._lock, self._connection() as connection:
            result = connection.execute("DELETE FROM task_leases WHERE lease_expires_at<=?", (moment,))
            return result.rowcount
