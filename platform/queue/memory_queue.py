"""Deterministic in-memory queue used by the platform runtime baseline."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from threading import Lock
from types import MappingProxyType
from typing import Any, Literal, Mapping

from ai_agent_tenant import IdentityContext, IdentityContextError


TaskStatus = Literal["queued", "running", "waiting_human", "paused", "completed", "failed", "cancelled"]
TERMINAL_STATUSES = frozenset({"completed", "cancelled"})
STATUS_TRANSITIONS = frozenset({
    ("queued", "running"), ("queued", "cancelled"), ("running", "waiting_human"),
    ("running", "paused"), ("running", "completed"), ("running", "failed"),
    ("running", "cancelled"), ("waiting_human", "running"), ("waiting_human", "cancelled"),
    ("paused", "queued"), ("paused", "cancelled"), ("failed", "queued"), ("failed", "cancelled"),
})


class QueueConflictError(ValueError):
    """Raised when idempotency or lifecycle rules are violated."""


@dataclass(frozen=True, slots=True)
class QueuedTask:
    task_id: str
    project_id: str
    operation_key: str
    task_type: str
    context: IdentityContext
    payload: Mapping[str, Any]
    status: TaskStatus = "queued"

    def __post_init__(self) -> None:
        for field_name in ("task_id", "project_id", "operation_key", "task_type"):
            if not getattr(self, field_name).strip():
                raise QueueConflictError(f"{field_name} must not be empty")
        if self._contains_sensitive_key(self.payload):
            raise QueueConflictError("task payload contains sensitive fields")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    @staticmethod
    def _contains_sensitive_key(value: Any) -> bool:
        forbidden = ("secret", "token", "password", "api_key", "authorization", "credential")
        if isinstance(value, Mapping):
            return any(any(word in str(key).lower() for word in forbidden) or QueuedTask._contains_sensitive_key(item) for key, item in value.items())
        if isinstance(value, (list, tuple, set, frozenset)): return any(QueuedTask._contains_sensitive_key(item) for item in value)
        return False


class InMemoryTaskQueue:
    def __init__(self) -> None:
        self._lock = Lock()
        self._pending: deque[str] = deque()
        self._tasks: dict[str, QueuedTask] = {}
        self._operation_keys: dict[tuple[str, str, str, str], str] = {}

    def enqueue(self, task: QueuedTask) -> tuple[QueuedTask, bool]:
        scope_key = (
            task.context.tenant_id, task.context.identity_id, task.project_id, task.operation_key
        )
        with self._lock:
            existing_id = self._operation_keys.get(scope_key)
            if existing_id is not None:
                existing = self._tasks[existing_id]
                if self._same_request(existing, task):
                    return existing, True
                raise QueueConflictError("operation_key conflicts with an existing request")
            if task.task_id in self._tasks:
                raise QueueConflictError("task_id already exists")
            self._tasks[task.task_id] = task
            self._operation_keys[scope_key] = task.task_id
            self._pending.append(task.task_id)
            return task, False

    def claim(self, tenant_id: str, identity_id: str | None = None) -> QueuedTask | None:
        tenant_id = self._required_scope("tenant_id", tenant_id)
        identity_id = self._optional_scope("identity_id", identity_id)
        with self._lock:
            for _ in range(len(self._pending)):
                task_id = self._pending.popleft()
                task = self._tasks[task_id]
                if task.context.tenant_id != tenant_id:
                    self._pending.append(task_id)
                    continue
                if identity_id is not None and task.context.identity_id != identity_id.strip():
                    self._pending.append(task_id)
                    continue
                claimed = replace(task, status="running")
                self._tasks[task_id] = claimed
                return claimed
            return None

    def finish(self, task_id: str, status: Literal["completed", "failed"]) -> QueuedTask:
        task_id = self._required_scope("task_id", task_id)
        if status not in {"completed", "failed"}:
            raise QueueConflictError("finish status must be completed or failed")
        with self._lock:
            task = self._require(task_id)
            if task.status != "running":
                raise QueueConflictError("only running tasks can finish")
            finished = replace(task, status=status)
            self._tasks[task_id] = finished
            return finished

    def cancel(self, task_id: str) -> QueuedTask:
        task_id = self._required_scope("task_id", task_id)
        with self._lock:
            task = self._require(task_id)
            if task.status in TERMINAL_STATUSES:
                raise QueueConflictError("terminal task cannot be cancelled")
            cancelled = replace(task, status="cancelled")
            self._tasks[task_id] = cancelled
            if task_id in self._pending:
                self._pending.remove(task_id)
            return cancelled

    def pause(self, task_id: str) -> QueuedTask:
        task_id = self._required_scope("task_id", task_id)
        with self._lock:
            task = self._require(task_id)
            if task.status != "running":
                raise QueueConflictError("only running tasks can pause")
            paused = replace(task, status="paused")
            self._tasks[task_id] = paused
            return paused

    def wait_for_human(self, task_id: str) -> QueuedTask:
        task_id = self._required_scope("task_id", task_id)
        with self._lock:
            task = self._require(task_id)
            if task.status != "running":
                raise QueueConflictError("only running tasks can wait for human")
            waiting = replace(task, status="waiting_human")
            self._tasks[task_id] = waiting
            return waiting

    def resume(self, task_id: str) -> QueuedTask:
        task_id = self._required_scope("task_id", task_id)
        with self._lock:
            task = self._require(task_id)
            if task.status not in {"paused", "failed"}:
                raise QueueConflictError("only paused or failed tasks can return to queue")
            queued = replace(task, status="queued")
            self._tasks[task_id] = queued
            self._pending.append(task_id)
            return queued

    def resume_human(self, task_id: str) -> QueuedTask:
        task_id = self._required_scope("task_id", task_id)
        with self._lock:
            task = self._require(task_id)
            if task.status != "waiting_human":
                raise QueueConflictError("only waiting_human tasks can resume running")
            running = replace(task, status="running")
            self._tasks[task_id] = running
            return running

    def get(self, task_id: str, tenant_id: str, identity_id: str | None = None) -> QueuedTask:
        task_id = self._required_scope("task_id", task_id)
        tenant_id = self._required_scope("tenant_id", tenant_id)
        identity_id = self._optional_scope("identity_id", identity_id)
        with self._lock:
            task = self._require(task_id)
            task.context.require_tenant(tenant_id)
            if identity_id is not None and task.context.identity_id != identity_id.strip():
                raise IdentityContextError("identity scope mismatch")
            return task

    def list(self, tenant_id: str, project_id: str | None = None, identity_id: str | None = None) -> tuple[QueuedTask, ...]:
        tenant_id = self._required_scope("tenant_id", tenant_id)
        project_id = self._optional_scope("project_id", project_id)
        identity_id = self._optional_scope("identity_id", identity_id)
        with self._lock:
            return tuple(task for task in self._tasks.values() if task.context.tenant_id == tenant_id
                         and (identity_id is None or task.context.identity_id == identity_id.strip())
                         and (project_id is None or task.project_id == project_id))

    def apply_status_event(self, task_id: str, tenant_id: str, identity_id: str, project_id: str, status: TaskStatus, progress_percent: int) -> QueuedTask:
        task_id = self._required_scope("task_id", task_id)
        tenant_id = self._required_scope("tenant_id", tenant_id)
        identity_id = self._required_scope("identity_id", identity_id)
        project_id = self._required_scope("project_id", project_id)
        if status not in {"queued", "running", "waiting_human", "paused", "completed", "failed", "cancelled"}:
            raise QueueConflictError("task status is invalid")
        with self._lock:
            task = self._require(task_id)
            task.context.require_tenant(tenant_id)
            if task.context.identity_id != identity_id.strip():
                raise IdentityContextError("identity scope mismatch")
            if task.project_id != project_id:
                raise QueueConflictError("project scope mismatch")
            if task.status != status and (task.status, status) not in STATUS_TRANSITIONS:
                raise QueueConflictError("task status event transition is forbidden")
            if not 0 <= progress_percent <= 100:
                raise QueueConflictError("progress_percent is invalid")
            updated = replace(task, status=status, payload={**dict(task.payload), "progress_percent": progress_percent})
            self._tasks[task_id] = updated
            return updated

    def _require(self, task_id: str) -> QueuedTask:
        try:
            return self._tasks[task_id]
        except KeyError as error:
            raise QueueConflictError("task does not exist") from error

    @staticmethod
    def _required_scope(field_name: str, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise QueueConflictError(f"{field_name} must not be empty")
        return normalized

    @classmethod
    def _optional_scope(cls, field_name: str, value: str | None) -> str | None:
        return None if value is None else cls._required_scope(field_name, value)

    @staticmethod
    def _same_request(existing: QueuedTask, incoming: QueuedTask) -> bool:
        return (
            existing.project_id == incoming.project_id
            and existing.task_type == incoming.task_type
            and dict(existing.payload) == dict(incoming.payload)
        )
