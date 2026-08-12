"""Tenant- and project-scoped task query and lifecycle service."""

from __future__ import annotations

from ai_agent_events import EventBus, PublishedEvent
from ai_agent_tenant import IdentityContext

from .memory_queue import InMemoryTaskQueue, QueueConflictError, QueuedTask


class TaskService:
    def __init__(self, queue: InMemoryTaskQueue, events: EventBus | None = None) -> None:
        if not isinstance(queue,InMemoryTaskQueue):raise QueueConflictError("task queue contract is invalid")
        if events is not None and not isinstance(events,EventBus):raise QueueConflictError("event bus contract is invalid")
        self.queue = queue
        self._unsubscribe = events.subscribe("TASK_STATUS_CHANGED", self._apply_event) if events else None

    def _apply_event(self, event: PublishedEvent) -> None:
        if not isinstance(event,PublishedEvent):raise QueueConflictError("task event contract is invalid")
        payload = event.payload
        self.queue.apply_status_event(
            payload.get("task_id", ""), event.context.tenant_id, event.context.identity_id, event.project_id,
            payload.get("current_status", ""), payload.get("progress_percent", -1),  # type: ignore[arg-type]
        )

    def list_tasks(self, context: IdentityContext, project_id: str | None = None) -> tuple[QueuedTask, ...]:
        self._context(context)
        return self.queue.list(context.tenant_id, project_id, context.identity_id)

    def get_task(self, context: IdentityContext, task_id: str) -> QueuedTask:
        self._context(context)
        return self.queue.get(task_id, context.tenant_id, context.identity_id)

    def cancel_task(self, context: IdentityContext, task_id: str) -> QueuedTask:
        self.get_task(context, task_id)
        return self.queue.cancel(task_id)

    def resume_task(self, context: IdentityContext, task_id: str) -> QueuedTask:
        self.get_task(context, task_id)
        return self.queue.resume(task_id)

    @staticmethod
    def _context(context: IdentityContext) -> None:
        if not isinstance(context,IdentityContext):raise QueueConflictError("identity context is required")
