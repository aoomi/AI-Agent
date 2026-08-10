from __future__ import annotations

import unittest

from ai_agent_queue import InMemoryTaskQueue, QueuedTask, TaskService
from ai_agent_tenant import IdentityContext, IdentityContextError


def context(tenant: str) -> IdentityContext:
    return IdentityContext("request-1", "trace-1", "identity-1", "user", tenant)


class TaskServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.queue = InMemoryTaskQueue(); self.service = TaskService(self.queue)
        for task_id, tenant, project in (("task-a", "tenant-a", "project-a"), ("task-b", "tenant-a", "project-b"), ("task-c", "tenant-b", "project-a")):
            self.queue.enqueue(QueuedTask(task_id, project, "operation-" + task_id, "type", context(tenant), {}))

    def test_list_is_tenant_and_project_scoped(self) -> None:
        self.assertEqual([task.task_id for task in self.service.list_tasks(context("tenant-a"), "project-a")], ["task-a"])

    def test_cross_tenant_detail_is_rejected(self) -> None:
        with self.assertRaises(IdentityContextError): self.service.get_task(context("tenant-b"), "task-a")

    def test_cancel_and_resume_follow_queue_transitions(self) -> None:
        self.assertEqual(self.service.cancel_task(context("tenant-a"), "task-a").status, "cancelled")
        self.queue.claim("tenant-a"); self.queue.finish("task-b", "failed")
        self.assertEqual(self.service.resume_task(context("tenant-a"), "task-b").status, "queued")


if __name__ == "__main__": unittest.main()
