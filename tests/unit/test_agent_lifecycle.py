from __future__ import annotations

import unittest

from ai_agent_core import AgentLifecycle, AgentLifecycleError, AgentState


class AgentLifecycleTest(unittest.TestCase):
    def test_agent_can_complete(self) -> None:
        lifecycle = AgentLifecycle()
        state = lifecycle.transition(AgentState("agent-1"), "loading")
        state = lifecycle.transition(state, "running")
        self.assertEqual(lifecycle.transition(state, "completed").status, "completed")

    def test_human_wait_can_resume(self) -> None:
        lifecycle = AgentLifecycle()
        state = AgentState("agent-1", "running")
        state = lifecycle.transition(state, "waiting_human")
        self.assertEqual(lifecycle.transition(state, "running").status, "running")

    def test_idle_cannot_skip_loading(self) -> None:
        with self.assertRaisesRegex(AgentLifecycleError, "idle:running"):
            AgentLifecycle().transition(AgentState("agent-1"), "running")

    def test_terminal_state_cannot_restart(self) -> None:
        with self.assertRaises(AgentLifecycleError):
            AgentLifecycle().transition(AgentState("agent-1", "completed"), "running")


if __name__ == "__main__":
    unittest.main()
