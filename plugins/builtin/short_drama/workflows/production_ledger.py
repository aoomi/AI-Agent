"""Authoritative SQLite production ledger for the short-drama workflow."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, Iterable, Mapping
from uuid import uuid4


CANONICAL_STAGES = (
    "requirements", "outline", "script", "storyboard", "assets", "image",
    "video", "audio", "subtitle", "composition", "review_export",
)
STAGE_ALIASES = {
    "requirement": "requirements", "characters": "assets", "shots": "image",
    "shot_images": "image", "shot_videos": "video", "merge": "composition",
    "merged_episodes": "composition", "review": "review_export",
    "final_audit": "review_export", "export": "review_export", "upscale": "review_export",
}
LIFECYCLES = {
    "idle", "queued", "running", "pending_confirmation", "completed", "paused",
    "failed", "stale", "skipped", "cancelled",
}
SCOPE_TYPES = {"project", "story_arc_batch", "episode_batch", "episode", "scene", "shot", "line", "asset"}
TERMINAL_LIFECYCLES = {"completed", "failed", "skipped", "cancelled"}


class ProductionLedgerError(ValueError):
    pass


def canonical_stage(value: object) -> str:
    stage = str(value or "").strip()
    stage = STAGE_ALIASES.get(stage, stage)
    if stage not in CANONICAL_STAGES:
        raise ProductionLedgerError(f"unknown production stage: {stage}")
    return stage


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ProductionLedger:
    """Single source of truth for scope state, dependencies and immutable versions."""

    def __init__(self, database: Path) -> None:
        self.database = database.resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS production_scopes (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    plugin_key TEXT NOT NULL,
                    lifecycle TEXT NOT NULL,
                    stage_substate TEXT NOT NULL,
                    content_fingerprint TEXT NOT NULL,
                    audit_batch_id TEXT NOT NULL,
                    confirmation_json TEXT,
                    progress_json TEXT NOT NULL,
                    checkpoint TEXT NOT NULL,
                    error TEXT NOT NULL,
                    confirmation_scope_json TEXT NOT NULL,
                    impact_scope_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, user_id, project_id, stage, scope_type, scope_id)
                );
                CREATE TABLE IF NOT EXISTS production_dependencies (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    source_stage TEXT NOT NULL,
                    source_scope_type TEXT NOT NULL,
                    source_scope_id TEXT NOT NULL,
                    target_stage TEXT NOT NULL,
                    target_scope_type TEXT NOT NULL,
                    target_scope_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,user_id,project_id,source_stage,source_scope_type,source_scope_id,target_stage,target_scope_type,target_scope_id)
                );
                CREATE TABLE IF NOT EXISTS production_versions (
                    version_id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    version_status TEXT NOT NULL,
                    versioned_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_production_scope_project
                    ON production_scopes(tenant_id,user_id,project_id,stage,scope_type,scope_id);
            """)

    @staticmethod
    def _identity(payload: Mapping[str, Any]) -> tuple[str, str, str]:
        values = tuple(str(payload.get(key, "")).strip() for key in ("tenant_id", "user_id", "project_id"))
        if not all(values):
            raise ProductionLedgerError("tenant_id, user_id and project_id are required")
        return values  # type: ignore[return-value]

    @staticmethod
    def _key(payload: Mapping[str, Any]) -> tuple[str, str, str]:
        stage = canonical_stage(payload.get("stage"))
        scope_type = str(payload.get("scope_type", "")).strip()
        scope_id = str(payload.get("scope_id", "")).strip()
        if scope_type not in SCOPE_TYPES or not scope_id:
            raise ProductionLedgerError("valid scope_type and scope_id are required")
        return stage, scope_type, scope_id

    def list(self, identity: Mapping[str, Any]) -> list[dict[str, Any]]:
        tenant_id, user_id, project_id = self._identity(identity)
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM production_scopes WHERE tenant_id=? AND user_id=? AND project_id=? ORDER BY stage,scope_type,scope_id",
                (tenant_id, user_id, project_id),
            ).fetchall()
        return [self._record(row) for row in rows]

    def upsert(self, payload: Mapping[str, Any], *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        tenant_id, user_id, project_id = self._identity(payload)
        stage, scope_type, scope_id = self._key(payload)
        lifecycle = str(payload.get("lifecycle", "idle")).strip()
        if lifecycle not in LIFECYCLES:
            raise ProductionLedgerError(f"invalid lifecycle: {lifecycle}")
        owns_connection = connection is None
        context = self._connection() if owns_connection else _existing_connection(connection)
        with context as active:
            current = active.execute(
                "SELECT * FROM production_scopes WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?",
                (tenant_id, user_id, project_id, stage, scope_type, scope_id),
            ).fetchone()
            created_at = current["created_at"] if current else _now()
            record_id = current["id"] if current else f"scope-{uuid4().hex}"
            confirmation = json.loads(current["confirmation_json"]) if current and current["confirmation_json"] else None
            if current and current["content_fingerprint"] != str(payload.get("content_fingerprint", current["content_fingerprint"])):
                confirmation = None
            if "confirmation" in payload:
                confirmation = payload.get("confirmation")
            values = {
                "id": record_id, "tenant_id": tenant_id, "user_id": user_id, "project_id": project_id,
                "stage": stage, "scope_type": scope_type, "scope_id": scope_id,
                "plugin_key": str(payload.get("plugin_key", current["plugin_key"] if current else "short_drama")),
                "lifecycle": lifecycle,
                "stage_substate": str(payload.get("stage_substate", current["stage_substate"] if current else "")),
                "content_fingerprint": str(payload.get("content_fingerprint", current["content_fingerprint"] if current else "")),
                "audit_batch_id": str(payload.get("audit_batch_id", current["audit_batch_id"] if current else "")),
                "confirmation_json": _json(confirmation) if confirmation else None,
                "progress_json": _json(payload.get("progress", json.loads(current["progress_json"]) if current else {"completed": 0, "total": 1})),
                "checkpoint": str(payload.get("checkpoint", current["checkpoint"] if current else "")),
                "error": str(payload.get("error", current["error"] if current else "")),
                "confirmation_scope_json": _json(payload.get("confirmation_scope", json.loads(current["confirmation_scope_json"]) if current else {"scope_type": scope_type, "scope_ids": [scope_id]})),
                "impact_scope_json": _json(payload.get("impact_scope", json.loads(current["impact_scope_json"]) if current else [])),
                "created_at": created_at, "updated_at": _now(),
            }
            active.execute("""
                INSERT INTO production_scopes VALUES (
                    :id,:tenant_id,:user_id,:project_id,:stage,:scope_type,:scope_id,:plugin_key,:lifecycle,:stage_substate,
                    :content_fingerprint,:audit_batch_id,:confirmation_json,:progress_json,:checkpoint,:error,
                    :confirmation_scope_json,:impact_scope_json,:created_at,:updated_at
                ) ON CONFLICT(tenant_id,user_id,project_id,stage,scope_type,scope_id) DO UPDATE SET
                    plugin_key=excluded.plugin_key,lifecycle=excluded.lifecycle,stage_substate=excluded.stage_substate,
                    content_fingerprint=excluded.content_fingerprint,audit_batch_id=excluded.audit_batch_id,
                    confirmation_json=excluded.confirmation_json,progress_json=excluded.progress_json,
                    checkpoint=excluded.checkpoint,error=excluded.error,confirmation_scope_json=excluded.confirmation_scope_json,
                    impact_scope_json=excluded.impact_scope_json,updated_at=excluded.updated_at
            """, values)
            row = active.execute("SELECT * FROM production_scopes WHERE id=?", (record_id,)).fetchone()
            self._snapshot(active, row, "current")
            return self._record(row)

    def upsert_many(self, records: Iterable[Mapping[str, Any]], *, replace: bool = False) -> list[dict[str, Any]]:
        records = list(records)
        if not records:
            return []
        identity = self._identity(records[0])
        if any(self._identity(item) != identity for item in records):
            raise ProductionLedgerError("bulk records must share one identity")
        with self._lock, self._connection() as connection:
            if replace:
                keys = {(canonical_stage(item.get("stage")), str(item.get("scope_type")), str(item.get("scope_id"))) for item in records}
                rows = connection.execute(
                    "SELECT stage,scope_type,scope_id FROM production_scopes WHERE tenant_id=? AND user_id=? AND project_id=?",
                    identity,
                ).fetchall()
                for row in rows:
                    if (row["stage"], row["scope_type"], row["scope_id"]) not in keys:
                        connection.execute(
                            "DELETE FROM production_scopes WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?",
                            (*identity, row["stage"], row["scope_type"], row["scope_id"]),
                        )
            return [self.upsert(item, connection=connection) for item in records]

    def confirm(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        tenant_id, user_id, project_id = self._identity(payload)
        stage, scope_type, scope_id = self._key(payload)
        with self._lock, self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM production_scopes WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?",
                (tenant_id, user_id, project_id, stage, scope_type, scope_id),
            ).fetchone()
            if not row:
                raise ProductionLedgerError("production scope does not exist")
            confirmation = {"content_fingerprint": row["content_fingerprint"], "audit_batch_id": row["audit_batch_id"], "confirmed_by": user_id, "confirmed_at": _now()}
            connection.execute("UPDATE production_scopes SET lifecycle='completed',confirmation_json=?,updated_at=? WHERE id=?", (_json(confirmation), _now(), row["id"]))
            updated = connection.execute("SELECT * FROM production_scopes WHERE id=?", (row["id"],)).fetchone()
            self._snapshot(connection, updated, "confirmed")
            return self._record(updated)

    def dependency(self, payload: Mapping[str, Any], *, connection: sqlite3.Connection | None = None) -> None:
        tenant_id, user_id, project_id = self._identity(payload)
        source = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
        target = payload.get("target") if isinstance(payload.get("target"), Mapping) else {}
        source_stage, source_type, source_id = self._key(source)
        target_stage, target_type, target_id = self._key(target)
        context = self._connection() if connection is None else _existing_connection(connection)
        with context as active:
            active.execute("INSERT OR IGNORE INTO production_dependencies VALUES (?,?,?,?,?,?,?,?,?,?)", (
                tenant_id, user_id, project_id, source_stage, source_type, source_id,
                target_stage, target_type, target_id, _now(),
            ))

    def dependencies(self, records: Iterable[Mapping[str, Any]]) -> None:
        with self._lock, self._connection() as connection:
            for record in records:
                self.dependency(record, connection=connection)

    def impact(self, payload: Mapping[str, Any], *, mutate: bool) -> list[dict[str, Any]]:
        tenant_id, user_id, project_id = self._identity(payload)
        source = payload.get("source") if isinstance(payload.get("source"), Mapping) else payload
        source_stage, source_type, source_id = self._key(source)
        with self._lock, self._connection() as connection:
            pending = [(source_stage, source_type, source_id)]
            seen: set[tuple[str, str, str]] = set()
            while pending:
                current = pending.pop(0)
                rows = connection.execute("""
                    SELECT target_stage,target_scope_type,target_scope_id FROM production_dependencies
                    WHERE tenant_id=? AND user_id=? AND project_id=? AND source_stage=? AND source_scope_type=? AND source_scope_id=?
                """, (tenant_id, user_id, project_id, *current)).fetchall()
                for row in rows:
                    key = (row["target_stage"], row["target_scope_type"], row["target_scope_id"])
                    if key not in seen:
                        seen.add(key); pending.append(key)
            if mutate and seen:
                for stage, scope_type, scope_id in seen:
                    connection.execute("""
                        UPDATE production_scopes SET lifecycle='stale',confirmation_json=NULL,error=?,updated_at=?
                        WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
                    """, (str(payload.get("reason") or "上游内容已变化"), _now(), tenant_id, user_id, project_id, stage, scope_type, scope_id))
            return [self._record(row) for row in connection.execute(
                "SELECT * FROM production_scopes WHERE tenant_id=? AND user_id=? AND project_id=?",
                (tenant_id, user_id, project_id),
            ).fetchall() if (row["stage"], row["scope_type"], row["scope_id"]) in seen]

    def withdraw(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        tenant_id, user_id, project_id = self._identity(payload)
        stage, scope_type, scope_id = self._key(payload)
        with self._lock, self._connection() as connection:
            connection.execute("""
                UPDATE production_scopes SET lifecycle='pending_confirmation',confirmation_json=NULL,error=?,updated_at=?
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
            """, (str(payload.get("reason") or "人工撤回确认"), _now(), tenant_id, user_id, project_id, stage, scope_type, scope_id))
        return self.impact({**payload, "source": {"stage": stage, "scope_type": scope_type, "scope_id": scope_id}, "reason": payload.get("reason")}, mutate=True)

    def restore_pending_confirmation(self, payload: Mapping[str, Any], reason: str) -> dict[str, Any]:
        tenant_id, user_id, project_id = self._identity(payload); stage, scope_type, scope_id = self._key(payload)
        with self._lock, self._connection() as connection:
            connection.execute("""UPDATE production_scopes SET lifecycle='pending_confirmation',confirmation_json=NULL,error=?,updated_at=?
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?""",
                (reason, _now(), tenant_id, user_id, project_id, stage, scope_type, scope_id))
            row = connection.execute("SELECT * FROM production_scopes WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?",
                (tenant_id, user_id, project_id, stage, scope_type, scope_id)).fetchone()
            if not row: raise ProductionLedgerError("production scope does not exist")
            self._snapshot(connection, row, "confirmation_rollback")
            return self._record(row)

    def versions(self, identity: Mapping[str, Any]) -> list[dict[str, Any]]:
        records = self.list(identity)
        ids = [record["id"] for record in records]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self._lock, self._connection() as connection:
            rows = connection.execute(f"SELECT * FROM production_versions WHERE scope_id IN ({placeholders}) ORDER BY versioned_at DESC", ids).fetchall()
        return [{**json.loads(row["snapshot_json"]), "version_id": row["version_id"], "version_status": row["version_status"], "versioned_at": row["versioned_at"]} for row in rows]

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "tenant_id": row["tenant_id"], "user_id": row["user_id"], "project_id": row["project_id"],
            "stage": row["stage"], "scope_type": row["scope_type"], "scope_id": row["scope_id"], "plugin_key": row["plugin_key"],
            "lifecycle": row["lifecycle"], "stage_substate": row["stage_substate"], "content_fingerprint": row["content_fingerprint"],
            "audit_batch_id": row["audit_batch_id"], "confirmation": json.loads(row["confirmation_json"]) if row["confirmation_json"] else None,
            "progress": json.loads(row["progress_json"]), "checkpoint": row["checkpoint"], "error": row["error"],
            "confirmation_scope": json.loads(row["confirmation_scope_json"]), "impact_scope": json.loads(row["impact_scope_json"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    def _snapshot(self, connection: sqlite3.Connection, row: sqlite3.Row, status: str) -> None:
        connection.execute(
            "INSERT INTO production_versions VALUES (?,?,?,?,?)",
            (f"version-{uuid4().hex}", row["id"], _json(self._record(row)), status, _now()),
        )


@contextmanager
def _existing_connection(connection: sqlite3.Connection):
    yield connection
