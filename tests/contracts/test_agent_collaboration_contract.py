from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "shared/contracts/agent-collaboration.schema.json").read_text())


def validate(name: str, value: dict) -> list:
    validator = Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]}, format_checker=FormatChecker())
    return list(validator.iter_errors(value))


NOW = "2026-08-07T12:00:00Z"
EVIDENCE = {"evidence_id": "evidence-1", "kind": "test", "reference": "tests/results.xml", "metadata": {"passed": 12}}


class AgentCollaborationContractTest(unittest.TestCase):
    def test_valid_collaboration_contracts(self) -> None:
        cases = [
            ("session", {"session_id": "session-1", "tenant_id": "tenant-1", "project_id": "project-1", "root_task_id": "task-1", "developer_agent_id": "developer-1", "inspector_agent_id": "inspector-1", "status": "waiting_inspection", "remediation_round": 0, "max_remediation_rounds": 3, "created_at": NOW, "updated_at": NOW, "contract_version": "1.0"}),
            ("handoff", {"handoff_id": "handoff-1", "session_id": "session-1", "task_id": "task-1", "source_agent_id": "developer-1", "target_agent_id": "inspector-1", "handoff_type": "submit_for_inspection", "status": "pending", "context_reference": "contexts/session-1.json", "evidence": [EVIDENCE], "created_at": NOW, "contract_version": "1.0"}),
            ("report", {"report_id": "report-1", "session_id": "session-1", "handoff_id": "handoff-1", "inspector_agent_id": "inspector-1", "read_only": True, "verdict": "changes_required", "issues": [{"issue_id": "issue-1", "code": "TEST_FAILURE", "title": "测试失败", "description": "修复失败测试", "severity": "high", "file_reference": "tests/test_example.py", "evidence_ids": ["evidence-1"]}], "evidence": [EVIDENCE], "created_at": NOW, "contract_version": "1.0"}),
            ("remediationInstruction", {"instruction_id": "instruction-1", "session_id": "session-1", "report_id": "report-1", "developer_agent_id": "developer-1", "root_task_id": "task-1", "issue_ids": ["issue-1"], "remediation_round": 1, "status": "pending", "created_at": NOW, "contract_version": "1.0"}),
        ]
        for name, value in cases:
            with self.subTest(contract=name):
                self.assertFalse(validate(name, value))

    def test_inspection_report_is_read_only_and_verdict_is_consistent(self) -> None:
        report = {"report_id": "report-1", "session_id": "session-1", "handoff_id": "handoff-1", "inspector_agent_id": "inspector-1", "read_only": True, "verdict": "passed", "issues": [], "evidence": [], "created_at": NOW, "contract_version": "1.0"}
        self.assertTrue(validate("report", {**report, "read_only": False}))
        self.assertTrue(validate("report", {**report, "verdict": "changes_required"}))
        self.assertTrue(validate("report", {**report, "issues": [{"issue_id": "issue-1", "code": "X", "title": "X", "description": "X", "severity": "low", "evidence_ids": []}]}))

    def test_references_reject_absolute_and_parent_paths(self) -> None:
        handoff = {"handoff_id": "handoff-1", "session_id": "session-1", "task_id": "task-1", "source_agent_id": "developer-1", "target_agent_id": "inspector-1", "handoff_type": "submit_for_inspection", "status": "pending", "context_reference": "contexts/session-1.json", "evidence": [], "created_at": NOW, "contract_version": "1.0"}
        self.assertTrue(validate("handoff", {**handoff, "context_reference": "/etc/passwd"}))
        self.assertTrue(validate("handoff", {**handoff, "context_reference": "contexts/../../secret"}))

    def test_remediation_loop_has_finite_limit(self) -> None:
        session = {"session_id": "session-1", "tenant_id": "tenant-1", "project_id": "project-1", "root_task_id": "task-1", "developer_agent_id": "developer-1", "inspector_agent_id": "inspector-1", "status": "active", "remediation_round": 0, "max_remediation_rounds": 3, "created_at": NOW, "updated_at": NOW, "contract_version": "1.0"}
        self.assertTrue(validate("session", {**session, "max_remediation_rounds": 0}))
        self.assertTrue(validate("session", {**session, "max_remediation_rounds": 101}))


if __name__ == "__main__":
    unittest.main()
