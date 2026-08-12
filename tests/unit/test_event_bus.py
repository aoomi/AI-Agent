from __future__ import annotations

import unittest

from ai_agent_events import EventBus, EventBusError, PublishedEvent
from ai_agent_tenant import IdentityContext


def identity_context() -> IdentityContext:
    return IdentityContext("request-1", "trace-1", "identity-1", "user", "tenant-default")


class EventBusTest(unittest.TestCase):
    def test_runtime_event_shapes_are_rejected(self) -> None:
        with self.assertRaises(EventBusError):PublishedEvent("event","PROJECT_CREATED","project",object(),{"x":1})
        with self.assertRaises(EventBusError):EventBus().publish(object())
        for values in ((1,"PROJECT_CREATED","project"),("event",1,"project"),("event","PROJECT_CREATED",1)):
            with self.subTest(values=values),self.assertRaises(EventBusError):PublishedEvent(*values,identity_context(),{"x":1})
        with self.assertRaises(EventBusError):EventBus().subscribe(1,lambda _event:None)
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
        with self.assertRaisesRegex(EventBusError, "callable"):
            EventBus().subscribe("PROJECT_CREATED", None)  # type: ignore[arg-type]

    def test_empty_payload_is_rejected(self) -> None:
        with self.assertRaisesRegex(EventBusError, "payload"):
            PublishedEvent("event-1", "PROJECT_CREATED", "project-1", identity_context(), {})

    def test_sensitive_event_payload_is_rejected_recursively(self) -> None:
        for payload in (
            {"access_token":"plaintext"},
            {"transport":{"headers":{"Authorization":"Bearer plaintext"}}},
            {"profiles":[{"client_secret":"plaintext"}]},
        ):
            with self.subTest(payload=payload), self.assertRaisesRegex(EventBusError, "sensitive fields"):
                PublishedEvent("event-1", "PROJECT_CREATED", "project-1", identity_context(), payload)

    def test_event_payload_requires_standard_json(self) -> None:
        for payload in ({"value":float("nan")},{"value":object()}):
            with self.subTest(payload=payload),self.assertRaisesRegex(EventBusError,"standard JSON"):
                PublishedEvent("event-1","PROJECT_CREATED","project-1",identity_context(),payload)

    def test_event_payload_is_deeply_immutable_from_caller_mutation(self) -> None:
        nested = {"items": [{"status": "queued"}]}
        event = PublishedEvent("event-1", "PROJECT_CREATED", "project-1", identity_context(), nested)
        nested["items"][0]["status"] = "forged"
        self.assertEqual(event.payload["items"][0]["status"], "queued")


if __name__ == "__main__":
    unittest.main()
