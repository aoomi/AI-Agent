from __future__ import annotations

import unittest

from ai_agent_core import AgentContextError, AgentContextStore


class AgentContextStoreTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
