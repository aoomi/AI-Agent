from __future__ import annotations

from pathlib import Path
from threading import Barrier, Thread
import unittest

from ai_agent_core import AgentConfigurationError, AgentConfigurationStore
from ai_agent_discovery import AgentRegistry, SkillRegistry
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry


ROOT = Path(__file__).resolve().parents[2]


class AgentConfigurationStoreTest(unittest.TestCase):
    def test_runtime_configuration_contracts_are_rejected(self) -> None:
        with self.assertRaisesRegex(AgentConfigurationError,"registry contract"):AgentConfigurationStore(object())
        skill=self.skills["system_main_developer"];agent,_=self.agents.register(skill)
        with self.assertRaisesRegex(AgentConfigurationError,"settings must be a mapping"):self.store.create(agent=agent,skill=skill,model_id="model-full",updated_by_identity_id="owner",settings=[])
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

    def test_concurrent_cas_allows_only_one_version_update(self) -> None:
        skill, agent, _ = self.create_for("system_main_developer")
        barrier = Barrier(3); results = []
        def update(value):
            barrier.wait()
            try: results.append(self.store.update(agent.agent_id, expected_version=1, updated_by_identity_id=value, settings={"value": value}, skill=skill, agent=agent))
            except AgentConfigurationError as error: results.append(error)
        threads = [Thread(target=update, args=(value,)) for value in ("one", "two")]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join()
        self.assertEqual(sum(not isinstance(item, Exception) for item in results), 1)
        self.assertEqual(self.store.get(agent.agent_id).configuration_version, 2)
        self.assertEqual(len(self.store.history(agent.agent_id)), 2)

    def test_model_must_satisfy_skill_capabilities(self) -> None:
        skill = self.skills["system_main_developer"]
        agent, _ = self.agents.register(skill)
        with self.assertRaisesRegex(ValueError, "does not satisfy"):
            self.store.create(
                agent=agent, skill=skill, model_id="model-chat", updated_by_identity_id="owner"
            )

    def test_sensitive_settings_are_rejected_recursively(self) -> None:
        skill = self.skills["system_main_developer"]
        agent, _ = self.agents.register(skill)
        for settings in (
            {"access_token": "plaintext"},
            {"transport": {"headers": {"Authorization": "Bearer plaintext"}}},
            {"profiles": [{"client_secret": "plaintext"}]},
        ):
            with self.subTest(settings=settings), self.assertRaisesRegex(
                AgentConfigurationError, "sensitive fields"
            ):
                self.store.create(
                    agent=agent, skill=skill, model_id="model-full",
                    updated_by_identity_id="owner", settings=settings,
                )

    def test_settings_require_standard_json(self) -> None:
        skill=self.skills["system_main_developer"];agent,_=self.agents.register(skill)
        for settings in ({"value":float("nan")},{"value":object()}):
            with self.subTest(settings=settings),self.assertRaisesRegex(AgentConfigurationError,"standard JSON"):
                self.store.create(agent=agent,skill=skill,model_id="model-full",updated_by_identity_id="owner",settings=settings)

    def test_skill_prompt_version_must_be_a_non_empty_string(self) -> None:
        from dataclasses import replace
        from types import MappingProxyType
        skill=self.skills["system_main_developer"];agent,_=self.agents.register(skill)
        for value in (1," "):
            metadata=dict(skill.metadata);metadata["system_prompt_version"]=value
            invalid=replace(skill,metadata=MappingProxyType(metadata))
            with self.subTest(value=value),self.assertRaisesRegex(AgentConfigurationError,"prompt_version"):self.store.create(agent=agent,skill=invalid,model_id="model-full",updated_by_identity_id="owner")


if __name__ == "__main__":
    unittest.main()
