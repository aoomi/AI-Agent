from __future__ import annotations

import unittest

from ai_agent_core import AgentContextError, AgentContextStore, CollaborationContextStore


class AgentContextStoreTest(unittest.TestCase):
    def test_update_deeply_snapshots_caller_values(self) -> None:
        store=AgentContextStore();store.create("tenant","project","agent")
        values={"state":{"steps":["queued"]}};item=store.update("tenant","project","agent",values)
        values["state"]["steps"][0]="forged"
        self.assertEqual(item.values["state"]["steps"][0],"queued")
    def test_update_rejects_non_mapping_values(self) -> None:
        store=AgentContextStore();store.create("tenant","project","agent")
        with self.assertRaisesRegex(AgentContextError,"must be a mapping"):store.update("tenant","project","agent",[])
        for values in ({1:"value"},):
            with self.subTest(values=values),self.assertRaises(AgentContextError):store.update("tenant","project","agent",values)
    def test_context_is_scoped_to_tenant_project_and_agent(self) -> None:
        store = AgentContextStore()
        store.create("tenant-a", "project-a", "agent-a")
        context = store.update("tenant-a", "project-a", "agent-a", {"draft": "one"})
        self.assertEqual(context.values["draft"], "one")
        for scope in (("tenant-b", "project-a", "agent-a"), ("tenant-a", "project-b", "agent-a"), ("tenant-a", "project-a", "agent-b")):
            with self.subTest(scope=scope), self.assertRaises(AgentContextError):
                store.get(*scope)

    def test_returned_values_are_immutable_snapshots(self) -> None:
        store = AgentContextStore()
        context = store.create("tenant-a", "project-a", "agent-a")
        with self.assertRaises(TypeError):
            context.values["forbidden"] = True  # type: ignore[index]

    def test_duplicate_context_is_rejected(self) -> None:
        store = AgentContextStore()
        store.create("tenant-a", "project-a", "agent-a")
        with self.assertRaisesRegex(AgentContextError, "already exists"):
            store.create("tenant-a", "project-a", "agent-a")
        with self.assertRaisesRegex(AgentContextError,"keys"):store.update("tenant-a","project-a","agent-a",{" ":1})

    def test_sensitive_context_values_are_rejected_recursively(self) -> None:
        store=AgentContextStore();store.create("tenant-a","project-a","agent-a")
        for values in ({"access_token":"plaintext"},{"headers":{"Authorization":"Bearer plaintext"}},{"profiles":[{"client_secret":"plaintext"}]}):
            with self.subTest(values=values),self.assertRaisesRegex(AgentContextError,"sensitive fields"):store.update("tenant-a","project-a","agent-a",values)
        for values in ({"value":float("nan")},{"value":object()}):
            with self.subTest(values=values),self.assertRaisesRegex(AgentContextError,"standard JSON"):store.update("tenant-a","project-a","agent-a",values)

    def test_context_identifiers_and_references_require_strings(self) -> None:
        store=AgentContextStore()
        with self.assertRaises(AgentContextError):store.create(1,"project","agent")  # type: ignore[arg-type]
        collaboration=CollaborationContextStore()
        with self.assertRaises(AgentContextError):collaboration.create(tenant_id="tenant",project_id="project",session_id=1,developer_agent_id="dev",inspector_agent_id="audit")  # type: ignore[arg-type]
        collaboration.create(tenant_id="tenant",project_id="project",session_id="session",developer_agent_id="dev",inspector_agent_id="audit")
        with self.assertRaises(AgentContextError):
            collaboration.update("tenant","project","session",agent_id="dev",evidence_references=(1,))  # type: ignore[arg-type]
        for states in ({1:"running"},{"task":[]}):
            with self.subTest(states=states),self.assertRaises(AgentContextError):collaboration.update("tenant","project","session",agent_id="dev",task_states=states)


if __name__ == "__main__":
    unittest.main()
