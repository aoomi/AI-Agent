from __future__ import annotations

import unittest

from ai_agent_events import EventBus, PublishedEvent, TaskProgressProjection, TaskProjectionError
from ai_agent_tenant import IdentityContext


def context(tenant="tenant-a", identity="identity-1"): return IdentityContext("request-1", "trace-1", identity, "user", tenant)


class TaskProgressProjectionTest(unittest.TestCase):
    def test_event_updates_realtime_projection(self) -> None:
        events = EventBus(); projection = TaskProgressProjection(events)
        events.publish(PublishedEvent("event-1", "TASK_STATUS_CHANGED", "project-a", context(), {"task_id": "task-a", "current_status": "running", "progress_percent": 35}))
        self.assertEqual(projection.get(context(), "project-a", "task-a").progress_percent, 35)
        events.publish(PublishedEvent("event-2", "TASK_STATUS_CHANGED", "project-a", context(), {"task_id": "task-a", "current_status": "completed", "progress_percent": 100}))
        self.assertEqual(projection.get(context(), "project-a", "task-a").status, "completed")

    def test_projection_is_tenant_scoped(self) -> None:
        events = EventBus(); projection = TaskProgressProjection(events)
        events.publish(PublishedEvent("event-1", "TASK_STATUS_CHANGED", "project-a", context(), {"task_id": "task-a", "current_status": "running", "progress_percent": 1}))
        with self.assertRaises(TaskProjectionError): projection.get(context("tenant-b"), "project-a", "task-a")

    def test_projection_is_identity_scoped_within_tenant(self) -> None:
        events = EventBus(); projection = TaskProgressProjection(events)
        events.publish(PublishedEvent("event-1", "TASK_STATUS_CHANGED", "project-a", context(), {"task_id":"task-a", "current_status":"running", "progress_percent":1}))
        self.assertEqual(projection.list(context("tenant-a", "identity-2")), ())
        with self.assertRaises(TaskProjectionError):
            projection.get(context("tenant-a", "identity-2"), "project-a", "task-a")

    def test_invalid_progress_is_rejected(self) -> None:
        events = EventBus(); TaskProgressProjection(events)
        with self.assertRaises(TaskProjectionError):
            events.publish(PublishedEvent("event-1", "TASK_STATUS_CHANGED", "project-a", context(), {"task_id": "task-a", "current_status": "running", "progress_percent": 101}))


if __name__ == "__main__": unittest.main()
