"""SQLite-backed authoritative lifecycle store for heterogeneous production jobs."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import sqlite3
from threading import Event, RLock, Thread
import time
from typing import Any, Mapping
from uuid import uuid4
from dataclasses import dataclass


@dataclass(slots=True)
class ProjectionLease:
    acquired: bool
    lost: Event
    repository: "DurableTaskRepository"
    scope_key: str
    owner_id: str

    def __bool__(self) -> bool:
        return self.acquired and not self.lost.is_set()

    def owns(self) -> bool:
        if not self.acquired or self.lost.is_set():
            return False
        try:
            with self.repository._lock, self.repository._connection() as connection:
                row = connection.execute("SELECT owner_id,expires_at FROM task_projection_locks WHERE scope_key=?", (self.scope_key,)).fetchone()
            owned = bool(row and row["owner_id"] == self.owner_id and float(row["expires_at"]) > time.time())
        except sqlite3.Error:
            owned = False
        if not owned:
            self.lost.set()
        return owned


class DurableTaskRepository:
    def __init__(self, database: Path) -> None:
        if not isinstance(database,Path):raise ValueError("durable task database must be a Path")
        self.database = database.resolve(); self.database.parent.mkdir(parents=True, exist_ok=True); self._lock = RLock()
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS durable_tasks (
                    job_id TEXT PRIMARY KEY, task_class TEXT NOT NULL, tenant_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL, stage TEXT NOT NULL, subject_key TEXT NOT NULL, status TEXT NOT NULL,
                    pid INTEGER, process_group INTEGER, heartbeat_at TEXT NOT NULL, started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_durable_tasks_project ON durable_tasks(tenant_id,user_id,project_id,status,updated_at);
                CREATE TABLE IF NOT EXISTS task_projection_outbox (
                    job_id TEXT PRIMARY KEY, task_class TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
                    event_revision INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS task_projection_sequence (event_revision INTEGER PRIMARY KEY AUTOINCREMENT);
                CREATE TABLE IF NOT EXISTS task_projection_locks (
                    scope_key TEXT PRIMARY KEY, owner_id TEXT NOT NULL, expires_at REAL NOT NULL
                );
            """)
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(task_projection_outbox)")}
            if "event_revision" not in columns:
                connection.execute("ALTER TABLE task_projection_outbox ADD COLUMN event_revision INTEGER NOT NULL DEFAULT 0")

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database, timeout=30); connection.row_factory = sqlite3.Row
        try: yield connection; connection.commit()
        except Exception: connection.rollback(); raise
        finally: connection.close()

    def upsert(self, job_id: str, task_class: str, job: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(job_id,str) or not isinstance(task_class,str):raise ValueError("durable task identity must be strings")
        values = self._values(job_id, task_class, job)
        self.upsert_many(task_class, {job_id:job})
        return self.get(job_id, tenant_id=values["tenant_id"], user_id=values["user_id"], project_id=values["project_id"]) or {}

    def upsert_many(self, task_class: str, jobs: Mapping[str, Mapping[str, Any]], *, enqueue_projection: bool = False) -> list[dict[str, Any]]:
        if not isinstance(task_class,str) or not isinstance(jobs, Mapping) or not isinstance(enqueue_projection, bool) or any(not isinstance(job_id,str) for job_id in jobs):raise ValueError("durable task batch contract is invalid")
        task_class=task_class.strip()
        if not task_class:raise ValueError("durable task batch contract is invalid")
        prepared = [(job_id.strip(), self._values(job_id, task_class, job)) for job_id, job in jobs.items()]
        if any(not job_id for job_id,_ in prepared) or len({job_id for job_id,_ in prepared}) != len(prepared):raise ValueError("durable task batch contains duplicate normalized job ids")
        applied: list[str] = []
        with self._lock, self._connection() as connection:
            for job_id, values in prepared:
                current = connection.execute(
                    "SELECT payload_json,task_class,tenant_id,user_id,project_id FROM durable_tasks WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if current and current["task_class"] != task_class:
                    raise ValueError("durable task job_id belongs to another task class")
                if current and tuple(current[key] for key in ("tenant_id", "user_id", "project_id")) != tuple(
                    values[key] for key in ("tenant_id", "user_id", "project_id")
                ):
                    raise ValueError("durable task owner scope is immutable")
                if current and current["task_class"] == task_class and current["payload_json"] == values["payload_json"]:
                    continue
                self._execute_upsert(connection, values)
                applied.append(job_id)
                if enqueue_projection:
                    event_revision = int(connection.execute("INSERT INTO task_projection_sequence DEFAULT VALUES").lastrowid)
                    connection.execute("""INSERT INTO task_projection_outbox(job_id,task_class,payload_json,updated_at,event_revision) VALUES(?,?,?,?,?)
                        ON CONFLICT(job_id) DO UPDATE SET task_class=excluded.task_class,payload_json=excluded.payload_json,
                        updated_at=excluded.updated_at,event_revision=excluded.event_revision""",
                        (job_id, task_class, values["payload_json"], values["updated_at"], event_revision))
        applied_set=set(applied)
        with self._lock, self._connection() as connection:
            rows=connection.execute(f"SELECT * FROM durable_tasks WHERE job_id IN ({','.join('?' for _ in applied_set)})", tuple(applied_set)).fetchall() if applied_set else []
        return [self._record(row) for row in rows]

    @staticmethod
    def _values(job_id: str, task_class: str, job: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(job_id,str) or not isinstance(task_class,str):raise ValueError("durable task identity must be strings")
        if not isinstance(job, Mapping):raise ValueError("durable task payload must be a mapping")
        request = job.get("request") if isinstance(job.get("request"), Mapping) else {}
        now = datetime.now(UTC).isoformat()
        raw_scope=tuple(job.get(key) or request.get(key) or "" for key in ("tenant_id","user_id","project_id"))
        if any(not isinstance(value,str) for value in raw_scope):raise ValueError("durable task owner scope is required")
        tenant_id,user_id,project_id=(value.strip() for value in raw_scope)
        if not job_id.strip() or not task_class.strip() or not all((tenant_id,user_id,project_id)):raise ValueError("durable task owner scope is required")
        string_fields={"stage":job.get("stage") or job.get("phase") or task_class,"subject_key":job.get("subject_key") or "","status":job.get("status") or "queued","heartbeat_at":job.get("heartbeat_at") or "","started_at":job.get("started_at") or job.get("queued_at") or "","finished_at":job.get("finished_at") or ""}
        if any(not isinstance(value,str) for value in string_fields.values()):raise ValueError("durable task lifecycle fields must be strings")
        for field in ("pid","process_group"):
            value=job.get(field)
            if value is not None and (isinstance(value,bool) or not isinstance(value,int) or value<=0):raise ValueError("durable task process identity is invalid")
        try:payload_json=json.dumps(dict(job),ensure_ascii=False,sort_keys=True,allow_nan=False)
        except (TypeError,ValueError) as error:raise ValueError("durable task payload must be standard JSON") from error
        return {
            "job_id":job_id.strip(), "task_class":task_class.strip(),
            "tenant_id":tenant_id, "user_id":user_id, "project_id":project_id,
            **string_fields, "pid":job.get("pid"), "process_group":job.get("process_group"),
            "payload_json":payload_json, "updated_at":now,
        }

    @staticmethod
    def _execute_upsert(connection: sqlite3.Connection, values: Mapping[str, Any]) -> None:
        connection.execute("""
                INSERT INTO durable_tasks VALUES (:job_id,:task_class,:tenant_id,:user_id,:project_id,:stage,:subject_key,:status,:pid,:process_group,:heartbeat_at,:started_at,:finished_at,:payload_json,:updated_at)
                ON CONFLICT(job_id) DO UPDATE SET task_class=excluded.task_class,tenant_id=excluded.tenant_id,user_id=excluded.user_id,
                project_id=excluded.project_id,stage=excluded.stage,subject_key=excluded.subject_key,status=excluded.status,pid=excluded.pid,
                process_group=excluded.process_group,heartbeat_at=excluded.heartbeat_at,started_at=excluded.started_at,
                finished_at=excluded.finished_at,payload_json=excluded.payload_json,updated_at=excluded.updated_at
            """, values)

    def pending_projections(self, *, task_class: str = "") -> list[dict[str, Any]]:
        if not isinstance(task_class,str):raise ValueError("projection task_class must be a string")
        query = "SELECT * FROM task_projection_outbox" + (" WHERE task_class=?" if task_class else "") + " ORDER BY updated_at,job_id"
        with self._lock, self._connection() as connection:
            rows = connection.execute(query, (task_class,) if task_class else ()).fetchall()
        return [{"job_id":row["job_id"], "task_class":row["task_class"], "payload":self._decode_payload(row["payload_json"]), "updated_at":row["updated_at"], "event_revision":int(row["event_revision"])} for row in rows]

    def acknowledge_projections(self, events: list[str | tuple[str, int]]) -> int:
        if not isinstance(events,list):raise ValueError("projection acknowledgements must be a list")
        if any((isinstance(item,tuple) and (len(item)!=2 or not isinstance(item[0],str) or not item[0].strip() or isinstance(item[1],bool) or not isinstance(item[1],int) or item[1]<=0)) or (not isinstance(item,tuple) and (not isinstance(item,str) or not item.strip())) for item in events):raise ValueError("projection acknowledgement is invalid")
        unversioned = sorted({item.strip() for item in events if isinstance(item,str)})
        versioned = sorted({(item[0].strip(), item[1]) for item in events if isinstance(item,tuple)})
        if not unversioned and not versioned: return 0
        with self._lock, self._connection() as connection:
            deleted = 0
            if unversioned:
                deleted += int(connection.execute(f"DELETE FROM task_projection_outbox WHERE job_id IN ({','.join('?' for _ in unversioned)})", unversioned).rowcount)
            for job_id, revision in versioned:
                deleted += int(connection.execute("DELETE FROM task_projection_outbox WHERE job_id=? AND event_revision=?", (job_id, revision)).rowcount)
        return deleted

    def requeue_projection(self, job_id: str) -> int:
        if not isinstance(job_id,str) or not job_id.strip():raise ValueError("projection job_id is required")
        job_id=job_id.strip()
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT task_class,payload_json FROM durable_tasks WHERE job_id=?", (str(job_id),)).fetchone()
            if not row: return 0
            event_revision = int(connection.execute("INSERT INTO task_projection_sequence DEFAULT VALUES").lastrowid)
            now = datetime.now(UTC).isoformat()
            connection.execute("""INSERT INTO task_projection_outbox(job_id,task_class,payload_json,updated_at,event_revision) VALUES(?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET task_class=excluded.task_class,payload_json=excluded.payload_json,
                updated_at=excluded.updated_at,event_revision=excluded.event_revision""",
                (str(job_id), row["task_class"], row["payload_json"], now, event_revision))
        return event_revision

    @contextmanager
    def projection_lock(self, scope_key: str, *, ttl: float = 30.0):
        if not isinstance(scope_key,str):raise ValueError("invalid projection lock")
        key = scope_key.strip(); owner = uuid4().hex
        if not key or isinstance(ttl,bool) or not isinstance(ttl,(int,float)) or not math.isfinite(ttl) or ttl <= 1: raise ValueError("invalid projection lock")
        now = time.time()
        lost = Event(); lease = ProjectionLease(False, lost, self, key, owner)
        acquired = False
        try:
            with self._lock, self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute("SELECT owner_id,expires_at FROM task_projection_locks WHERE scope_key=?", (key,)).fetchone()
                if not current or float(current["expires_at"]) <= now:
                    connection.execute("""INSERT INTO task_projection_locks(scope_key,owner_id,expires_at) VALUES(?,?,?)
                        ON CONFLICT(scope_key) DO UPDATE SET owner_id=excluded.owner_id,expires_at=excluded.expires_at""", (key, owner, now + ttl))
                    acquired = True
        except sqlite3.OperationalError:
            acquired = False
        lease.acquired = acquired
        if not acquired:
            yield lease
            return
        stop = Event()
        def renew() -> None:
            while not stop.wait(ttl / 3):
                try:
                    with self._lock, self._connection() as connection:
                        result = connection.execute("UPDATE task_projection_locks SET expires_at=? WHERE scope_key=? AND owner_id=?", (time.time() + ttl, key, owner))
                    if result.rowcount != 1: lost.set(); return
                except sqlite3.Error:
                    lost.set(); return
        renewal = Thread(target=renew, daemon=True, name=f"projection-lock-{owner[:8]}"); renewal.start()
        try:
            yield lease
        finally:
            stop.set(); renewal.join(timeout=1)
            try:
                with self._lock, self._connection() as connection:
                    connection.execute("DELETE FROM task_projection_locks WHERE scope_key=? AND owner_id=?", (key, owner))
            except sqlite3.Error:
                # Release is best effort. The row is owner fenced and its TTL
                # guarantees recovery; a transient busy database must not tear
                # down the worker heartbeat or projection drain.
                pass

    def get(self, job_id: str, *, tenant_id: str, user_id: str, project_id: str) -> dict[str, Any] | None:
        if not isinstance(job_id,str):raise ValueError("durable task job_id is required")
        job_id=job_id.strip()
        if not job_id:raise ValueError("durable task job_id is required")
        if any(not isinstance(value,str) for value in (tenant_id,user_id,project_id)):raise ValueError("durable task owner scope is required")
        scope=tuple(value.strip() for value in (tenant_id,user_id,project_id))
        if not all(scope):raise ValueError("durable task owner scope is required")
        with self._lock, self._connection() as connection:
            row = connection.execute("SELECT * FROM durable_tasks WHERE job_id=? AND tenant_id=? AND user_id=? AND project_id=?", (job_id,*scope)).fetchone()
        return self._record(row) if row else None

    def list(self, *, tenant_id: str = "", user_id: str = "", project_id: str = "", task_class: str = "", nonterminal_only: bool = False) -> list[dict[str, Any]]:
        if not isinstance(nonterminal_only,bool):raise ValueError("nonterminal_only must be boolean")
        if any(not isinstance(value,str) for value in (tenant_id,user_id,project_id,task_class)):raise ValueError("durable task query scope must be strings")
        scope=tuple(value.strip() for value in (tenant_id,user_id,project_id)); task_class=task_class.strip()
        if any(scope) and not all(scope):raise ValueError("tenant_id, user_id and project_id must be supplied together")
        clauses: list[str] = []; values: list[Any] = []
        for column, value in zip(("tenant_id","user_id","project_id"),scope):
            if value: clauses.append(f"{column}=?"); values.append(value)
        if task_class: clauses.append("task_class=?"); values.append(task_class)
        if nonterminal_only: clauses.append("status IN ('queued','waiting_memory','generating','running','retrying','processing')")
        query = "SELECT * FROM durable_tasks" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY updated_at DESC"
        with self._lock, self._connection() as connection: rows = connection.execute(query, values).fetchall()
        return [self._record(row) for row in rows]

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        return {key:row[key] for key in row.keys() if key != "payload_json"} | {"payload":DurableTaskRepository._decode_payload(row["payload_json"])}

    @staticmethod
    def _decode_payload(raw: Any) -> dict[str, Any]:
        try:payload=json.loads(raw,parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
        except (json.JSONDecodeError,ValueError,TypeError) as error:raise ValueError("durable task payload is invalid") from error
        if not isinstance(payload,dict):raise ValueError("durable task payload is invalid")
        return payload
