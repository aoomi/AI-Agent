from __future__ import annotations

import unittest

from ai_agent_core import AgentConfigurationError, AgentConfigurationStore
from ai_agent_llm_gateway import ModelRegistry


class AgentConfigurationControlTest(unittest.TestCase):
    def test_reads_reject_anonymous_or_invalid_version_controls(self) -> None:
        store = AgentConfigurationStore(ModelRegistry())
        with self.assertRaisesRegex(AgentConfigurationError, "agent_id is required"):
            store.get(" ")
        with self.assertRaisesRegex(AgentConfigurationError, "agent_id is required"):
            store.history(" ")
        for version in (0, -1, True):
            with self.subTest(version=version), self.assertRaisesRegex(AgentConfigurationError, "positive integer"):
                store.get("agent-1", version)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
