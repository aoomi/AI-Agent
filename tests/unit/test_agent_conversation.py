from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ai_agent_core import AgentConfigurationStore, AgentConversationService, ConversationError, ConversationMemoryStore
from ai_agent_discovery import AgentRegistry, SkillRegistry
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry


ROOT = Path(__file__).resolve().parents[2]


class ModelClient:
    def __init__(self, response): self.response = response; self.calls = 0
    def complete(self, model, messages, response_schema): self.calls += 1; return self.response


class TaskExecutor:
    def __init__(self): self.calls = []
    def execute(self, configuration, requested_changes, confirmed_by_identity_id):
        self.calls.append((configuration, dict(requested_changes), confirmed_by_identity_id))
        return {"task_id": "task-1"}


class ResultExecutor(TaskExecutor):
    def __init__(self, result): self.result = result; self.calls = []
    def execute(self, configuration, requested_changes, confirmed_by_identity_id):
        self.calls.append((configuration, dict(requested_changes), confirmed_by_identity_id)); return self.result


class FailingMemoryStore(ConversationMemoryStore):
    def update(self, identity_id, project_id, values):
        raise OSError("memory persistence failed")


class AgentConversationServiceTest(unittest.TestCase):
    def test_runtime_control_shapes_are_rejected(self) -> None:
        skill,agent=self.configured();service=AgentConversationService(self.models,self.configurations,None);service.bind(agent,skill)
        with self.assertRaisesRegex(ConversationError,"context must be a mapping"):service.open_session(agent.agent_id,"identity",[])
        with self.assertRaisesRegex(ConversationError,"session_id is required"):service.messages(" ","identity")
        with self.assertRaisesRegex(ConversationError,"proposal_id is required"):service.confirm(" ","identity")
        for operation in (lambda:service.messages(1,"identity"),lambda:service.messages("missing",1),lambda:service.confirm(1,"identity")):
            with self.subTest(operation=operation),self.assertRaises(ConversationError):operation()
        memory=ConversationMemoryStore()
        for operation in (lambda:memory.read(1,"project"),lambda:memory.update("identity",1,{})):
            with self.subTest(operation=operation),self.assertRaises(ConversationError):operation()
        for operation in (lambda:service.bind(object(),skill),lambda:service.bind(agent,object()),lambda:service.open_session(1,"identity",{"project_id":"project"}),lambda:service.open_session(agent.agent_id,1,{"project_id":"project"})):
            with self.subTest(operation=operation),self.assertRaises(ConversationError):operation()
        for build in (lambda:ConversationMemoryStore("memory.json"),lambda:AgentConversationService(object(),self.configurations,None),lambda:AgentConversationService(self.models,self.configurations,object()),lambda:AgentConversationService(self.models,self.configurations,None,task_executor=object()),lambda:AgentConversationService(self.models,self.configurations,None,memory_store=object())):
            with self.subTest(build=build),self.assertRaises(ConversationError):build()
        for operation in (lambda:service.open_session(agent.agent_id,"identity",{1:"value","project_id":"project"}),lambda:service.open_session(agent.agent_id,"identity",{"project_id":1}),lambda:memory.update("identity","project",{1:"value"})):
            with self.subTest(operation=operation),self.assertRaises(ConversationError):operation()
    def setUp(self) -> None:
        self.skills = {skill.skill_id: skill for skill in SkillRegistry(ROOT / "plugins/builtin").scan()}
        self.agents = AgentRegistry(); self.models = ModelRegistry()
        self.models.register(ModelDefinition.create(model_id="model-full", provider_id="provider", display_name="Full", capabilities={"chat", "reasoning", "tool_calling", "structured_output"}, context_window=32768))
        self.configurations = AgentConfigurationStore(self.models)

    def configured(self, skill_id="system_main_developer"):
        skill = self.skills[skill_id]; agent, _ = self.agents.register(skill)
        self.configurations.create(agent=agent, skill=skill, model_id="model-full", updated_by_identity_id="owner")
        return skill, agent

    def test_configuration_proposal_requires_confirmation_and_versions_update(self) -> None:
        skill, agent = self.configured()
        client = ModelClient({"reply": "请确认配置", "proposal": {"proposal_type": "configuration_change", "requested_changes": {"settings": {"approval": "strict"}}}})
        service = AgentConversationService(self.models, self.configurations, client); service.bind(agent, skill)
        session = service.open_session(agent.agent_id, "owner", {"project_id":"project"})
        _, proposal = service.send(session.session_id, "将审批改为严格", "owner")
        self.assertIsNotNone(proposal); self.assertEqual(self.configurations.get(agent.agent_id).configuration_version, 1)
        applied = service.confirm(proposal.proposal_id, "owner")
        self.assertEqual(applied.status, "applied"); self.assertEqual(self.configurations.get(agent.agent_id).configuration_version, 2)
        self.assertEqual(len(service.messages(session.session_id, "owner")), 3)

    def test_complex_task_executes_only_after_confirmation(self) -> None:
        skill, agent = self.configured(); executor = TaskExecutor()
        client = ModelClient({"reply": "任务已规划", "proposal": {"proposal_type": "task_execution", "requested_changes": {"objective": "实现复杂功能"}}})
        service = AgentConversationService(self.models, self.configurations, client, executor); service.bind(agent, skill)
        _, proposal = service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "执行复杂任务", "owner")
        self.assertEqual(executor.calls, [])
        applied = service.confirm(proposal.proposal_id, "owner")
        self.assertEqual(applied.applied_result["task_id"], "task-1"); self.assertEqual(len(executor.calls), 1)

    def test_inspector_cannot_propose_writable_task(self) -> None:
        skill, agent = self.configured("system_inspector")
        client = ModelClient({"reply": "提案", "proposal": {"proposal_type": "task_execution", "requested_changes": {"objective": "修改代码"}}})
        service = AgentConversationService(self.models, self.configurations, client); service.bind(agent, skill)
        with self.assertRaisesRegex(ConversationError, "read-only"):
            service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "修改代码", "owner")

    def test_missing_real_model_client_fails_explicitly(self) -> None:
        skill, agent = self.configured()
        service = AgentConversationService(self.models, self.configurations, None); service.bind(agent, skill)
        with self.assertRaisesRegex(ConversationError, "not configured"):
            service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "你好", "owner")

    def test_invalid_model_response_has_no_partial_conversation_commit(self) -> None:
        skill, agent = self.configured()
        service = AgentConversationService(self.models, self.configurations, ModelClient({"reply":"ok", "plan":[""]})); service.bind(agent, skill)
        session = service.open_session(agent.agent_id, "owner", {"project_id":"project"})
        with self.assertRaisesRegex(ConversationError, "plan"):
            service.send(session.session_id, "invalid response", "owner")
        self.assertEqual(len(service.messages(session.session_id, "owner")), 1)
        self.assertEqual(service.proposals(session.session_id, "owner"), ())

    def test_sensitive_proposal_and_executor_result_are_not_published(self) -> None:
        skill, agent = self.configured()
        unsafe = ModelClient({"reply":"wait", "proposal":{"proposal_type":"task_execution", "requested_changes":{"headers":{"Authorization":"Bearer plaintext"}}}})
        service = AgentConversationService(self.models, self.configurations, unsafe); service.bind(agent, skill)
        session = service.open_session(agent.agent_id, "owner", {"project_id":"project"})
        with self.assertRaisesRegex(ConversationError, "sensitive fields"): service.send(session.session_id, "run", "owner")
        self.assertEqual(len(service.messages(session.session_id, "owner")), 1)
        executor = ResultExecutor({"access_token":"plaintext"})
        safe = ModelClient({"reply":"wait", "proposal":{"proposal_type":"task_execution", "requested_changes":{"objective":"run"}}})
        service = AgentConversationService(self.models, self.configurations, safe, executor); service.bind(agent, skill)
        session = service.open_session(agent.agent_id, "owner", {"project_id":"project"}); _, proposal = service.send(session.session_id, "run", "owner")
        with self.assertRaisesRegex(ConversationError, "sensitive fields"): service.confirm(proposal.proposal_id, "owner")
        self.assertEqual(service.proposals(session.session_id, "owner")[0].status, "failed")

    def test_sensitive_memory_update_is_not_persisted(self) -> None:
        skill, agent = self.configured(); memory = ConversationMemoryStore()
        client = ModelClient({"reply":"ok", "memory_updates":{"profiles":[{"client_secret":"plaintext"}]}})
        service = AgentConversationService(self.models, self.configurations, client, memory_store=memory); service.bind(agent, skill)
        session = service.open_session(agent.agent_id, "owner", {"project_id":"project"})
        with self.assertRaisesRegex(ConversationError, "sensitive fields"): service.send(session.session_id, "remember", "owner")
        self.assertEqual(memory.read("owner", "project"), {})
        self.assertEqual(len(service.messages(session.session_id, "owner")), 1)

    def test_memory_persistence_failure_has_no_partial_conversation_commit(self) -> None:
        skill, agent = self.configured()
        client = ModelClient({
            "reply": "待确认",
            "memory_updates": {"style": "brief"},
            "proposal": {"proposal_type": "configuration_change", "requested_changes": {"settings": {"x": 1}}},
        })
        service = AgentConversationService(
            self.models, self.configurations, client, memory_store=FailingMemoryStore()
        )
        service.bind(agent, skill)
        session = service.open_session(agent.agent_id, "owner", {"project_id": "project"})
        with self.assertRaisesRegex(OSError, "memory persistence failed"):
            service.send(session.session_id, "remember this", "owner")
        self.assertEqual(len(service.messages(session.session_id, "owner")), 1)
        self.assertEqual(service.proposals(session.session_id, "owner"), ())

    def test_memory_store_does_not_publish_failed_file_update(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            store = ConversationMemoryStore(path)
            store.update("owner", "project", {"style": "brief"})
            path.parent.chmod(0o500)
            try:
                with self.assertRaises(OSError):
                    store.update("owner", "project", {"goal": "finish"})
            finally:
                path.parent.chmod(0o700)
            self.assertEqual(store.read("owner", "project"), {"style": "brief"})

    def test_rejected_proposal_cannot_be_confirmed(self) -> None:
        skill, agent = self.configured()
        client = ModelClient({"reply": "提案", "proposal": {"proposal_type": "configuration_change", "requested_changes": {"settings": {"x": 1}}}})
        service = AgentConversationService(self.models, self.configurations, client); service.bind(agent, skill)
        _, proposal = service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "更改", "owner")
        service.reject(proposal.proposal_id, "owner")
        with self.assertRaisesRegex(ConversationError, "not pending"):
            service.confirm(proposal.proposal_id, "owner")

    def test_session_injects_skill_project_context_and_reuses_memory(self) -> None:
        skill, agent = self.configured()
        client = ModelClient({"reply": "已记住", "memory_updates": {"answer_style": "精简", "goal": "完成视频工作流"}})
        service = AgentConversationService(self.models, self.configurations, client); service.bind(agent, skill)
        first = service.open_session(agent.agent_id, "owner", {"project_id": "project-1", "task_id": "task-1"})
        service.send(first.session_id, "以后回答精简", "owner")
        second = service.open_session(agent.agent_id, "owner", {"project_id": "project-1"})
        system = service.messages(second.session_id, "owner")[0].content
        self.assertIn("skill_id=system_main_developer", system)
        self.assertIn("完成视频工作流", system)
        self.assertEqual(second.context["project_id"], "project-1")

    def test_memory_survives_service_restart(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            first = ConversationMemoryStore(path); first.update("owner", "project-1", {"style": "精简"})
            self.assertEqual(ConversationMemoryStore(path).read("owner", "project-1")["style"], "精简")
            self.assertEqual(ConversationMemoryStore(path).read("other", "project-1"), {})

    def test_persistent_memory_rejects_non_standard_json_without_partial_write(self) -> None:
        with TemporaryDirectory() as directory:
            path=Path(directory)/"memory.json";store=ConversationMemoryStore(path)
            for value in (float("nan"),object()):
                with self.subTest(value=value),self.assertRaisesRegex(ConversationError,"standard JSON"):
                    store.update("owner","project",{"value":value})
            self.assertFalse(path.exists())
            self.assertEqual(store.read("owner","project"),{})

    def test_clarification_cannot_create_execution_proposal(self) -> None:
        skill, agent = self.configured()
        client = ModelClient({"reply": "需要确认目标平台", "needs_clarification": True, "proposal": {"proposal_type": "task_execution", "requested_changes": {"objective": "执行"}}})
        service = AgentConversationService(self.models, self.configurations, client); service.bind(agent, skill)
        with self.assertRaisesRegex(ConversationError, "clarification response"):
            service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "开始", "owner")

    def test_selected_skill_and_plan_are_enforced(self) -> None:
        skill, agent = self.configured(); executor = TaskExecutor()
        client = ModelClient({"reply": "计划待确认", "selected_skill_id": skill.skill_id, "plan": ["读取上下文", "执行任务"], "proposal": {"proposal_type": "task_execution", "requested_changes": {"objective": "执行"}}})
        service = AgentConversationService(self.models, self.configurations, client, executor); service.bind(agent, skill)
        _, proposal = service.send(service.open_session(agent.agent_id, "owner", {"project_id":"project"}).session_id, "开始", "owner")
        self.assertEqual(proposal.requested_changes["plan"], ["读取上下文", "执行任务"])

    def test_conversation_lifecycle_is_owner_scoped(self) -> None:
        skill, agent = self.configured()
        client = ModelClient({"reply": "待确认", "proposal": {"proposal_type": "configuration_change", "requested_changes": {"settings": {"x": 1}}}})
        service = AgentConversationService(self.models, self.configurations, client); service.bind(agent, skill)
        session = service.open_session(agent.agent_id, "owner", {"project_id":"project"})
        with self.assertRaisesRegex(ConversationError, "not owned"):
            service.send(session.session_id, "越权消息", "other")
        _, proposal = service.send(session.session_id, "更改", "owner")
        for operation in (
            lambda: service.messages(session.session_id, "other"),
            lambda: service.proposals(session.session_id, "other"),
            lambda: service.confirm(proposal.proposal_id, "other"),
            lambda: service.reject(proposal.proposal_id, "other"),
        ):
            with self.assertRaisesRegex(ConversationError, "not owned"):
                operation()
        self.assertEqual(service.confirm(proposal.proposal_id, "owner").status, "applied")


if __name__ == "__main__": unittest.main()
