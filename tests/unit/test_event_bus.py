from __future__ import annotations

import unittest

from ai_agent_events import EventBus, EventBusError, PublishedEvent
from ai_agent_tenant import IdentityContext


def identity_context() -> IdentityContext:
    return IdentityContext("request-1", "trace-1", "identity-1", "user", "tenant-default")


class EventBusTest(unittest.TestCase):
    def test_subscriber_receives_scoped_event(self) -> None:
        bus = EventBus()
        received: list[PublishedEvent] = []
        bus.subscribe("TASK_STATUS_CHANGED", received.append)
        event = PublishedEvent(
            event_id="event-1",
            event_type="TASK_STATUS_CHANGED",
            project_id="project-1",
            context=identity_context(),
            payload={"task_id": "task-1", "current_status": "running"},
        )
        self.assertEqual(bus.publish(event), 1)
        self.assertEqual(received, [event])
        self.assertEqual(received[0].context.tenant_id, "tenant-default")

    def test_unsubscribe_stops_delivery(self) -> None:
        bus = EventBus()
        received: list[PublishedEvent] = []
        unsubscribe = bus.subscribe("PROJECT_CREATED", received.append)
        unsubscribe()
        event = PublishedEvent(
            "event-1", "PROJECT_CREATED", "project-1", identity_context(), {"project_id": "project-1"}
        )
        self.assertEqual(bus.publish(event), 0)
        self.assertEqual(received, [])

    def test_unknown_event_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(EventBusError, "not supported"):
            PublishedEvent("event-1", "UNKNOWN", "project-1", identity_context(), {"id": "1"})

    def test_empty_payload_is_rejected(self) -> None:
        with self.assertRaisesRegex(EventBusError, "payload"):
            PublishedEvent("event-1", "PROJECT_CREATED", "project-1", identity_context(), {})


if __name__ == "__main__":
    unittest.main()
