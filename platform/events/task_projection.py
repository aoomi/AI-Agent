"""Real-time task status projection derived from task events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from threading import RLock

from ai_agent_tenant import IdentityContext

from .bus import EventBus, PublishedEvent


class TaskProjectionError(ValueError): pass


@dataclass(frozen=True, slots=True)
class TaskProgress:
    task_id: str
    tenant_id: str
    identity_id: str
    project_id: str
    status: str
    progress_percent: int


class TaskProgressProjection:
    def __init__(self, events: EventBus) -> None:
        if not callable(getattr(events,"subscribe",None)):raise TaskProjectionError("event bus contract is invalid")
        self._items: dict[tuple[str, str, str], TaskProgress] = {}
        self._lock = RLock()
        self._unsubscribe = events.subscribe("TASK_STATUS_CHANGED", self._apply)

    def close(self) -> None: self._unsubscribe()

    def _apply(self, event: PublishedEvent) -> None:
        if not isinstance(event,PublishedEvent):raise TaskProjectionError("task event is invalid")
        payload: dict[str, Any] = dict(event.payload)
        task_id, status, progress = payload.get("task_id"), payload.get("current_status"), payload.get("progress_percent")
        if not isinstance(task_id, str) or not task_id.strip() or not isinstance(status, str) or not status.strip():
            raise TaskProjectionError("task event payload is incomplete")
        if isinstance(progress, bool) or not isinstance(progress, int) or not 0 <= progress <= 100:
            raise TaskProjectionError("progress_percent must be between 0 and 100")
        key = (event.context.tenant_id, event.context.identity_id, event.project_id, task_id)
        with self._lock:self._items[key] = TaskProgress(task_id, event.context.tenant_id, event.context.identity_id, event.project_id, status, progress)

    def get(self, context: IdentityContext, project_id: str, task_id: str) -> TaskProgress:
        if not isinstance(context,IdentityContext) or not isinstance(project_id,str) or not isinstance(task_id,str):raise TaskProjectionError("project_id and task_id are required")
        project_id,task_id=project_id.strip(),task_id.strip()
        if not project_id or not task_id:raise TaskProjectionError("project_id and task_id are required")
        with self._lock:
            try: return self._items[(context.tenant_id, context.identity_id, project_id, task_id)]
            except KeyError as error: raise TaskProjectionError("task progress does not exist in this scope") from error

    def list(self, context: IdentityContext, project_id: str | None = None) -> tuple[TaskProgress, ...]:
        if not isinstance(context,IdentityContext):raise TaskProjectionError("identity context is required")
        if project_id is not None:
            if not isinstance(project_id,str):raise TaskProjectionError("project_id is required")
            project_id=project_id.strip()
            if not project_id:raise TaskProjectionError("project_id is required")
        with self._lock:return tuple(item for item in self._items.values() if item.tenant_id == context.tenant_id
                     and item.identity_id == context.identity_id and (project_id is None or item.project_id == project_id))
