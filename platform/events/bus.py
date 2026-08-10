"""Synchronous in-process event bus for the runnable platform baseline."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from ai_agent_tenant import IdentityContext


EVENT_TYPES = frozenset(
    {
        "PROJECT_CREATED",
        "TASK_STATUS_CHANGED",
        "PLUGIN_STATUS_CHANGED",
        "ASSET_STATUS_CHANGED",
    }
)


class EventBusError(ValueError):
    """Raised when an event violates the public event envelope."""


@dataclass(frozen=True, slots=True)
class PublishedEvent:
    event_id: str
    event_type: str
    project_id: str
    context: IdentityContext
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise EventBusError("event_id must not be empty")
        if self.event_type not in EVENT_TYPES:
            raise EventBusError("event_type is not supported")
        if not self.project_id.strip():
            raise EventBusError("project_id must not be empty")
        if not self.payload:
            raise EventBusError("payload must not be empty")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


EventHandler = Callable[[PublishedEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> Callable[[], None]:
        if event_type not in EVENT_TYPES:
            raise EventBusError("event_type is not supported")
        self._subscribers[event_type].append(handler)

        def unsubscribe() -> None:
            handlers = self._subscribers[event_type]
            if handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    def publish(self, event: PublishedEvent) -> int:
        handlers = tuple(self._subscribers.get(event.event_type, ()))
        for handler in handlers:
            handler(event)
        return len(handlers)
