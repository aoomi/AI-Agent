from __future__ import annotations

import unittest

from ai_agent_queue import InMemoryTaskQueue, QueueConflictError, QueuedTask
from ai_agent_tenant import IdentityContext, IdentityContextError


def task(task_id: str = "task-1", operation_key: str = "operation-1", tenant_id: str = "tenant-a", identity_id: str = "identity-1") -> QueuedTask:
    return QueuedTask(
        task_id=task_id,
        project_id="project-1",
        operation_key=operation_key,
        task_type="contract_test",
        context=IdentityContext("request-1", "trace-1", identity_id, "user", tenant_id),
        payload={"input": "value"},
    )


class InMemoryTaskQueueTest(unittest.TestCase):
    def test_enqueue_claim_and_complete(self) -> None:
        queue = InMemoryTaskQueue()
        queued, replayed = queue.enqueue(task())
        self.assertFalse(replayed)
        self.assertEqual(queued.status, "queued")
        claimed = queue.claim("tenant-a")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.status, "running")
        self.assertEqual(queue.finish("task-1", "completed").status, "completed")

    def test_same_operation_is_replayed(self) -> None:
        queue = InMemoryTaskQueue()
        first, _ = queue.enqueue(task())
        replay, replayed = queue.enqueue(task(task_id="task-2"))
        self.assertTrue(replayed)
        self.assertEqual(replay.task_id, first.task_id)

    def test_conflicting_operation_is_rejected(self) -> None:
        queue = InMemoryTaskQueue()
        queue.enqueue(task())
        conflicting = QueuedTask(
            "task-2", "project-1", "operation-1", "different", task().context, {"input": "value"}
        )
        with self.assertRaisesRegex(QueueConflictError, "conflicts"):
            queue.enqueue(conflicting)

    def test_task_payload_rejects_nested_sensitive_fields(self) -> None:
        for payload in (
            {"access_token":"plaintext"},
            {"transport":{"headers":{"Authorization":"Bearer plaintext"}}},
            {"profiles":[{"client_secret":"plaintext"}]},
        ):
            with self.subTest(payload=payload), self.assertRaisesRegex(QueueConflictError, "sensitive fields"):
                QueuedTask("task", "project", "operation", "type", task().context, payload)

    def test_same_tenant_different_identities_have_independent_operation_keys(self) -> None:
        queue = InMemoryTaskQueue()
        first, first_replayed = queue.enqueue(task())
        second, second_replayed = queue.enqueue(task(task_id="task-2", identity_id="identity-2"))
        self.assertFalse(first_replayed); self.assertFalse(second_replayed)
        self.assertNotEqual(first.task_id, second.task_id)

    def test_same_identity_different_projects_have_independent_operation_keys(self) -> None:
        queue = InMemoryTaskQueue()
        first, first_replayed = queue.enqueue(task())
        other_project = QueuedTask(
            task_id="task-2", project_id="project-2", operation_key="operation-1",
            task_type="contract_test", context=task().context, payload={"input": "value"},
        )
        second, second_replayed = queue.enqueue(other_project)
        self.assertFalse(first_replayed); self.assertFalse(second_replayed)
        self.assertNotEqual(first.task_id, second.task_id)

    def test_claim_and_read_are_tenant_scoped(self) -> None:
        queue = InMemoryTaskQueue()
        queue.enqueue(task())
        self.assertIsNone(queue.claim("tenant-b"))
        with self.assertRaises(IdentityContextError):
            queue.get("task-1", "tenant-b")

    def test_claim_can_be_restricted_to_identity(self) -> None:
        queue = InMemoryTaskQueue()
        queue.enqueue(task(task_id="task-1", identity_id="identity-1"))
        queue.enqueue(task(task_id="task-2", operation_key="operation-2", identity_id="identity-2"))
        self.assertEqual(queue.claim("tenant-a", "identity-2").task_id, "task-2")
        self.assertEqual(queue.claim("tenant-a", "identity-1").task_id, "task-1")

    def test_status_event_is_identity_scoped(self) -> None:
        queue = InMemoryTaskQueue(); queue.enqueue(task()); queue.claim("tenant-a", "identity-1")
        with self.assertRaises(IdentityContextError):
            queue.apply_status_event("task-1", "tenant-a", "identity-2", "project-1", "paused", 20)
        self.assertEqual(queue.get("task-1", "tenant-a", "identity-1").status, "running")

    def test_terminal_task_cannot_be_cancelled(self) -> None:
        queue = InMemoryTaskQueue()
        queue.enqueue(task())
        queue.claim("tenant-a")
        queue.finish("task-1", "completed")
        with self.assertRaisesRegex(QueueConflictError, "terminal"):
            queue.cancel("task-1")

    def test_failed_and_paused_tasks_can_return_to_queue(self) -> None:
        queue = InMemoryTaskQueue(); queue.enqueue(task()); queue.claim("tenant-a")
        queue.finish("task-1", "failed")
        self.assertEqual(queue.resume("task-1").status, "queued")
        queue.claim("tenant-a"); queue.pause("task-1")
        self.assertEqual(queue.resume("task-1").status, "queued")

    def test_public_controls_reject_empty_scope_identifiers(self) -> None:
        queue = InMemoryTaskQueue(); queue.enqueue(task()); queue.claim("tenant-a")
        calls = (
            lambda: queue.claim(" "), lambda: queue.claim("tenant-a", " "),
            lambda: queue.get(" ", "tenant-a"), lambda: queue.get("task-1", " "),
            lambda: queue.list(" "), lambda: queue.list("tenant-a", identity_id=" "),
            lambda: queue.cancel(" "), lambda: queue.pause(" "),
            lambda: queue.wait_for_human(" "), lambda: queue.resume(" "),
            lambda: queue.resume_human(" "),
            lambda: queue.apply_status_event(" ", "tenant-a", "identity-1", "project-1", "paused", 1),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaisesRegex(QueueConflictError, "must not be empty"):
                call()

    def test_finish_rejects_unknown_runtime_status_without_mutation(self) -> None:
        queue = InMemoryTaskQueue(); queue.enqueue(task()); queue.claim("tenant-a")
        with self.assertRaisesRegex(QueueConflictError, "finish status"):
            queue.finish("task-1", "cancelled")  # type: ignore[arg-type]
        self.assertEqual(queue.get("task-1", "tenant-a").status, "running")

    def test_status_event_rejects_unknown_runtime_status_without_mutation(self) -> None:
        queue = InMemoryTaskQueue(); queue.enqueue(task()); queue.claim("tenant-a")
        with self.assertRaisesRegex(QueueConflictError, "status is invalid"):
            queue.apply_status_event("task-1", "tenant-a", "identity-1", "project-1", "unknown", 1)  # type: ignore[arg-type]
        self.assertEqual(queue.get("task-1", "tenant-a").status, "running")

    def test_status_event_rejects_boolean_progress_without_mutation(self) -> None:
        queue = InMemoryTaskQueue(); queue.enqueue(task()); queue.claim("tenant-a")
        with self.assertRaisesRegex(QueueConflictError, "progress_percent"):
            queue.apply_status_event("task-1", "tenant-a", "identity-1", "project-1", "paused", True)  # type: ignore[arg-type]
        self.assertEqual(queue.get("task-1", "tenant-a").status, "running")

    def test_runtime_types_are_rejected_before_queue_mutation(self) -> None:
        invalid_tasks = (
            lambda: QueuedTask(1, "project", "operation", "type", task().context, {}),  # type: ignore[arg-type]
            lambda: QueuedTask("task", "project", "operation", "type", object(), {}),  # type: ignore[arg-type]
            lambda: QueuedTask("task", "project", "operation", "type", task().context, []),  # type: ignore[arg-type]
            lambda: QueuedTask("task", "project", "operation", "type", task().context, {}, status=[]),  # type: ignore[arg-type]
        )
        for build in invalid_tasks:
            with self.subTest(build=build), self.assertRaises(QueueConflictError):
                build()

        queue = InMemoryTaskQueue()
        with self.assertRaisesRegex(QueueConflictError, "QueuedTask"):
            queue.enqueue(object())  # type: ignore[arg-type]
        queue.enqueue(task())
        with self.assertRaisesRegex(QueueConflictError, "must be a string"):
            queue.claim(1)  # type: ignore[arg-type]
        queue.claim("tenant-a")
        with self.assertRaisesRegex(QueueConflictError, "finish status"):
            queue.finish("task-1", [])  # type: ignore[arg-type]
        with self.assertRaisesRegex(QueueConflictError, "status is invalid"):
            queue.apply_status_event("task-1", "tenant-a", "identity-1", "project-1", [], 1)  # type: ignore[arg-type]
        self.assertEqual(queue.get("task-1", "tenant-a").status, "running")

    def test_task_payload_requires_standard_json(self) -> None:
        for payload in ({"value":float("nan")},{"value":object()}):
            with self.subTest(payload=payload),self.assertRaisesRegex(QueueConflictError,"standard JSON"):
                QueuedTask("task","project","operation","type",task().context,payload)


if __name__ == "__main__":
    unittest.main()
