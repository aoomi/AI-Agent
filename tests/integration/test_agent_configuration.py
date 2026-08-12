from __future__ import annotations

from pathlib import Path
import unittest

from ai_agent_core import AgentConfigurationStore, AgentConversationService, ConversationError
from ai_agent_discovery import AgentRegistry, SkillRegistry
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry


ROOT = Path(__file__).resolve().parents[2]


class ResponseClient:
    def __init__(self, response): self.response = response
    def complete(self, model, messages, response_schema): return self.response


class RecordingExecutor:
    def __init__(self): self.executions = []
    def execute(self, configuration, requested_changes, confirmed_by_identity_id):
        self.executions.append((configuration.role, configuration.writable, dict(requested_changes)))
        return {"task_id": f"task-{len(self.executions)}"}


class AgentConfigurationIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        skills = SkillRegistry(ROOT / "plugins/builtin").scan()
        self.skills = {skill.skill_id: skill for skill in skills}
        self.agents = AgentRegistry(); self.models = ModelRegistry()
        for model_id, window in (("model-a", 32768), ("model-b", 65536)):
            self.models.register(ModelDefinition.create(model_id=model_id, provider_id="provider", display_name=model_id, capabilities={"chat", "reasoning", "tool_calling", "structured_output"}, context_window=window))
        self.configurations = AgentConfigurationStore(self.models)

    def configure(self, skill_id):
        skill = self.skills[skill_id]; agent, _ = self.agents.register(skill)
        self.configurations.create(agent=agent, skill=skill, model_id="model-a", updated_by_identity_id="owner")
        return skill, agent

    def test_conversation_switches_model_with_versioned_confirmation(self) -> None:
        skill, agent = self.configure("system_main_developer")
        client = ResponseClient({"reply": "切换方案待确认", "proposal": {"proposal_type": "configuration_change", "requested_changes": {"model_id": "model-b", "settings": {"effort": "high"}}}})
        service = AgentConversationService(self.models, self.configurations, client); service.bind(agent, skill)
        _, proposal = service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "切换高上下文模型", "owner")
        self.assertEqual(self.configurations.get(agent.agent_id).model_id, "model-a")
        service.confirm(proposal.proposal_id, "owner")
        updated = self.configurations.get(agent.agent_id)
        self.assertEqual((updated.model_id, updated.configuration_version), ("model-b", 2))
        self.assertEqual(len(self.configurations.history(agent.agent_id)), 2)

    def test_developer_complex_task_runs_only_after_confirmation(self) -> None:
        skill, agent = self.configure("system_main_developer"); executor = RecordingExecutor()
        client = ResponseClient({"reply": "复杂任务待确认", "proposal": {"proposal_type": "task_execution", "requested_changes": {"objective": "跨模块实现", "steps": ["contract", "backend", "frontend"]}}})
        service = AgentConversationService(self.models, self.configurations, client, executor); service.bind(agent, skill)
        _, proposal = service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "执行复杂任务", "owner")
        self.assertEqual(executor.executions, [])
        service.confirm(proposal.proposal_id, "owner")
        self.assertEqual(executor.executions[0][0:2], ("developer", True))

    def test_inspector_is_read_only_for_configuration_and_tasks(self) -> None:
        skill, agent = self.configure("system_inspector"); executor = RecordingExecutor()
        readonly = ResponseClient({"reply": "只读稽查待确认", "proposal": {"proposal_type": "task_execution", "requested_changes": {"objective": "检查代码", "read_only": True}}})
        service = AgentConversationService(self.models, self.configurations, readonly, executor); service.bind(agent, skill)
        _, proposal = service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "检查", "owner")
        service.confirm(proposal.proposal_id, "owner")
        self.assertEqual(executor.executions[0][0:2], ("inspector", False))
        writable = ResponseClient({"reply": "修改", "proposal": {"proposal_type": "task_execution", "requested_changes": {"objective": "修改代码"}}})
        denied = AgentConversationService(self.models, self.configurations, writable, executor); denied.bind(agent, skill)
        with self.assertRaisesRegex(ConversationError, "read-only"):
            denied.send(denied.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "修改", "owner")

    def test_no_real_model_client_never_returns_simulated_success(self) -> None:
        skill, agent = self.configure("system_main_developer")
        service = AgentConversationService(self.models, self.configurations, None); service.bind(agent, skill)
        with self.assertRaisesRegex(ConversationError, "real conversation model client is not configured"):
            service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "生成方案", "owner")


if __name__ == "__main__": unittest.main()
