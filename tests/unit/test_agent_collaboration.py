from __future__ import annotations

import unittest
from pathlib import Path

from ai_agent_core import AgentCollaborationError, AgentCollaborationService, AgentConfigurationStore
from ai_agent_discovery import AgentRegistry, SkillRegistry
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry


class InspectionExecutor:
    def __init__(self, result: dict) -> None: self.result = result
    def inspect(self, handoff): return self.result


class RemediationScheduler:
    def __init__(self) -> None: self.instructions = []
    def schedule_remediation(self, instruction): self.instructions.append(instruction)


class AgentCollaborationServiceTest(unittest.TestCase):
    def test_runtime_dependency_and_identifier_contracts_are_rejected(self) -> None:
        with self.assertRaisesRegex(AgentCollaborationError,"configuration store"):AgentCollaborationService(object(),None)
        with self.assertRaisesRegex(AgentCollaborationError,"inspection executor"):AgentCollaborationService(self.configurations,object())
        service=AgentCollaborationService(self.configurations,None)
        for operation in (lambda:service.get_session(" "),lambda:service.get_handoff(" "),lambda:service.get_report(" "),lambda:service.get_instruction(" ")):
            with self.subTest(operation=operation),self.assertRaises(AgentCollaborationError):operation()
    def setUp(self) -> None:
        models = ModelRegistry(); models.register(ModelDefinition.create(model_id="model-1", provider_id="provider-1", display_name="Model", capabilities={"chat", "reasoning", "tool_calling", "structured_output"}, context_window=10000))
        configurations = AgentConfigurationStore(models)
        skills = {item.skill_id: item for item in SkillRegistry(Path(__file__).resolve().parents[2] / "plugins/builtin").scan()}
        agents = AgentRegistry()
        self.developer, _ = agents.register(skills["system_main_developer"])
        self.inspector, _ = agents.register(skills["system_inspector"])
        configurations.create(agent=self.developer, skill=skills["system_main_developer"], model_id="model-1", updated_by_identity_id="user-1")
        configurations.create(agent=self.inspector, skill=skills["system_inspector"], model_id="model-1", updated_by_identity_id="user-1")
        self.configurations = configurations

    def open(self, executor=None, scheduler=None, max_rounds=3):
        service = AgentCollaborationService(self.configurations, executor, scheduler)
        session = service.open_session(tenant_id="tenant-1", created_by_identity_id="user-1", project_id="project-1", root_task_id="task-1", developer_agent_id=self.developer.agent_id, inspector_agent_id=self.inspector.agent_id, max_remediation_rounds=max_rounds)
        return service, session

    def test_developer_submits_and_inspector_returns_read_only_report(self) -> None:
        executor = InspectionExecutor({"read_only": True, "verdict": "changes_required", "issues": [{"issue_id": "issue-1", "code": "TEST_FAILURE", "title": "测试失败", "description": "修复测试", "severity": "high", "file_reference": "tests/test_x.py", "evidence_ids": ["evidence-1"]}], "evidence": [{"evidence_id": "evidence-1", "kind": "test", "reference": "results/test.xml", "metadata": {"passed": False}}]})
        service, session = self.open(executor)
        handoff = service.submit_for_inspection(session.session_id, task_id="task-1", context_reference="contexts/task-1.json")
        report = service.run_inspection(handoff.handoff_id)
        self.assertTrue(report.read_only)
        self.assertEqual(report.verdict, "changes_required")
        self.assertEqual(service.get_handoff(handoff.handoff_id).status, "completed")
        self.assertEqual(service.get_session(session.session_id).status, "waiting_remediation")

    def test_inspector_cannot_return_writable_or_inconsistent_report(self) -> None:
        for result in [
            {"read_only": False, "verdict": "passed", "issues": [], "evidence": []},
            {"read_only": True, "verdict": "passed", "issues": [{"issue_id": "i", "code": "X", "title": "X", "description": "X", "severity": "low", "evidence_ids": []}], "evidence": []},
            {"read_only": True, "verdict": "changes_required", "issues": [], "evidence": []},
        ]:
            with self.subTest(result=result):
                service, session = self.open(InspectionExecutor(result))
                handoff = service.submit_for_inspection(session.session_id, task_id="task-1", context_reference="contexts/task.json")
                with self.assertRaises(AgentCollaborationError): service.run_inspection(handoff.handoff_id)

    def test_inspection_evidence_rejects_nested_sensitive_metadata(self) -> None:
        for metadata in (
            {"access_token": "plaintext"},
            {"transport": {"headers": {"Authorization": "Bearer plaintext"}}},
            {"profiles": [{"client_secret": "plaintext"}]},
        ):
            result = {
                "read_only": True, "verdict": "passed", "issues": [],
                "evidence": [{
                    "evidence_id": "evidence-1", "kind": "test",
                    "reference": "results/test.xml", "metadata": metadata,
                }],
            }
            service, session = self.open(InspectionExecutor(result))
            handoff = service.submit_for_inspection(
                session.session_id, task_id="task-1", context_reference="contexts/task.json"
            )
            with self.subTest(metadata=metadata), self.assertRaisesRegex(
                AgentCollaborationError, "sensitive fields"
            ):
                service.run_inspection(handoff.handoff_id)

    def test_real_inspection_executor_and_safe_references_are_required(self) -> None:
        service, session = self.open(None)
        with self.assertRaises(AgentCollaborationError): service.submit_for_inspection(session.session_id, task_id="task-1", context_reference="../../secret")
        handoff = service.submit_for_inspection(session.session_id, task_id="task-1", context_reference="contexts/task.json")
        with self.assertRaisesRegex(AgentCollaborationError, "real inspection executor"):
            service.run_inspection(handoff.handoff_id)

    def test_issues_become_developer_remediation_on_original_task(self) -> None:
        scheduler = RemediationScheduler()
        executor = InspectionExecutor({"read_only": True, "verdict": "changes_required", "issues": [{"issue_id": "issue-1", "code": "X", "title": "X", "description": "X", "severity": "high", "evidence_ids": []}], "evidence": []})
        service, session = self.open(executor, scheduler)
        handoff = service.submit_for_inspection(session.session_id, task_id="inspection-task", context_reference="contexts/task.json")
        report = service.run_inspection(handoff.handoff_id)
        instruction = service.create_remediation(report.report_id)
        self.assertEqual(instruction.root_task_id, "task-1")
        self.assertEqual(instruction.developer_agent_id, self.developer.agent_id)
        self.assertEqual(instruction.issue_ids, ("issue-1",))
        self.assertEqual(scheduler.instructions, [instruction])
        self.assertEqual(service.get_session(session.session_id).remediation_round, 1)

    def test_cycle_routes_failed_inspection_back_to_main_developer(self) -> None:
        scheduler = RemediationScheduler()
        executor = InspectionExecutor({"read_only": True, "verdict": "changes_required", "issues": [{"issue_id": "issue-1", "code": "X", "title": "回归失败", "description": "修复回归", "severity": "high", "evidence_ids": []}], "evidence": []})
        service, session = self.open(executor, scheduler)
        handoff, report, remediation = service.run_cycle(session.session_id, task_id="task-1", context_reference="contexts/task.json")
        self.assertEqual(handoff.source_agent_id, self.developer.agent_id)
        self.assertEqual(report.inspector_agent_id, self.inspector.agent_id)
        self.assertIsNotNone(remediation)
        self.assertEqual(remediation.developer_agent_id, self.developer.agent_id)
        self.assertEqual(service.get_session(session.session_id).status, "active")

    def test_remediation_round_limit_requires_manual_takeover(self) -> None:
        scheduler = RemediationScheduler()
        executor = InspectionExecutor({"read_only": True, "verdict": "changes_required", "issues": [{"issue_id": "issue-1", "code": "X", "title": "X", "description": "X", "severity": "high", "evidence_ids": []}], "evidence": []})
        service, session = self.open(executor, scheduler, max_rounds=1)
        first = service.submit_for_inspection(session.session_id, task_id="task-1", context_reference="contexts/task.json")
        service.create_remediation(service.run_inspection(first.handoff_id).report_id)
        second = service.submit_for_inspection(session.session_id, task_id="task-1", context_reference="contexts/task-2.json")
        report = service.run_inspection(second.handoff_id)
        with self.assertRaisesRegex(AgentCollaborationError, "maximum remediation rounds"):
            service.create_remediation(report.report_id)
        self.assertEqual(service.get_session(session.session_id).status, "waiting_human")

    def test_collaboration_resources_are_owner_scoped(self) -> None:
        executor = InspectionExecutor({"read_only": True, "verdict": "passed", "issues": [], "evidence": []})
        service, session = self.open(executor)
        handoff = service.submit_for_inspection(session.session_id, task_id="task-1", context_reference="contexts/task.json")
        report = service.run_inspection(handoff.handoff_id)
        for operation in (
            lambda: service.require_owner(session.session_id, "tenant-1", "user-2"),
            lambda: service.require_owner(session.session_id, "tenant-2", "user-1"),
            lambda: service.require_handoff_owner(handoff.handoff_id, "tenant-1", "user-2"),
            lambda: service.require_report_owner(report.report_id, "tenant-1", "user-2"),
        ):
            with self.assertRaisesRegex(AgentCollaborationError, "not owned"):
                operation()
        self.assertEqual(service.require_owner(session.session_id, "tenant-1", "user-1").session_id, session.session_id)


if __name__ == "__main__": unittest.main()
