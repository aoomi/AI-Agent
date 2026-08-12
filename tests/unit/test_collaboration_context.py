from __future__ import annotations

import unittest

from ai_agent_core import AgentContextError, CollaborationContextStore


class CollaborationContextStoreTest(unittest.TestCase):
    def test_runtime_update_shapes_are_rejected(self) -> None:
        for operation in (lambda:self.store.update("tenant-1","project-1","session-1",agent_id="developer-1",task_states=[]),lambda:self.store.update("tenant-1","project-1","session-1",agent_id="developer-1",evidence_references="proof")):
            with self.subTest(operation=operation),self.assertRaises(AgentContextError):operation()
    def setUp(self) -> None:
        self.store = CollaborationContextStore()
        self.store.create(tenant_id="tenant-1", project_id="project-1", session_id="session-1", developer_agent_id="developer-1", inspector_agent_id="inspector-1")

    def test_developer_publishes_state_and_inspector_reads_snapshot(self) -> None:
        self.store.update("tenant-1", "project-1", "session-1", agent_id="developer-1", task_states={"task-1": "waiting_inspection"}, evidence_references=("evidence/result.xml",), file_references=("platform/core/example.py",))
        snapshot = self.store.get("tenant-1", "project-1", "session-1", agent_id="inspector-1")
        self.assertEqual(snapshot.task_states["task-1"], "waiting_inspection")
        self.assertEqual(snapshot.file_references, ("platform/core/example.py",))
        with self.assertRaises(TypeError): snapshot.task_states["task-2"] = "running"  # type: ignore[index]

    def test_inspector_and_unbound_agent_cannot_mutate_or_read(self) -> None:
        with self.assertRaisesRegex(AgentContextError, "only the developer"):
            self.store.update("tenant-1", "project-1", "session-1", agent_id="inspector-1", task_states={"task-1": "completed"})
        with self.assertRaisesRegex(AgentContextError, "cannot access"):
            self.store.get("tenant-1", "project-1", "session-1", agent_id="other-1")

    def test_scope_and_references_are_isolated(self) -> None:
        with self.assertRaises(AgentContextError): self.store.get("tenant-2", "project-1", "session-1", agent_id="developer-1")
        with self.assertRaisesRegex(AgentContextError, "safe relative"):
            self.store.update("tenant-1", "project-1", "session-1", agent_id="developer-1", file_references=("../../secret",))
        with self.assertRaisesRegex(AgentContextError, "task state"):
            self.store.update("tenant-1", "project-1", "session-1", agent_id="developer-1", task_states={"task": "unknown"})
        with self.assertRaisesRegex(AgentContextError,"identifiers"):
            self.store.update("tenant-1","project-1","session-1",agent_id="developer-1",task_states={" ":"running"})


if __name__ == "__main__": unittest.main()
