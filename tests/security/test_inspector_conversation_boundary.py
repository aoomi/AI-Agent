from __future__ import annotations

from pathlib import Path
import unittest

from ai_agent_core import AgentConfigurationStore, AgentConversationService, ConversationError
from ai_agent_discovery import AgentRegistry, SkillRegistry
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry


class WritableProposalClient:
    def complete(self, model, messages, response_schema):
        return {"reply": "修改提案", "proposal": {"proposal_type": "task_execution", "requested_changes": {"objective": "修改工作区"}}}


class InspectorConversationSecurityTest(unittest.TestCase):
    def test_inspector_model_output_cannot_cross_read_only_boundary(self) -> None:
        root = Path(__file__).resolve().parents[2]
        skill = {item.skill_id: item for item in SkillRegistry(root / "plugins/builtin").scan()}["system_inspector"]
        agent, _ = AgentRegistry().register(skill)
        models = ModelRegistry(); models.register(ModelDefinition.create(model_id="model", provider_id="provider", display_name="Model", capabilities={"chat", "reasoning", "tool_calling", "structured_output"}, context_window=32768))
        configurations = AgentConfigurationStore(models)
        configuration = configurations.create(agent=agent, skill=skill, model_id="model", updated_by_identity_id="owner")
        self.assertFalse(configuration.writable)
        service = AgentConversationService(models, configurations, WritableProposalClient()); service.bind(agent, skill)
        with self.assertRaisesRegex(ConversationError, "read-only"):
            service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "修改代码", "owner")


if __name__ == "__main__": unittest.main()
