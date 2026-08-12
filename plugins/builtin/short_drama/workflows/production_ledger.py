"""Authoritative SQLite production ledger for the short-drama workflow."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, Callable, Iterable, Mapping
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
UPSCALE_EVIDENCE_FIELDS = {"production_evidence", "audit_evidence"}
UPSCALE_SERVER_FIELDS = {
    "content_fingerprint", "audit_batch_id", "generation", "confirmation",
    *UPSCALE_EVIDENCE_FIELDS,
}


class ProductionLedgerError(ValueError):
    pass


def canonical_stage(value: object) -> str:
    if not isinstance(value, str):
        raise ProductionLedgerError("production stage must be a string")
    stage = value.strip()
    stage = STAGE_ALIASES.get(stage, stage)
    if stage not in CANONICAL_STAGES:
        raise ProductionLedgerError(f"unknown production stage: {stage}")
    return stage


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _is_upscale_scope(stage: str, scope_type: str, scope_id: str) -> bool:
    return stage == "review_export" and scope_type == "episode" and scope_id.startswith("upscale:")


def _nonempty_evidence(value: object, label: str) -> str:
    if value is None or value == "" or value == {} or value == []:
        raise ProductionLedgerError(f"{label} must be non-empty canonical JSON")
    try:
        return _json(value)
    except (TypeError, ValueError) as error:
        raise ProductionLedgerError(f"{label} must be non-empty canonical JSON") from error


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ProductionLedgerError(f"{label} must be an integer")
    return value


def _string(value: object, label: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise ProductionLedgerError(f"{label} must be a string")
    normalized = value.strip()
    if not allow_empty and not normalized:
        raise ProductionLedgerError(f"{label} must be a non-empty string")
    return normalized


class ProductionLedger:
    """Single source of truth for scope state, dependencies and immutable versions."""

    def __init__(self, database: Path) -> None:
        if not isinstance(database, Path):
            raise ProductionLedgerError("production ledger database must be a Path")
        self.database = database.resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    @contextmanager
    def _connection(self):
        # LangGraph persists checkpoints from its executor thread while the
        # authority coordinator owns this same transaction.
        connection = sqlite3.connect(self.database, timeout=30, check_same_thread=False)
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
                    generation INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 0,
                    production_evidence_json TEXT,
                    audit_evidence_json TEXT,
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
            # Schema upgrades are serialized across processes.  Rechecking after
            # BEGIN IMMEDIATE makes concurrent startup safe for an existing DB.
            connection.execute("BEGIN IMMEDIATE")
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(production_scopes)").fetchall()}
            for name, definition in (
                ("generation", "INTEGER NOT NULL DEFAULT 0"),
                ("revision", "INTEGER NOT NULL DEFAULT 0"),
                ("production_evidence_json", "TEXT"),
                ("audit_evidence_json", "TEXT"),
            ):
                if name not in columns:
                    connection.execute(f"ALTER TABLE production_scopes ADD COLUMN {name} {definition}")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS production_scope_generations (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,user_id,project_id,stage,scope_type,scope_id)
                );
                CREATE TABLE IF NOT EXISTS production_upscale_authority (
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    content_fingerprint TEXT NOT NULL,
                    audit_batch_id TEXT NOT NULL,
                    production_evidence_json TEXT NOT NULL,
                    audit_evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,user_id,project_id,stage,scope_type,scope_id,generation),
                    UNIQUE(tenant_id,user_id,project_id,stage,scope_type,scope_id,content_fingerprint,audit_batch_id)
                );
            """)

    @staticmethod
    def _identity(payload: Mapping[str, Any]) -> tuple[str, str, str]:
        raw = tuple(payload.get(key, "") for key in ("tenant_id", "user_id", "project_id"))
        if any(not isinstance(value,str) for value in raw):raise ProductionLedgerError("tenant_id, user_id and project_id are required")
        values = tuple(value.strip() for value in raw)
        if not all(values):
            raise ProductionLedgerError("tenant_id, user_id and project_id are required")
        return values  # type: ignore[return-value]

    @staticmethod
    def _key(payload: Mapping[str, Any]) -> tuple[str, str, str]:
        stage = canonical_stage(payload.get("stage"))
        scope_type,scope_id=payload.get("scope_type", ""),payload.get("scope_id", "")
        if not isinstance(scope_type,str) or not isinstance(scope_id,str):raise ProductionLedgerError("valid scope_type and scope_id are required")
        scope_type,scope_id=scope_type.strip(),scope_id.strip()
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

    def reserve_upscale_generation(self, payload: Mapping[str, Any]) -> int:
        """Allocate one durable monotonic generation for a real upscale run."""
        tenant_id, user_id, project_id = self._identity(payload)
        stage, scope_type, scope_id = self._key(payload)
        if not _is_upscale_scope(stage, scope_type, scope_id):
            raise ProductionLedgerError("upscale generation requires review_export/upscale episode scope")
        key = (tenant_id, user_id, project_id, stage, scope_type, scope_id)
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            counter = connection.execute("""
                SELECT generation FROM production_scope_generations
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
            """, key).fetchone()
            current = connection.execute("""
                SELECT generation FROM production_scopes
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
            """, key).fetchone()
            generation = max(
                int(counter["generation"] if counter else 0),
                int(current["generation"] if current else 0),
            ) + 1
            connection.execute("""
                INSERT INTO production_scope_generations
                    (tenant_id,user_id,project_id,stage,scope_type,scope_id,generation,updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id,user_id,project_id,stage,scope_type,scope_id)
                DO UPDATE SET generation=excluded.generation,updated_at=excluded.updated_at
            """, (*key, generation, _now()))
        return generation

    def commit_upscale_authority(
        self, payload: Mapping[str, Any], *, connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        """Commit server-created upscale evidence with durable generation/CAS fences."""
        tenant_id, user_id, project_id = self._identity(payload)
        stage, scope_type, scope_id = self._key(payload)
        if not _is_upscale_scope(stage, scope_type, scope_id):
            raise ProductionLedgerError("authoritative upscale commit requires an upscale episode scope")
        generation = payload.get("generation")
        fingerprint = payload.get("content_fingerprint")
        audit_batch_id = payload.get("audit_batch_id")
        if (isinstance(generation,bool) or not isinstance(generation,int) or not isinstance(fingerprint,str)
                or not isinstance(audit_batch_id,str)):
            raise ProductionLedgerError("authoritative upscale generation, fingerprint and audit batch are required")
        fingerprint,audit_batch_id=fingerprint.strip(),audit_batch_id.strip()
        if generation < 1 or not fingerprint or not audit_batch_id:
            raise ProductionLedgerError("authoritative upscale generation, fingerprint and audit batch are required")
        production_json = _nonempty_evidence(payload.get("production_evidence"), "production_evidence")
        audit_json = _nonempty_evidence(payload.get("audit_evidence"), "audit_evidence")
        key = (tenant_id, user_id, project_id, stage, scope_type, scope_id)
        owns_connection = connection is None
        context = self._connection() if owns_connection else _existing_connection(connection)
        with self._lock, context as active:
            if owns_connection:
                active.execute("BEGIN IMMEDIATE")
            counter = active.execute("""
                SELECT generation FROM production_scope_generations
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
            """, key).fetchone()
            if not counter or int(counter["generation"]) != generation:
                raise ProductionLedgerError("stale or unreserved upscale generation")
            current = active.execute("""
                SELECT * FROM production_scopes
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
            """, key).fetchone()
            if current and int(current["generation"] or 0) > generation:
                raise ProductionLedgerError("stale upscale generation")
            history = active.execute("""
                SELECT * FROM production_upscale_authority
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=? AND generation=?
            """, (*key, generation)).fetchone()
            exact = (
                history
                and history["content_fingerprint"] == fingerprint
                and history["audit_batch_id"] == audit_batch_id
                and history["production_evidence_json"] == production_json
                and history["audit_evidence_json"] == audit_json
            )
            if history and not exact:
                raise ProductionLedgerError("same-generation upscale authority is immutable")
            replay = active.execute("""
                SELECT generation FROM production_upscale_authority
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
                  AND content_fingerprint=? AND audit_batch_id=? AND generation<>?
            """, (*key, fingerprint, audit_batch_id, generation)).fetchone()
            if replay:
                raise ProductionLedgerError("old upscale fingerprint and audit batch cannot be replayed")
            if current and int(current["generation"] or 0) == generation:
                same_current = (
                    current["content_fingerprint"] == fingerprint
                    and current["audit_batch_id"] == audit_batch_id
                    and current["production_evidence_json"] == production_json
                    and current["audit_evidence_json"] == audit_json
                )
                if not same_current:
                    raise ProductionLedgerError("same-generation upscale authority is immutable")
                if not history:
                    active.execute("""
                        INSERT INTO production_upscale_authority VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (*key, generation, fingerprint, audit_batch_id, production_json, audit_json, _now()))
                return self._record(current)
            created_at = current["created_at"] if current else _now()
            record_id = current["id"] if current else f"scope-{uuid4().hex}"
            current_revision = int(current["revision"] or 0) if current else 0
            expected_revision = payload.get("expected_revision")
            if expected_revision is not None:
                if isinstance(expected_revision,bool) or not isinstance(expected_revision,int):raise ProductionLedgerError("expected_revision must be an integer")
                if expected_revision != current_revision:
                    raise ProductionLedgerError("production scope CAS conflict")
            progress = json.loads(current["progress_json"]) if current else {"completed": 0, "total": 1}
            progress = {key: value for key, value in progress.items() if key not in UPSCALE_EVIDENCE_FIELDS}
            incoming_progress = payload.get("progress")
            if incoming_progress is not None and not isinstance(incoming_progress, Mapping):
                raise ProductionLedgerError("progress must be an object")
            if isinstance(incoming_progress, Mapping):
                for name, value in incoming_progress.items():
                    if name not in UPSCALE_EVIDENCE_FIELDS and value is not None:
                        progress[name] = value
            values = {
                "id": record_id, "tenant_id": tenant_id, "user_id": user_id, "project_id": project_id,
                "stage": stage, "scope_type": scope_type, "scope_id": scope_id,
                "plugin_key": str(payload.get("plugin_key") or (current["plugin_key"] if current else "short_drama")),
                "lifecycle": "pending_confirmation", "stage_substate": str(payload.get("stage_substate") or "upscale"),
                "content_fingerprint": fingerprint, "audit_batch_id": audit_batch_id,
                "confirmation_json": None, "progress_json": _json(progress),
                "checkpoint": str(payload.get("checkpoint") or f"upscale:{generation}"), "error": "",
                "confirmation_scope_json": _json(payload.get("confirmation_scope") or {"scope_type": scope_type, "scope_ids": [scope_id]}),
                "impact_scope_json": _json(payload.get("impact_scope") or []),
                "created_at": created_at, "updated_at": _now(), "generation": generation,
                "revision": current_revision + 1, "production_evidence_json": production_json,
                "audit_evidence_json": audit_json,
            }
            if current:
                cursor = active.execute("""
                    UPDATE production_scopes SET plugin_key=:plugin_key,lifecycle=:lifecycle,stage_substate=:stage_substate,
                        content_fingerprint=:content_fingerprint,audit_batch_id=:audit_batch_id,confirmation_json=NULL,
                        progress_json=:progress_json,checkpoint=:checkpoint,error=:error,
                        confirmation_scope_json=:confirmation_scope_json,impact_scope_json=:impact_scope_json,
                        updated_at=:updated_at,generation=:generation,revision=:revision,
                        production_evidence_json=:production_evidence_json,audit_evidence_json=:audit_evidence_json
                    WHERE id=:id AND revision=:current_revision AND generation<:generation
                """, {**values, "current_revision": current_revision})
                if cursor.rowcount != 1:
                    raise ProductionLedgerError("upscale authority CAS conflict")
            else:
                active.execute("""
                    INSERT INTO production_scopes (
                        id,tenant_id,user_id,project_id,stage,scope_type,scope_id,plugin_key,lifecycle,stage_substate,
                        content_fingerprint,audit_batch_id,confirmation_json,progress_json,checkpoint,error,
                        confirmation_scope_json,impact_scope_json,created_at,updated_at,generation,revision,
                        production_evidence_json,audit_evidence_json
                    ) VALUES (
                        :id,:tenant_id,:user_id,:project_id,:stage,:scope_type,:scope_id,:plugin_key,:lifecycle,:stage_substate,
                        :content_fingerprint,:audit_batch_id,:confirmation_json,:progress_json,:checkpoint,:error,
                        :confirmation_scope_json,:impact_scope_json,:created_at,:updated_at,:generation,:revision,
                        :production_evidence_json,:audit_evidence_json
                    )
                """, values)
            if not history:
                try:
                    active.execute("INSERT INTO production_upscale_authority VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (*key, generation, fingerprint, audit_batch_id, production_json, audit_json, _now()))
                except sqlite3.IntegrityError as error:
                    raise ProductionLedgerError("old upscale fingerprint and audit batch cannot be replayed") from error
            row = active.execute("SELECT * FROM production_scopes WHERE id=?", (record_id,)).fetchone()
            self._snapshot(active, row, "upscale_authority")
            return self._record(row)

    def commit_upscale_authorities(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        commit_callback: Callable[[sqlite3.Connection], Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Atomically publish an upscale batch around its control-plane commit.

        The callback runs after every authority row has passed validation but
        before the SQLite transaction is committed.  A failed control-plane
        commit therefore rolls the complete authority batch back and exposes
        no successful evidence.  Callers must additionally hold the stage
        lease commit guard so cancellation and this transaction are ordered.
        """
        records = list(records)
        if not records:
            return []
        identity = self._identity(records[0])
        if any(self._identity(item) != identity for item in records):
            raise ProductionLedgerError("authoritative upscale records must share one identity")
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            committed = [self.commit_upscale_authority(item, connection=connection) for item in records]
            if commit_callback is not None:
                commit_callback(connection)
            return committed

    def commit_stage_authorities(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        commit_callback: Callable[[sqlite3.Connection], Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Atomically publish server-created non-upscale evidence and its graph event."""
        records = list(records)
        if not records:
            raise ProductionLedgerError("authoritative stage records are required")
        identity = self._identity(records[0])
        if any(self._identity(item) != identity for item in records):
            raise ProductionLedgerError("authoritative stage records must share one identity")
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            committed: list[dict[str, Any]] = []
            for item in records:
                stage, scope_type, scope_id = self._key(item)
                if _is_upscale_scope(stage, scope_type, scope_id):
                    raise ProductionLedgerError("upscale authority requires the dedicated commit protocol")
                generation = _integer(item.get("generation"), "generation", minimum=1)
                fingerprint = _string(item.get("content_fingerprint"), "content_fingerprint", allow_empty=False)
                audit_batch_id = _string(item.get("audit_batch_id"), "audit_batch_id", allow_empty=False)
                production_json = _nonempty_evidence(item.get("production_evidence"), "production_evidence")
                audit_json = _nonempty_evidence(item.get("audit_evidence"), "audit_evidence")
                if generation < 1 or not fingerprint or not audit_batch_id:
                    raise ProductionLedgerError("authoritative generation, fingerprint and audit batch are required")
                current = connection.execute("""
                    SELECT * FROM production_scopes
                    WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
                """, (*identity, stage, scope_type, scope_id)).fetchone()
                if current and int(current["generation"] or 0) > generation:
                    raise ProductionLedgerError("stale authoritative stage generation")
                if current and int(current["generation"] or 0) == generation:
                    exact = (
                        current["content_fingerprint"] == fingerprint
                        and current["audit_batch_id"] == audit_batch_id
                        and current["production_evidence_json"] == production_json
                        and current["audit_evidence_json"] == audit_json
                    )
                    if not exact:
                        raise ProductionLedgerError("same-generation stage authority is immutable")
                    committed.append(self._record(current))
                    continue
                committed.append(self.upsert({**item, "lifecycle":"pending_confirmation", "confirmation":None}, connection=connection))
            if commit_callback is not None:
                commit_callback(connection)
            return committed

    def upsert(self, payload: Mapping[str, Any], *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        tenant_id, user_id, project_id = self._identity(payload)
        stage, scope_type, scope_id = self._key(payload)
        lifecycle = _string(payload.get("lifecycle", "idle"), "lifecycle", allow_empty=False)
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
            current_revision = int(current["revision"] or 0) if current else 0
            expected_revision = payload.get("expected_revision")
            if expected_revision is not None:
                expected_revision = _integer(expected_revision, "expected_revision")
                if expected_revision != current_revision:
                    raise ProductionLedgerError("production scope CAS conflict")
            confirmation = json.loads(current["confirmation_json"]) if current and current["confirmation_json"] else None
            next_fingerprint = str(payload.get("content_fingerprint", current["content_fingerprint"] if current else ""))
            next_audit_batch_id = str(payload.get("audit_batch_id", current["audit_batch_id"] if current else ""))
            generation_changed = bool(current) and (
                current["content_fingerprint"] != next_fingerprint
                or current["audit_batch_id"] != next_audit_batch_id
            )
            if generation_changed:
                confirmation = None
            elif "confirmation" in payload:
                confirmation = payload.get("confirmation")
            current_progress = json.loads(current["progress_json"]) if current else {"completed": 0, "total": 1}
            incoming_progress = payload.get("progress")
            # Evidence belongs to the exact fingerprint + audit-batch generation.
            # A projection from the same generation may omit/null evidence without
            # erasing it, but a new generation must start from an evidence-free
            # baseline and can only receive evidence carried by that same upsert.
            if generation_changed:
                current_progress = {
                    key: value for key, value in current_progress.items()
                    if key not in {"production_evidence", "audit_evidence"}
                }
            if incoming_progress is None:
                progress = current_progress
            elif not isinstance(incoming_progress, Mapping):
                raise ProductionLedgerError("progress must be an object")
            else:
                # UI projection updates are partial.  In particular, a deep watcher may
                # only know completed/total while the server-owned upscale evidence is
                # already durable.  Missing or null fields must never erase that evidence.
                progress = dict(current_progress)
                for key, value in incoming_progress.items():
                    if value is None:
                        continue
                    if generation_changed and key in {"production_evidence", "audit_evidence"}:
                        if value == "" or value == {} or value == []:
                            continue
                    progress[key] = value
            current_error = current["error"] if current else ""
            if bool(payload.get("reactivate")) and lifecycle not in {"failed", "cancelled", "stale"}:
                current_error = ""
            next_error = str(payload.get("error", current_error))
            if lifecycle == "completed":
                next_error = ""
            values = {
                "id": record_id, "tenant_id": tenant_id, "user_id": user_id, "project_id": project_id,
                "stage": stage, "scope_type": scope_type, "scope_id": scope_id,
                "plugin_key": str(payload.get("plugin_key", current["plugin_key"] if current else "short_drama")),
                "lifecycle": lifecycle,
                "stage_substate": str(payload.get("stage_substate", current["stage_substate"] if current else "")),
                "content_fingerprint": next_fingerprint,
                "audit_batch_id": next_audit_batch_id,
                "confirmation_json": _json(confirmation) if confirmation else None,
                "progress_json": _json(progress),
                "checkpoint": str(payload.get("checkpoint", current["checkpoint"] if current else "")),
                "error": next_error,
                "confirmation_scope_json": _json(payload.get("confirmation_scope", json.loads(current["confirmation_scope_json"]) if current else {"scope_type": scope_type, "scope_ids": [scope_id]})),
                "impact_scope_json": _json(payload.get("impact_scope", json.loads(current["impact_scope_json"]) if current else [])),
                "created_at": created_at, "updated_at": _now(),
                "generation": _integer(payload.get("generation", current["generation"] if current else 0), "generation"),
                "revision": current_revision + 1,
                "production_evidence_json": current["production_evidence_json"] if current else None,
                "audit_evidence_json": current["audit_evidence_json"] if current else None,
            }
            production_value = payload.get("production_evidence")
            audit_value = payload.get("audit_evidence")
            if production_value is not None:
                values["production_evidence_json"] = _nonempty_evidence(production_value, "production_evidence")
            if audit_value is not None:
                values["audit_evidence_json"] = _nonempty_evidence(audit_value, "audit_evidence")
            if _is_upscale_scope(stage, scope_type, scope_id):
                production_value = payload.get("production_evidence", progress.get("production_evidence"))
                audit_value = payload.get("audit_evidence", progress.get("audit_evidence"))
                if production_value is not None:
                    values["production_evidence_json"] = _json(production_value)
                if audit_value is not None:
                    values["audit_evidence_json"] = _json(audit_value)
                progress = {key: value for key, value in progress.items() if key not in UPSCALE_EVIDENCE_FIELDS}
                values["progress_json"] = _json(progress)
            active.execute("""
                INSERT INTO production_scopes (
                    id,tenant_id,user_id,project_id,stage,scope_type,scope_id,plugin_key,lifecycle,stage_substate,
                    content_fingerprint,audit_batch_id,confirmation_json,progress_json,checkpoint,error,
                    confirmation_scope_json,impact_scope_json,created_at,updated_at,generation,revision,
                    production_evidence_json,audit_evidence_json
                ) VALUES (
                    :id,:tenant_id,:user_id,:project_id,:stage,:scope_type,:scope_id,:plugin_key,:lifecycle,:stage_substate,
                    :content_fingerprint,:audit_batch_id,:confirmation_json,:progress_json,:checkpoint,:error,
                    :confirmation_scope_json,:impact_scope_json,:created_at,:updated_at,:generation,:revision,
                    :production_evidence_json,:audit_evidence_json
                ) ON CONFLICT(tenant_id,user_id,project_id,stage,scope_type,scope_id) DO UPDATE SET
                    plugin_key=excluded.plugin_key,lifecycle=excluded.lifecycle,stage_substate=excluded.stage_substate,
                    content_fingerprint=excluded.content_fingerprint,audit_batch_id=excluded.audit_batch_id,
                    confirmation_json=excluded.confirmation_json,progress_json=excluded.progress_json,
                    checkpoint=excluded.checkpoint,error=excluded.error,confirmation_scope_json=excluded.confirmation_scope_json,
                    impact_scope_json=excluded.impact_scope_json,updated_at=excluded.updated_at,
                    generation=excluded.generation,revision=excluded.revision,
                    production_evidence_json=excluded.production_evidence_json,audit_evidence_json=excluded.audit_evidence_json
            """, values)
            row = active.execute("SELECT * FROM production_scopes WHERE id=?", (record_id,)).fetchone()
            self._snapshot(active, row, "current")
            return self._record(row)

    def upsert_projection(self, payload: Mapping[str, Any], *, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Apply an untrusted UI projection without granting production authority."""
        tenant_id, user_id, project_id = self._identity(payload)
        stage, scope_type, scope_id = self._key(payload)
        if not _is_upscale_scope(stage, scope_type, scope_id):
            owns_connection = connection is None
            context = self._connection() if owns_connection else _existing_connection(connection)
            with self._lock, context as active:
                current = active.execute("""
                    SELECT * FROM production_scopes
                    WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
                """, (tenant_id, user_id, project_id, stage, scope_type, scope_id)).fetchone()
                projected = dict(payload)
                expected_revision = projected.pop("expected_revision", None)
                if expected_revision is not None:
                    expected_revision = _integer(expected_revision, "expected_revision")
                    if expected_revision != int(current["revision"] if current else 0):
                        raise ProductionLedgerError("production scope CAS conflict")
                for field in ("confirmation", "generation", "production_evidence", "audit_evidence"):
                    projected.pop(field, None)
                requested_lifecycle = _string(projected.get("lifecycle") or "idle", "lifecycle", allow_empty=False)
                if requested_lifecycle not in LIFECYCLES:
                    raise ProductionLedgerError(f"invalid lifecycle: {requested_lifecycle}")
                current_confirmation = json.loads(current["confirmation_json"]) if current and current["confirmation_json"] else None
                incoming_fingerprint = str(projected.get("content_fingerprint", current["content_fingerprint"] if current else ""))
                incoming_batch = str(projected.get("audit_batch_id", current["audit_batch_id"] if current else ""))
                same_confirmed_generation = bool(
                    current_confirmation
                    and incoming_fingerprint == str(current["content_fingerprint"])
                    and incoming_batch == str(current["audit_batch_id"])
                )
                if same_confirmed_generation:
                    projected["lifecycle"] = "completed"
                elif requested_lifecycle == "completed":
                    projected["lifecycle"] = "pending_confirmation"
                return self.upsert(projected, connection=active)
        owns_connection = connection is None
        context = self._connection() if owns_connection else _existing_connection(connection)
        with context as active:
            if owns_connection:
                active.execute("BEGIN IMMEDIATE")
            current = active.execute("""
                SELECT * FROM production_scopes
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
            """, (tenant_id, user_id, project_id, stage, scope_type, scope_id)).fetchone()
            expected_revision = payload.get("expected_revision")
            if expected_revision is not None:
                expected_revision = _integer(expected_revision, "expected_revision")
                if expected_revision != int(current["revision"] if current else 0):
                    raise ProductionLedgerError("production scope CAS conflict")
            incoming_progress = payload.get("progress")
            if incoming_progress is not None and not isinstance(incoming_progress, Mapping):
                raise ProductionLedgerError("progress must be an object")
            current_progress = json.loads(current["progress_json"]) if current else {"completed": 0, "total": 1}
            progress = {key: value for key, value in current_progress.items() if key not in UPSCALE_EVIDENCE_FIELDS}
            if isinstance(incoming_progress, Mapping):
                for name, value in incoming_progress.items():
                    if name not in UPSCALE_EVIDENCE_FIELDS and value is not None:
                        progress[name] = value
            created_at = current["created_at"] if current else _now()
            record_id = current["id"] if current else f"scope-{uuid4().hex}"
            current_revision = int(current["revision"] or 0) if current else 0
            has_authority = bool(current and int(current["generation"] or 0) > 0)
            confirmed = bool(current and current["confirmation_json"])
            requested_lifecycle = _string(payload.get("lifecycle") or "idle", "lifecycle", allow_empty=False)
            if requested_lifecycle not in LIFECYCLES:
                raise ProductionLedgerError(f"invalid lifecycle: {requested_lifecycle}")
            lifecycle = current["lifecycle"] if has_authority or confirmed else (
                "idle" if requested_lifecycle in {"pending_confirmation", "completed"} else requested_lifecycle
            )
            values = {
                "id": record_id, "tenant_id": tenant_id, "user_id": user_id, "project_id": project_id,
                "stage": stage, "scope_type": scope_type, "scope_id": scope_id,
                "plugin_key": current["plugin_key"] if current else "short_drama", "lifecycle": lifecycle,
                "stage_substate": str(payload.get("stage_substate", current["stage_substate"] if current else "upscale")),
                "content_fingerprint": current["content_fingerprint"] if current else "",
                "audit_batch_id": current["audit_batch_id"] if current else "",
                "confirmation_json": current["confirmation_json"] if current else None,
                "progress_json": _json(progress),
                "checkpoint": str(payload.get("checkpoint", current["checkpoint"] if current else "")),
                "error": str(payload.get("error", current["error"] if current else "")),
                "confirmation_scope_json": current["confirmation_scope_json"] if current else _json({"scope_type": scope_type, "scope_ids": [scope_id]}),
                "impact_scope_json": current["impact_scope_json"] if current else _json([]),
                "created_at": created_at, "updated_at": _now(),
                "generation": int(current["generation"] or 0) if current else 0,
                "revision": current_revision + 1,
                "production_evidence_json": current["production_evidence_json"] if current else None,
                "audit_evidence_json": current["audit_evidence_json"] if current else None,
            }
            if current:
                cursor = active.execute("""
                    UPDATE production_scopes SET lifecycle=:lifecycle,stage_substate=:stage_substate,
                        progress_json=:progress_json,checkpoint=:checkpoint,error=:error,updated_at=:updated_at,
                        revision=:revision WHERE id=:id AND revision=:current_revision
                """, {**values, "current_revision": current_revision})
                if cursor.rowcount != 1:
                    raise ProductionLedgerError("production scope CAS conflict")
            else:
                active.execute("""
                    INSERT INTO production_scopes (
                        id,tenant_id,user_id,project_id,stage,scope_type,scope_id,plugin_key,lifecycle,stage_substate,
                        content_fingerprint,audit_batch_id,confirmation_json,progress_json,checkpoint,error,
                        confirmation_scope_json,impact_scope_json,created_at,updated_at,generation,revision,
                        production_evidence_json,audit_evidence_json
                    ) VALUES (
                        :id,:tenant_id,:user_id,:project_id,:stage,:scope_type,:scope_id,:plugin_key,:lifecycle,:stage_substate,
                        :content_fingerprint,:audit_batch_id,:confirmation_json,:progress_json,:checkpoint,:error,
                        :confirmation_scope_json,:impact_scope_json,:created_at,:updated_at,:generation,:revision,
                        :production_evidence_json,:audit_evidence_json
                    )
                """, values)
            row = active.execute("SELECT * FROM production_scopes WHERE id=?", (record_id,)).fetchone()
            self._snapshot(active, row, "projection")
            return self._record(row)

    def upsert_many_projection(self, records: Iterable[Mapping[str, Any]], *, replace: bool = False) -> list[dict[str, Any]]:
        if not isinstance(replace,bool):raise ProductionLedgerError("replace must be boolean")
        records = list(records)
        if not records:
            return []
        identity = self._identity(records[0])
        if any(self._identity(item) != identity for item in records):
            raise ProductionLedgerError("bulk records must share one identity")
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if replace:
                keys = {(canonical_stage(item.get("stage")), str(item.get("scope_type")), str(item.get("scope_id"))) for item in records}
                rows = connection.execute("""
                    SELECT stage,scope_type,scope_id,generation,confirmation_json FROM production_scopes
                    WHERE tenant_id=? AND user_id=? AND project_id=?
                """, identity).fetchall()
                for row in rows:
                    key = (row["stage"], row["scope_type"], row["scope_id"])
                    if key not in keys and int(row["generation"] or 0) == 0 and not row["confirmation_json"]:
                        connection.execute("""
                            DELETE FROM production_scopes
                            WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
                        """, (*identity, *key))
            return [self.upsert_projection(item, connection=connection) for item in records]

    def upsert_many(self, records: Iterable[Mapping[str, Any]], *, replace: bool = False) -> list[dict[str, Any]]:
        if not isinstance(replace,bool):raise ProductionLedgerError("replace must be boolean")
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
            generation = int(row["generation"] or 0)
            if _is_upscale_scope(stage, scope_type, scope_id):
                if generation < 1 or not row["content_fingerprint"] or not row["audit_batch_id"]:
                    raise ProductionLedgerError("upscale scope has no authoritative generation")
                _nonempty_evidence(json.loads(row["production_evidence_json"]) if row["production_evidence_json"] else None, "production_evidence")
                _nonempty_evidence(json.loads(row["audit_evidence_json"]) if row["audit_evidence_json"] else None, "audit_evidence")
            confirmation = {
                "content_fingerprint": row["content_fingerprint"], "audit_batch_id": row["audit_batch_id"],
                "generation": generation, "confirmed_by": user_id, "confirmed_at": _now(),
            }
            current_revision = int(row["revision"] or 0)
            cursor = connection.execute("""
                UPDATE production_scopes SET lifecycle='completed',confirmation_json=?,error='',updated_at=?,revision=?
                WHERE id=? AND revision=? AND generation=?
            """, (_json(confirmation), _now(), current_revision + 1, row["id"], current_revision, generation))
            if cursor.rowcount != 1:
                raise ProductionLedgerError("production scope confirmation CAS conflict")
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
                        UPDATE production_scopes SET lifecycle='stale',confirmation_json=NULL,error=?,updated_at=?,revision=revision+1
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
                UPDATE production_scopes SET lifecycle='pending_confirmation',confirmation_json=NULL,error=?,updated_at=?,revision=revision+1
                WHERE tenant_id=? AND user_id=? AND project_id=? AND stage=? AND scope_type=? AND scope_id=?
            """, (str(payload.get("reason") or "人工撤回确认"), _now(), tenant_id, user_id, project_id, stage, scope_type, scope_id))
        return self.impact({**payload, "source": {"stage": stage, "scope_type": scope_type, "scope_id": scope_id}, "reason": payload.get("reason")}, mutate=True)

    def restore_pending_confirmation(self, payload: Mapping[str, Any], reason: str) -> dict[str, Any]:
        tenant_id, user_id, project_id = self._identity(payload); stage, scope_type, scope_id = self._key(payload)
        with self._lock, self._connection() as connection:
            connection.execute("""UPDATE production_scopes SET lifecycle='pending_confirmation',confirmation_json=NULL,error=?,updated_at=?,revision=revision+1
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
        progress = json.loads(row["progress_json"])
        production_evidence = json.loads(row["production_evidence_json"]) if row["production_evidence_json"] else None
        audit_evidence = json.loads(row["audit_evidence_json"]) if row["audit_evidence_json"] else None
        if not _is_upscale_scope(row["stage"], row["scope_type"], row["scope_id"]):
            production_evidence = progress.get("production_evidence", production_evidence)
            audit_evidence = progress.get("audit_evidence", audit_evidence)
        return {
            "id": row["id"], "tenant_id": row["tenant_id"], "user_id": row["user_id"], "project_id": row["project_id"],
            "stage": row["stage"], "scope_type": row["scope_type"], "scope_id": row["scope_id"], "plugin_key": row["plugin_key"],
            "lifecycle": row["lifecycle"], "stage_substate": row["stage_substate"], "content_fingerprint": row["content_fingerprint"],
            "audit_batch_id": row["audit_batch_id"], "confirmation": json.loads(row["confirmation_json"]) if row["confirmation_json"] else None,
            "progress": progress, "production_evidence": production_evidence, "audit_evidence": audit_evidence,
            "generation": int(row["generation"] or 0), "revision": int(row["revision"] or 0),
            "checkpoint": row["checkpoint"], "error": row["error"],
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
