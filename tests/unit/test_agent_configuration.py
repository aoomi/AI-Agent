from __future__ import annotations

from pathlib import Path
import unittest

from ai_agent_core import AgentConfigurationError, AgentConfigurationStore
from ai_agent_discovery import AgentRegistry, SkillRegistry
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry


ROOT = Path(__file__).resolve().parents[2]


class AgentConfigurationStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.skills = {
            skill.skill_id: skill for skill in SkillRegistry(ROOT / "plugins/builtin").scan()
        }
        self.agents = AgentRegistry()
        self.models = ModelRegistry()
        self.models.register(ModelDefinition.create(
            model_id="model-full", provider_id="provider", display_name="Full",
            capabilities={"chat", "reasoning", "tool_calling", "structured_output"},
            context_window=32768,
        ))
        self.models.register(ModelDefinition.create(
            model_id="model-chat", provider_id="provider", display_name="Chat",
            capabilities={"chat"}, context_window=8192,
        ))
        self.store = AgentConfigurationStore(self.models)

    def create_for(self, skill_id: str):
        skill = self.skills[skill_id]
        agent, _ = self.agents.register(skill)
        config = self.store.create(
            agent=agent, skill=skill, model_id="model-full", updated_by_identity_id="owner"
        )
        return skill, agent, config

    def test_inspector_is_always_read_only(self) -> None:
        _, _, config = self.create_for("system_inspector")
        self.assertFalse(config.writable)

    def test_update_versions_configuration_and_preserves_history(self) -> None:
        skill, agent, initial = self.create_for("system_main_developer")
        updated = self.store.update(
            agent.agent_id, expected_version=1, updated_by_identity_id="owner",
            settings={"approval": "required"}, skill=skill, agent=agent,
        )
        self.assertTrue(updated.writable)
        self.assertEqual(updated.configuration_version, 2)
        self.assertEqual(len(self.store.history(agent.agent_id)), 2)
        self.assertEqual(initial.configuration_id, updated.configuration_id)

    def test_stale_update_is_rejected(self) -> None:
        skill, agent, _ = self.create_for("system_main_developer")
        with self.assertRaisesRegex(AgentConfigurationError, "version conflict"):
            self.store.update(
                agent.agent_id, expected_version=2, updated_by_identity_id="owner",
                skill=skill, agent=agent,
            )

    def test_model_must_satisfy_skill_capabilities(self) -> None:
        skill = self.skills["system_main_developer"]
        agent, _ = self.agents.register(skill)
        with self.assertRaisesRegex(ValueError, "does not satisfy"):
            self.store.create(
                agent=agent, skill=skill, model_id="model-chat", updated_by_identity_id="owner"
            )


if __name__ == "__main__":
    unittest.main()
