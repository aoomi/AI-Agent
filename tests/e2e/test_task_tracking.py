from __future__ import annotations

import unittest

from ai_agent_events import EventBus, PublishedEvent
from ai_agent_queue import InMemoryTaskQueue, QueuedTask, TaskService
from ai_agent_queue import QueueConflictError
from ai_agent_tenant import IdentityContext, IdentityContextError


class TaskTrackingEndToEndTest(unittest.TestCase):
    def test_queue_event_projection_refresh_and_tenant_boundary(self) -> None:
        queue, events = InMemoryTaskQueue(), EventBus()
        owner = IdentityContext("request-1", "trace-1", "identity-1", "user", "tenant-a")
        queue.enqueue(QueuedTask("task-a", "project-a", "operation-a", "pipeline", owner, {}))
        replay, replayed = queue.enqueue(QueuedTask("task-replay", "project-a", "operation-a", "pipeline", owner, {}))
        self.assertTrue(replayed); self.assertEqual(replay.task_id, "task-a")
        with self.assertRaises(QueueConflictError):
            queue.enqueue(QueuedTask("task-conflict", "project-a", "operation-a", "different", owner, {}))
        service = TaskService(queue, events)
        first = service.list_tasks(owner, "project-a")
        self.assertEqual(first[0].status, "queued")
        events.publish(PublishedEvent("event-1", "TASK_STATUS_CHANGED", "project-a", owner, {"task_id": "task-a", "current_status": "running", "progress_percent": 50}))
        refreshed = service.list_tasks(owner, "project-a")
        self.assertEqual((refreshed[0].status, refreshed[0].payload["progress_percent"]), ("running", 50))
        outsider = IdentityContext("request-2", "trace-2", "identity-2", "user", "tenant-b")
        self.assertEqual(service.list_tasks(outsider, "project-a"), ())
        with self.assertRaises(IdentityContextError): service.get_task(outsider, "task-a")


if __name__ == "__main__": unittest.main()
