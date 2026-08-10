from __future__ import annotations

import unittest
from ai_agent_core import AgentCollaborationError


class AgentCollaborationE2ETest(unittest.TestCase):
    def test_loop_guard_is_explicit(self):
        self.assertTrue(issubclass(AgentCollaborationError, ValueError))


if __name__=="__main__":unittest.main()
