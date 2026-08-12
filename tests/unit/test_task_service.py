from __future__ import annotations

import unittest

from ai_agent_queue import InMemoryTaskQueue, QueueConflictError, QueuedTask, TaskService
from ai_agent_events import EventBus, PublishedEvent
from ai_agent_tenant import IdentityContext, IdentityContextError


def context(tenant: str, identity: str = "identity-1") -> IdentityContext:
    return IdentityContext("request-1", "trace-1", identity, "user", tenant)


class TaskServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.queue = InMemoryTaskQueue(); self.service = TaskService(self.queue)
        for task_id, tenant, project in (("task-a", "tenant-a", "project-a"), ("task-b", "tenant-a", "project-b"), ("task-c", "tenant-b", "project-a")):
            self.queue.enqueue(QueuedTask(task_id, project, "operation-" + task_id, "type", context(tenant), {}))

    def test_list_is_tenant_and_project_scoped(self) -> None:
        self.assertEqual([task.task_id for task in self.service.list_tasks(context("tenant-a"), "project-a")], ["task-a"])

    def test_cross_tenant_detail_is_rejected(self) -> None:
        with self.assertRaises(IdentityContextError): self.service.get_task(context("tenant-b"), "task-a")

    def test_same_tenant_cross_identity_list_and_detail_are_rejected(self) -> None:
        self.assertEqual(self.service.list_tasks(context("tenant-a", "identity-2")), ())
        with self.assertRaises(IdentityContextError):
            self.service.get_task(context("tenant-a", "identity-2"), "task-a")

    def test_cancel_and_resume_follow_queue_transitions(self) -> None:
        self.assertEqual(self.service.cancel_task(context("tenant-a"), "task-a").status, "cancelled")
        self.queue.claim("tenant-a"); self.queue.finish("task-b", "failed")
        self.assertEqual(self.service.resume_task(context("tenant-a"), "task-b").status, "queued")

    def test_runtime_dependencies_context_and_event_payload_are_rejected(self) -> None:
        for build in (lambda:TaskService(object()),lambda:TaskService(InMemoryTaskQueue(),object())):
            with self.subTest(build=build),self.assertRaises(QueueConflictError):build()
        with self.assertRaises(QueueConflictError):self.service.list_tasks(object())
        events=EventBus();queue=InMemoryTaskQueue();queue.enqueue(QueuedTask("task","project","operation","type",context("tenant-a"),{}));queue.claim("tenant-a")
        TaskService(queue,events)
        for payload in ({"task_id":1,"current_status":"paused","progress_percent":1},{"task_id":"task","current_status":"paused","progress_percent":"1"}):
            with self.subTest(payload=payload),self.assertRaises(QueueConflictError):events.publish(PublishedEvent("event","TASK_STATUS_CHANGED","project",context("tenant-a"),payload))
        self.assertEqual(queue.get("task","tenant-a").status,"running")


if __name__ == "__main__": unittest.main()
