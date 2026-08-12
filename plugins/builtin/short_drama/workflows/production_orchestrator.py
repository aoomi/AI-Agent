"""Durable LangGraph control plane for short-drama production."""

from __future__ import annotations

from datetime import UTC, datetime
import operator
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from threading import RLock
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Mapping, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .production_ledger import CANONICAL_STAGES, LIFECYCLES, canonical_stage


Director = Callable[[Mapping[str, Any]], Mapping[str, Any]]
StageExecutor = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class TransactionalSqliteSaver(SqliteSaver):
    """Let an authority commit lend its SQLite transaction to LangGraph."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)
        self._external_connection: sqlite3.Connection | None = None

    @contextmanager
    def use_connection(self, connection: sqlite3.Connection):
        if self._external_connection is not None:
            raise RuntimeError("nested LangGraph authority transactions are not supported")
        self._external_connection = connection
        try:
            yield
        finally:
            self._external_connection = None

    @contextmanager
    def cursor(self, transaction: bool = True):
        external = self._external_connection
        if external is None:
            with super().cursor(transaction=transaction) as cursor:
                yield cursor
            return
        with self.lock:
            self.setup()
            cursor = external.cursor()
            try:
                yield cursor
            finally:
                cursor.close()


@dataclass(frozen=True, slots=True)
class StageDefinition:
    stage: str
    provider_id: str
    enabled: bool


class ProductionControlState(TypedDict, total=False):
    tenant_id: str
    user_id: str
    project_id: str
    event: dict[str, Any]
    accepted_event: dict[str, Any]
    stage_events: Annotated[dict[str, dict[str, Any]], operator.or_]
    stages: Annotated[dict[str, str], operator.or_]
    projection_revisions: Annotated[dict[str, int], operator.or_]
    stage_generations: Annotated[dict[str, int], operator.or_]
    current_stage: str
    next_stage: str
    status: str
    decision: dict[str, Any]
    updated_at: str


class ProductionOrchestrator:
    """Authoritative state transition planner backed by LangGraph checkpoints."""

    def __init__(self, database: Path, director: Director | None = None) -> None:
        self.database = database.resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database, check_same_thread=False)
        self.checkpointer = TransactionalSqliteSaver(self.connection)
        self.checkpointer.setup()
        self.director = director
        self._executors: dict[str, tuple[StageDefinition, StageExecutor]] = {}
        self._executor_inflight: dict[str, int] = {}
        self._lock = RLock()
        self.graph = self._compile()

    @contextmanager
    def authority_transaction(self, connection: sqlite3.Connection):
        """Route all checkpoint writes to the caller's uncommitted connection."""
        with self._lock, self.checkpointer.use_connection(connection):
            yield

    def import_legacy_checkpoints(self, source: Path) -> int:
        """Idempotently copy checkpoints from the former split database."""
        source = source.resolve()
        if source == self.database or not source.is_file():
            return 0
        with self._lock:
            self.checkpointer.setup()
            before = int(self.connection.execute("SELECT count(*) FROM checkpoints").fetchone()[0])
            escaped = str(source).replace("'", "''")
            self.connection.execute(f"ATTACH DATABASE '{escaped}' AS legacy_graph")
            try:
                tables = {str(row[0]) for row in self.connection.execute(
                    "SELECT name FROM legacy_graph.sqlite_master WHERE type='table'"
                )}
                if {"checkpoints", "writes"}.issubset(tables):
                    self.connection.execute("INSERT OR IGNORE INTO checkpoints SELECT * FROM legacy_graph.checkpoints")
                    self.connection.execute("INSERT OR IGNORE INTO writes SELECT * FROM legacy_graph.writes")
                self.connection.commit()
            finally:
                self.connection.execute("DETACH DATABASE legacy_graph")
            after = int(self.connection.execute("SELECT count(*) FROM checkpoints").fetchone()[0])
            return after - before

    def register_stage(self, stage: str, executor: StageExecutor, *, provider_id: str = "local", enabled: bool = True, replace: bool = False) -> None:
        canonical = canonical_stage(stage)
        provider = provider_id.strip()
        if not callable(executor) or not provider:
            raise ValueError("stage executor and provider are required")
        with self._lock:
            if replace and self._executor_inflight.get(canonical, 0):
                raise ValueError(f"stage executor has in-flight invocations: {canonical}")
            if canonical in self._executors and not replace:
                raise ValueError(f"stage executor already registered: {canonical}")
            self._executors[canonical] = (StageDefinition(canonical, provider, enabled), executor)

    def unregister_stage(self, stage: str) -> bool:
        canonical = canonical_stage(stage)
        with self._lock:
            if self._executor_inflight.get(canonical, 0):
                raise ValueError(f"stage executor has in-flight invocations: {canonical}")
            return self._executors.pop(canonical, None) is not None

    def enable_stage(self, stage: str, enabled: bool) -> StageDefinition:
        canonical = canonical_stage(stage)
        with self._lock:
            try:
                definition, executor = self._executors[canonical]
            except KeyError as error:
                raise ValueError(f"stage executor is not installed: {canonical}") from error
            if not enabled and self._executor_inflight.get(canonical, 0):
                raise ValueError(f"stage executor has in-flight invocations: {canonical}")
            updated = StageDefinition(canonical, definition.provider_id, enabled)
            self._executors[canonical] = (updated, executor)
            return updated

    def stages(self) -> tuple[StageDefinition, ...]:
        with self._lock:
            return tuple(self._executors[stage][0] for stage in CANONICAL_STAGES if stage in self._executors)

    def execute(self, identity: Mapping[str, Any], stage: str, inputs: Mapping[str, Any]) -> dict[str, Any]:
        """Execute one registered production node under the durable LangGraph state machine."""
        canonical = canonical_stage(stage)
        state = self.state(identity)
        if state.get("status") == "cancelled":
            raise ValueError("workflow is cancelled")
        index = CANONICAL_STAGES.index(canonical)
        if index and state["stages"].get(CANONICAL_STAGES[index - 1]) != "completed":
            raise ValueError(f"previous stage is not completed: {CANONICAL_STAGES[index - 1]}")
        with self._lock:
            try:
                definition, executor = self._executors[canonical]
            except KeyError as error:
                raise ValueError(f"stage executor is not installed: {canonical}") from error
            if not definition.enabled:
                raise ValueError(f"stage executor is disabled: {canonical}")
            self._executor_inflight[canonical] = self._executor_inflight.get(canonical, 0) + 1
        self.report(identity, canonical, "running")
        try:
            try:
                output = executor(dict(inputs))
            except ConnectionError:
                output = executor(dict(inputs))
            if not isinstance(output, Mapping):
                raise ValueError("stage executor returned invalid output")
        except Exception as error:
            failed = self.report(identity, canonical, "failed", error=str(error))
            return {**failed, "output": None, "error": str(error)}
        finally:
            with self._lock:
                remaining = self._executor_inflight.get(canonical, 1) - 1
                if remaining:
                    self._executor_inflight[canonical] = remaining
                else:
                    self._executor_inflight.pop(canonical, None)
        waiting = self.report(identity, canonical, "pending_confirmation", evidence=dict(output))
        return {**waiting, "output": dict(output), "error": ""}

    def begin(self, identity: Mapping[str, Any], stage: str, *, stage_generation: int = 0) -> dict[str, Any]:
        """Authorize a legacy endpoint through the same dependency gate."""
        canonical = canonical_stage(stage)
        state = self.state(identity)
        if state.get("status") == "cancelled":
            current_generation = int(state.get("stage_generations", {}).get(canonical) or 0)
            if stage_generation <= current_generation:
                raise ValueError("cancelled workflow requires a newer stage generation")
        if state.get("stages", {}).get(canonical) == "running":
            raise ValueError(f"production stage is already running: {canonical}")
        index = CANONICAL_STAGES.index(canonical)
        if index and state["stages"].get(CANONICAL_STAGES[index - 1]) != "completed":
            raise ValueError(f"previous stage is not completed: {CANONICAL_STAGES[index - 1]}")
        return self.report(identity, canonical, "running", stage_generation=stage_generation)

    def _compile(self):
        builder = StateGraph(ProductionControlState)

        def apply_event(state: ProductionControlState) -> dict[str, Any]:
            event = dict(state.get("event") or {})
            stage = canonical_stage(event.get("stage"))
            lifecycle = str(event.get("lifecycle") or "idle")
            if lifecycle not in LIFECYCLES:
                raise ValueError(f"invalid production lifecycle: {lifecycle}")
            incoming_revision = max(0, int(event.get("projection_revision") or 0))
            current_revision = int((state.get("projection_revisions") or {}).get(stage) or 0)
            incoming_generation = max(0, int(event.get("stage_generation") or 0))
            current_generation = int((state.get("stage_generations") or {}).get(stage) or 0)

            def reject() -> dict[str, Any]:
                return {
                    "event": dict(state.get("accepted_event") or {}),
                    "updated_at": datetime.now(UTC).isoformat(),
                }

            # A generation is the owner fence.  Revisions are only comparable
            # inside that generation: a newly leased owner restarts its local
            # projection sequence and must not be rejected by the old owner's
            # numerically larger revision.
            if current_generation and incoming_generation < current_generation:
                return reject()
            same_generation = incoming_generation == current_generation
            stage_events = state.get("stage_events") or {}
            has_accepted_stage_event = isinstance(stage_events.get(stage), Mapping)
            if (
                same_generation
                and has_accepted_stage_event
                and (current_generation > 0 or current_revision > 0)
                and incoming_revision <= current_revision
            ):
                return reject()
            return {
                "event": event, "accepted_event": event, "stage_events": {stage:event},
                "stages": {stage: lifecycle}, "current_stage": stage,
                "projection_revisions": {stage:incoming_revision}
                    if incoming_revision or incoming_generation > current_generation else {},
                "stage_generations": {stage:incoming_generation} if incoming_generation else {},
                "updated_at": datetime.now(UTC).isoformat(),
            }

        def plan(state: ProductionControlState) -> dict[str, Any]:
            stages = dict(state.get("stages") or {})
            current = canonical_stage(state.get("current_stage"))
            lifecycle = stages.get(current, "idle")
            decision: dict[str, Any] = {"action": "wait", "stage": current, "reason": lifecycle}
            next_stage = ""
            status = "running"
            if lifecycle == "completed":
                index = CANONICAL_STAGES.index(current)
                if index == len(CANONICAL_STAGES) - 1:
                    status = "completed"; decision = {"action": "complete", "stage": current, "reason": "workflow_complete"}
                else:
                    next_stage = CANONICAL_STAGES[index + 1]
                    decision = {"action": "advance", "stage": next_stage, "reason": f"{current}_completed"}
            elif lifecycle == "pending_confirmation":
                status = "waiting_human"; decision = {"action": "human_approval", "stage": current, "reason": "confirmation_required"}
            elif lifecycle in {"failed", "stale"}:
                status = "failed"; decision = {"action": "repair", "stage": current, "reason": lifecycle}
                if self.director is not None:
                    raw = self.director({"role": "short_drama_global_director", "current_stage": current, "lifecycle": lifecycle, "stages": stages, "event": state.get("event", {})})
                    if isinstance(raw, Mapping) and raw.get("action") in {"repair", "manual", "cancel"}:
                        decision = {"action": str(raw["action"]), "stage": canonical_stage(raw.get("stage") or current), "reason": str(raw.get("reason") or lifecycle)}
            elif lifecycle in {"paused", "cancelled"}:
                status = lifecycle; decision = {"action": lifecycle, "stage": current, "reason": lifecycle}
            return {"next_stage": next_stage, "status": status, "decision": decision, "updated_at": datetime.now(UTC).isoformat()}

        builder.add_node("apply_event", apply_event)
        builder.add_node("global_director", plan)
        builder.add_edge(START, "apply_event")
        builder.add_edge("apply_event", "global_director")
        builder.add_edge("global_director", END)
        return builder.compile(checkpointer=self.checkpointer)

    @staticmethod
    def thread_id(tenant_id: str, user_id: str, project_id: str) -> str:
        values = tuple(str(value).strip() for value in (tenant_id, user_id, project_id))
        if not all(values):
            raise ValueError("tenant_id, user_id and project_id are required")
        return ":".join(values)

    def report(self, identity: Mapping[str, Any], stage: str, lifecycle: str, *, trusted: bool = False, **evidence: Any) -> dict[str, Any]:
        tenant_id, user_id, project_id = (str(identity.get(key, "")).strip() for key in ("tenant_id", "user_id", "project_id"))
        thread_id = self.thread_id(tenant_id, user_id, project_id)
        canonical = canonical_stage(stage)
        if lifecycle == "completed":
            self.validate_completion(identity, canonical, trusted=trusted, confirmation=evidence.get("confirmation"))
        event = {"stage": canonical, "lifecycle": lifecycle, **evidence}
        config = {"configurable": {"thread_id": thread_id}}
        with self._lock:
            result = self.graph.invoke({"tenant_id": tenant_id, "user_id": user_id, "project_id": project_id, "event": event}, config=config)
        return self._public(result, thread_id)

    def validate_completion(self, identity: Mapping[str, Any], stage: str, *, trusted: bool = False, confirmation: Any = None) -> None:
        canonical = canonical_stage(stage); current = self.state(identity); index = CANONICAL_STAGES.index(canonical)
        if index and current["stages"].get(CANONICAL_STAGES[index - 1]) != "completed":
            raise ValueError(f"previous stage is not completed: {CANONICAL_STAGES[index - 1]}")
        if not trusted and not (isinstance(confirmation, Mapping) and confirmation.get("confirmed_at")):
            raise ValueError(f"completed stage requires durable confirmation: {canonical}")

    def state(self, identity: Mapping[str, Any]) -> dict[str, Any]:
        tenant_id, user_id, project_id = (str(identity.get(key, "")).strip() for key in ("tenant_id", "user_id", "project_id"))
        thread_id = self.thread_id(tenant_id, user_id, project_id)
        with self._lock:
            snapshot = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        return self._public(snapshot.values or {}, thread_id)

    @staticmethod
    def _public(state: Mapping[str, Any], thread_id: str) -> dict[str, Any]:
        return {
            "thread_id": thread_id,
            "status": str(state.get("status") or "idle"),
            "current_stage": str(state.get("current_stage") or ""),
            "next_stage": str(state.get("next_stage") or ""),
            "stages": dict(state.get("stages") or {}),
            "decision": dict(state.get("decision") or {}),
            "event": dict(state.get("event") or {}),
            "stage_events": {
                str(key):dict(value)
                for key, value in dict(state.get("stage_events") or {}).items()
                if isinstance(value, Mapping)
            },
            "projection_revisions": {str(key):int(value) for key, value in dict(state.get("projection_revisions") or {}).items()},
            "stage_generations": {str(key):int(value) for key, value in dict(state.get("stage_generations") or {}).items()},
            "updated_at": str(state.get("updated_at") or ""),
            "orchestrator": "langgraph",
            "director_model": "mlx-community/Qwen3.5-122B-A10B-mxfp4",
        }
