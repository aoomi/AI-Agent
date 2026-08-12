from __future__ import annotations

import unittest

from ai_agent_core import AgentConfigurationError, AgentConfigurationStore
from ai_agent_llm_gateway import ModelRegistry
from pathlib import Path
from ai_agent_discovery import AgentInstance, SkillDefinition


class AgentConfigurationControlTest(unittest.TestCase):
    def test_reads_reject_anonymous_or_invalid_version_controls(self) -> None:
        store = AgentConfigurationStore(ModelRegistry())
        with self.assertRaisesRegex(AgentConfigurationError, "agent_id is required"):
            store.get(" ")
        with self.assertRaisesRegex(AgentConfigurationError, "agent_id is required"):
            store.history(" ")
        with self.assertRaisesRegex(AgentConfigurationError, "agent_id is required"):
            store.get(1)  # type: ignore[arg-type]
        for version in (0, -1, True):
            with self.subTest(version=version), self.assertRaisesRegex(AgentConfigurationError, "positive integer"):
                store.get("agent-1", version)  # type: ignore[arg-type]

    def test_writes_reject_invalid_agent_skill_and_model_contracts(self) -> None:
        store=AgentConfigurationStore(ModelRegistry())
        agent=AgentInstance("agent","Agent","skill","idle")
        skill=SkillDefinition("skill","Skill","1","main.py","test",Path("manifest.yaml"),{})
        for operation in (lambda:store.create(agent=object(),skill=skill,model_id="model",updated_by_identity_id="owner"),lambda:store.create(agent=agent,skill=object(),model_id="model",updated_by_identity_id="owner"),lambda:store.create(agent=agent,skill=skill,model_id=1,updated_by_identity_id="owner")):
            with self.subTest(operation=operation),self.assertRaises(AgentConfigurationError):operation()


if __name__ == "__main__":
    unittest.main()
