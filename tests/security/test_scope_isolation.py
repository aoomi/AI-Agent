from __future__ import annotations

import unittest

from ai_agent_core import AgentContextError, AgentContextStore
from ai_agent_queue import InMemoryTaskQueue, QueuedTask, TaskService
from ai_agent_tenant import IdentityContext, IdentityContextError


class ScopeIsolationSecurityTest(unittest.TestCase):
    def test_cross_tenant_task_and_cross_agent_context_are_denied(self) -> None:
        owner = IdentityContext("request-1", "trace-1", "identity-1", "user", "tenant-a")
        attacker = IdentityContext("request-2", "trace-2", "identity-2", "user", "tenant-b")
        queue = InMemoryTaskQueue(); queue.enqueue(QueuedTask("task-a", "project-a", "operation-a", "pipeline", owner, {}))
        with self.assertRaises(IdentityContextError): TaskService(queue).get_task(attacker, "task-a")
        contexts = AgentContextStore(); contexts.create("tenant-a", "project-a", "agent-a")
        with self.assertRaises(AgentContextError): contexts.get("tenant-a", "project-a", "agent-b")


if __name__ == "__main__": unittest.main()
