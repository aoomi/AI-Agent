"""Synchronous in-process event bus for the runnable platform baseline."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from threading import RLock
from typing import Any
import json

from ai_agent_tenant import IdentityContext


EVENT_TYPES = frozenset(
    {
        "PROJECT_CREATED",
        "TASK_STATUS_CHANGED",
        "PLUGIN_STATUS_CHANGED",
        "ASSET_STATUS_CHANGED",
    }
)
_SENSITIVE_KEY_PARTS = ("secret", "token", "password", "api_key", "authorization", "credential")


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(any(word in str(key).lower() for word in _SENSITIVE_KEY_PARTS) or _contains_sensitive_key(item) for key, item in value.items())
    if isinstance(value, (list, tuple, set, frozenset)): return any(_contains_sensitive_key(item) for item in value)
    return False


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
        if not isinstance(self.event_id,str) or not self.event_id.strip():
            raise EventBusError("event_id must not be empty")
        if not isinstance(self.event_type,str) or self.event_type not in EVENT_TYPES:
            raise EventBusError("event_type is not supported")
        if not isinstance(self.project_id,str) or not self.project_id.strip():
            raise EventBusError("project_id must not be empty")
        if not isinstance(self.context,IdentityContext):raise EventBusError("event context is invalid")
        if not isinstance(self.payload,Mapping) or not self.payload:
            raise EventBusError("payload must not be empty")
        if _contains_sensitive_key(self.payload):
            raise EventBusError("event payload contains sensitive fields")
        try:json.dumps(dict(self.payload),allow_nan=False)
        except (TypeError,ValueError) as error:raise EventBusError("event payload must be standard JSON") from error
        object.__setattr__(self,"event_id",self.event_id.strip())
        object.__setattr__(self,"project_id",self.project_id.strip())
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


EventHandler = Callable[[PublishedEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_type: str, handler: EventHandler) -> Callable[[], None]:
        if not isinstance(event_type,str) or event_type not in EVENT_TYPES:
            raise EventBusError("event_type is not supported")
        if not callable(handler):
            raise EventBusError("event handler must be callable")
        with self._lock: self._subscribers[event_type].append(handler)

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._subscribers[event_type]
                if handler in handlers: handlers.remove(handler)

        return unsubscribe

    def publish(self, event: PublishedEvent) -> int:
        if not isinstance(event,PublishedEvent):raise EventBusError("published event is invalid")
        with self._lock: handlers = tuple(self._subscribers.get(event.event_type, ()))
        for handler in handlers:
            handler(event)
        return len(handlers)
