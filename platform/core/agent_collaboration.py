"""Developer-to-inspector collaboration with immutable read-only inspection reports."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from threading import RLock
from typing import Any, Mapping, Protocol
from uuid import uuid4

from .agent_configuration import AgentConfigurationStore


class AgentCollaborationError(ValueError):
    """Raised when collaboration scope, role, or state rules are violated."""


@dataclass(frozen=True, slots=True)
class CollaborationEvidence:
    evidence_id: str
    kind: str
    reference: str
    metadata: Mapping[str, Any]
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CollaborationSession:
    session_id: str
    tenant_id: str
    created_by_identity_id: str
    project_id: str
    root_task_id: str
    developer_agent_id: str
    inspector_agent_id: str
    status: str
    remediation_round: int
    max_remediation_rounds: int
    created_at: str
    updated_at: str
    contract_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class TaskHandoff:
    handoff_id: str
    session_id: str
    task_id: str
    source_agent_id: str
    target_agent_id: str
    handoff_type: str
    status: str
    context_reference: str
    evidence: tuple[CollaborationEvidence, ...]
    created_at: str
    contract_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class InspectionIssue:
    issue_id: str
    code: str
    title: str
    description: str
    severity: str
    evidence_ids: tuple[str, ...]
    file_reference: str | None = None


@dataclass(frozen=True, slots=True)
class InspectionReport:
    report_id: str
    session_id: str
    handoff_id: str
    inspector_agent_id: str
    read_only: bool
    verdict: str
    issues: tuple[InspectionIssue, ...]
    evidence: tuple[CollaborationEvidence, ...]
    created_at: str
    contract_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class RemediationInstruction:
    instruction_id: str
    session_id: str
    report_id: str
    developer_agent_id: str
    root_task_id: str
    issue_ids: tuple[str, ...]
    remediation_round: int
    status: str
    created_at: str
    contract_version: str = "1.0"


class InspectionExecutor(Protocol):
    def inspect(self, handoff: TaskHandoff) -> Mapping[str, Any]: ...


class RemediationScheduler(Protocol):
    def schedule_remediation(self, instruction: RemediationInstruction) -> Any: ...


class AgentCollaborationService:
    SESSION_STATUSES = frozenset({"active", "paused", "waiting_inspection", "waiting_remediation", "waiting_human", "completed", "failed", "cancelled"})
    VERDICTS = frozenset({"passed", "changes_required", "blocked"})
    SEVERITIES = frozenset({"blocker", "high", "medium", "low"})
    EVIDENCE_KINDS = frozenset({"file", "test", "log", "artifact"})

    def __init__(self, configurations: AgentConfigurationStore, inspection_executor: InspectionExecutor | None, remediation_scheduler: RemediationScheduler | None = None) -> None:
        self.configurations = configurations
        self.inspection_executor = inspection_executor
        self.remediation_scheduler = remediation_scheduler
        self._sessions: dict[str, CollaborationSession] = {}
        self._handoffs: dict[str, TaskHandoff] = {}
        self._reports: dict[str, InspectionReport] = {}
        self._instructions: dict[str, RemediationInstruction] = {}
        self._lock = RLock()
        self._active_handoffs: set[str] = set()
        self._active_reports: set[str] = set()

    def open_session(self, *, tenant_id: str, created_by_identity_id: str, project_id: str, root_task_id: str, developer_agent_id: str, inspector_agent_id: str, max_remediation_rounds: int = 3) -> CollaborationSession:
        tenant_id, created_by_identity_id, project_id, root_task_id = self._required(tenant_id, created_by_identity_id, project_id, root_task_id)
        developer = self.configurations.get(developer_agent_id)
        inspector = self.configurations.get(inspector_agent_id)
        if developer.role != "developer" or not developer.writable:
            raise AgentCollaborationError("developer agent must have writable developer configuration")
        if inspector.role != "inspector" or inspector.writable:
            raise AgentCollaborationError("inspector agent must have read-only inspector configuration")
        if not 1 <= max_remediation_rounds <= 100:
            raise AgentCollaborationError("max_remediation_rounds must be between 1 and 100")
        now = self._now()
        session = CollaborationSession(f"collaboration-{uuid4().hex}", tenant_id, created_by_identity_id, project_id, root_task_id, developer_agent_id, inspector_agent_id, "active", 0, max_remediation_rounds, now, now)
        with self._lock:self._sessions[session.session_id] = session
        return session

    def submit_for_inspection(self, session_id: str, *, task_id: str, context_reference: str, evidence: tuple[Mapping[str, Any], ...] = ()) -> TaskHandoff:
        task_id = self._required(task_id)[0]
        parsed_evidence = tuple(self._evidence(item) for item in evidence)
        reference = self._safe_reference(context_reference)
        with self._lock:
            session = self.get_session(session_id)
            if session.status not in {"active", "waiting_remediation"}:raise AgentCollaborationError("session cannot submit inspection in its current state")
            handoff_type = "submit_for_inspection" if session.remediation_round == 0 else "resubmit_for_inspection"
            handoff = TaskHandoff(f"handoff-{uuid4().hex}", session_id, task_id, session.developer_agent_id, session.inspector_agent_id, handoff_type, "pending", reference, parsed_evidence, self._now())
            self._handoffs[handoff.handoff_id] = handoff;self._sessions[session_id] = replace(session, status="waiting_inspection", updated_at=self._now());return handoff

    def run_inspection(self, handoff_id: str) -> InspectionReport:
        with self._lock:
            handoff = self.get_handoff(handoff_id);session = self.get_session(handoff.session_id)
            if handoff_id in self._active_handoffs:raise AgentCollaborationError("handoff inspection is already active")
            if session.status != "waiting_inspection" or handoff.status != "pending":raise AgentCollaborationError("handoff is not pending inspection")
            self._active_handoffs.add(handoff_id)
        if self.inspection_executor is None:
            with self._lock:self._active_handoffs.discard(handoff_id)
            raise AgentCollaborationError("real inspection executor is not configured")
        try:
            raw = self.inspection_executor.inspect(handoff);report = self._report(handoff, raw)
            with self._lock:
                self._reports[report.report_id] = report;self._handoffs[handoff_id] = replace(handoff, status="completed")
                target_status = "completed" if report.verdict == "passed" else "waiting_remediation" if report.verdict == "changes_required" else "waiting_human"
                self._sessions[session.session_id] = replace(session, status=target_status, updated_at=self._now())
            return report
        finally:
            with self._lock:self._active_handoffs.discard(handoff_id)

    def create_remediation(self, report_id: str) -> RemediationInstruction:
        with self._lock:
            report = self.get_report(report_id);session = self.get_session(report.session_id)
            if report_id in self._active_reports:raise AgentCollaborationError("report remediation is already active")
            if report.verdict != "changes_required" or session.status != "waiting_remediation":raise AgentCollaborationError("inspection report does not require remediation")
            self._active_reports.add(report_id)
        try:return self._create_remediation_active(report, session)
        finally:
            with self._lock:self._active_reports.discard(report_id)

    def _create_remediation_active(self, report: InspectionReport, session: CollaborationSession) -> RemediationInstruction:
        next_round = session.remediation_round + 1
        if next_round > session.max_remediation_rounds:
            with self._lock:self._sessions[session.session_id] = replace(session, status="waiting_human", updated_at=self._now())
            raise AgentCollaborationError("maximum remediation rounds reached; manual takeover required")
        if self.remediation_scheduler is None:
            raise AgentCollaborationError("remediation scheduler is not configured")
        instruction = RemediationInstruction(
            f"remediation-{uuid4().hex}", session.session_id, report.report_id,
            session.developer_agent_id, session.root_task_id,
            tuple(issue.issue_id for issue in report.issues), next_round, "pending", self._now(),
        )
        self.remediation_scheduler.schedule_remediation(instruction)
        with self._lock:self._instructions[instruction.instruction_id] = instruction;self._sessions[session.session_id] = replace(session, remediation_round=next_round, status="active", updated_at=self._now())
        return instruction

    def run_cycle(self, session_id: str, *, task_id: str, context_reference: str, evidence: tuple[Mapping[str, Any], ...] = ()) -> tuple[TaskHandoff, InspectionReport, RemediationInstruction | None]:
        """Run one developer-to-inspector gate and route failures back to the developer."""
        handoff = self.submit_for_inspection(session_id, task_id=task_id, context_reference=context_reference, evidence=evidence)
        report = self.run_inspection(handoff.handoff_id)
        remediation = self.create_remediation(report.report_id) if report.verdict == "changes_required" else None
        return handoff, report, remediation

    def get_session(self, session_id: str) -> CollaborationSession:
        with self._lock:
            try: return self._sessions[session_id]
            except KeyError as error: raise AgentCollaborationError(f"unknown collaboration session: {session_id}") from error

    def require_owner(self, session_id: str, tenant_id: str, identity_id: str) -> CollaborationSession:
        tenant_id, identity_id = self._required(tenant_id, identity_id)
        session = self.get_session(session_id)
        if (session.tenant_id, session.created_by_identity_id) != (tenant_id, identity_id):
            raise AgentCollaborationError("collaboration session is not owned by identity")
        return session

    def require_handoff_owner(self, handoff_id: str, tenant_id: str, identity_id: str) -> TaskHandoff:
        handoff = self.get_handoff(handoff_id)
        self.require_owner(handoff.session_id, tenant_id, identity_id)
        return handoff

    def require_report_owner(self, report_id: str, tenant_id: str, identity_id: str) -> InspectionReport:
        report = self.get_report(report_id)
        self.require_owner(report.session_id, tenant_id, identity_id)
        return report

    def get_handoff(self, handoff_id: str) -> TaskHandoff:
        with self._lock:
            try: return self._handoffs[handoff_id]
            except KeyError as error: raise AgentCollaborationError(f"unknown task handoff: {handoff_id}") from error

    def get_report(self, report_id: str) -> InspectionReport:
        with self._lock:
            try: return self._reports[report_id]
            except KeyError as error: raise AgentCollaborationError(f"unknown inspection report: {report_id}") from error

    def get_instruction(self, instruction_id: str) -> RemediationInstruction:
        with self._lock:
            try: return self._instructions[instruction_id]
            except KeyError as error: raise AgentCollaborationError(f"unknown remediation instruction: {instruction_id}") from error

    def instructions(self, session_id: str) -> tuple[RemediationInstruction, ...]:
        with self._lock:self.get_session(session_id);return tuple(item for item in self._instructions.values() if item.session_id == session_id)

    def handoffs(self, session_id: str) -> tuple[TaskHandoff, ...]:
        with self._lock:self.get_session(session_id);return tuple(item for item in self._handoffs.values() if item.session_id == session_id)

    def reports(self, session_id: str) -> tuple[InspectionReport, ...]:
        with self._lock:self.get_session(session_id);return tuple(item for item in self._reports.values() if item.session_id == session_id)

    def _report(self, handoff: TaskHandoff, raw: Mapping[str, Any]) -> InspectionReport:
        if not isinstance(raw, Mapping):
            raise AgentCollaborationError("inspection executor returned invalid report")
        if raw.get("read_only") is not True:
            raise AgentCollaborationError("inspection report must be read-only")
        verdict = raw.get("verdict")
        if verdict not in self.VERDICTS:
            raise AgentCollaborationError("inspection verdict is invalid")
        raw_issues = raw.get("issues", [])
        raw_evidence = raw.get("evidence", [])
        if not isinstance(raw_issues, (list, tuple)) or not isinstance(raw_evidence, (list, tuple)):
            raise AgentCollaborationError("inspection issues and evidence must be arrays")
        evidence = tuple(self._evidence(item) for item in raw_evidence)
        evidence_ids = {item.evidence_id for item in evidence}
        issues = tuple(self._issue(item, evidence_ids) for item in raw_issues)
        if verdict == "passed" and issues:
            raise AgentCollaborationError("passed inspection cannot contain issues")
        if verdict != "passed" and not issues:
            raise AgentCollaborationError("non-passing inspection requires issues")
        return InspectionReport(f"report-{uuid4().hex}", handoff.session_id, handoff.handoff_id, handoff.target_agent_id, True, str(verdict), issues, evidence, self._now())

    def _issue(self, raw: Any, evidence_ids: set[str]) -> InspectionIssue:
        if not isinstance(raw, Mapping): raise AgentCollaborationError("inspection issue is invalid")
        issue_id, code, title, description = self._required(str(raw.get("issue_id", "")), str(raw.get("code", "")), str(raw.get("title", "")), str(raw.get("description", "")))
        severity = raw.get("severity")
        if severity not in self.SEVERITIES: raise AgentCollaborationError("inspection issue severity is invalid")
        raw_ids = raw.get("evidence_ids", [])
        if not isinstance(raw_ids, (list, tuple)) or not all(isinstance(item, str) and item for item in raw_ids): raise AgentCollaborationError("inspection issue evidence_ids are invalid")
        if not set(raw_ids).issubset(evidence_ids): raise AgentCollaborationError("inspection issue references unknown evidence")
        file_reference = raw.get("file_reference")
        if file_reference is not None: file_reference = self._safe_reference(str(file_reference))
        return InspectionIssue(issue_id, code, title, description, str(severity), tuple(raw_ids), file_reference)

    def _evidence(self, raw: Any) -> CollaborationEvidence:
        if not isinstance(raw, Mapping): raise AgentCollaborationError("collaboration evidence is invalid")
        evidence_id, kind = self._required(str(raw.get("evidence_id", "")), str(raw.get("kind", "")))
        if kind not in self.EVIDENCE_KINDS: raise AgentCollaborationError("collaboration evidence kind is invalid")
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, Mapping): raise AgentCollaborationError("collaboration evidence metadata is invalid")
        if self._contains_sensitive_key(metadata):
            raise AgentCollaborationError("collaboration evidence metadata contain sensitive fields")
        sha256 = raw.get("sha256")
        if sha256 is not None and (not isinstance(sha256, str) or len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256)):
            raise AgentCollaborationError("collaboration evidence sha256 is invalid")
        return CollaborationEvidence(evidence_id, kind, self._safe_reference(str(raw.get("reference", ""))), MappingProxyType(dict(metadata)), sha256)

    @staticmethod
    def _contains_sensitive_key(value: Any) -> bool:
        forbidden = ("secret", "token", "password", "api_key", "authorization", "credential")
        if isinstance(value, Mapping):
            return any(
                any(word in str(key).lower() for word in forbidden)
                or AgentCollaborationService._contains_sensitive_key(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple, set, frozenset)):
            return any(AgentCollaborationService._contains_sensitive_key(item) for item in value)
        return False

    @staticmethod
    def _safe_reference(value: str) -> str:
        reference = value.strip()
        if not reference or reference.startswith("/") or "\x00" in reference or ".." in reference.split("/"):
            raise AgentCollaborationError("collaboration reference must be a safe relative path")
        return reference

    @staticmethod
    def _required(*values: str) -> tuple[str, ...]:
        parsed = tuple(value.strip() for value in values)
        if not all(parsed): raise AgentCollaborationError("required collaboration identifier is missing")
        return parsed

    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()
