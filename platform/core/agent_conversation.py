"""Model-driven agent conversations with confirmable configuration and task proposals."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Any, Mapping, Protocol
from uuid import uuid4

from ai_agent_discovery import AgentInstance, SkillDefinition
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry, ModelRequirements

from .agent_configuration import AgentConfiguration, AgentConfigurationStore


class ConversationError(ValueError): pass


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    message_id: str
    session_id: str
    agent_id: str
    role: str
    content: str
    created_at: str
    contract_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class ConversationProposal:
    proposal_id: str
    session_id: str
    agent_id: str
    proposal_type: str
    status: str
    requested_changes: Mapping[str, Any]
    requires_confirmation: bool
    created_at: str
    applied_result: Mapping[str, Any] | None = None
    contract_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class ConversationSession:
    session_id: str
    agent_id: str
    configuration_version: int
    created_by_identity_id: str
    created_at: str
    context: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))


class ModelConversationClient(Protocol):
    def complete(self, model: ModelDefinition, messages: tuple[ConversationMessage, ...], response_schema: Mapping[str, Any]) -> Mapping[str, Any]: ...


class TaskProposalExecutor(Protocol):
    def execute(self, configuration: AgentConfiguration, requested_changes: Mapping[str, Any], confirmed_by_identity_id: str) -> Mapping[str, Any]: ...


class ConversationMemoryStore:
    """Tenant-safe conversational facts explicitly returned by the model."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path
        self._lock = RLock()
        self._items: dict[tuple[str, str], dict[str, Any]] = {}
        if storage_path and storage_path.exists():
            raw = json.loads(storage_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict): raise ConversationError("conversation memory file is invalid")
            for key, values in raw.items():
                if "\u0000" not in key or not isinstance(values, dict): raise ConversationError("conversation memory entry is invalid")
                identity_id, project_id = key.split("\u0000", 1)
                self._items[(identity_id, project_id)] = dict(values)

    def read(self, identity_id: str, project_id: str = "") -> Mapping[str, Any]:
        if not identity_id.strip() or not project_id.strip(): raise ConversationError("conversation memory identity and project are required")
        with self._lock: return MappingProxyType(dict(self._items.get((identity_id, project_id), {})))

    def update(self, identity_id: str, project_id: str, values: Mapping[str, Any]) -> Mapping[str, Any]:
        if not identity_id.strip() or not project_id.strip(): raise ConversationError("conversation memory identity and project are required")
        safe = {str(key): value for key, value in values.items() if str(key).strip() and value is not None}
        with self._lock:
            current = self._items.setdefault((identity_id, project_id), {}); current.update(safe)
            if self.storage_path:
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
                payload = {f"{owner}\u0000{project}": item for (owner, project), item in self._items.items()}
                temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
                temporary.replace(self.storage_path)
            return MappingProxyType(dict(current))


class AgentConversationService:
    RESPONSE_SCHEMA = MappingProxyType({
        "type": "object", "required": ["reply"],
        "properties": {
            "reply": {"type": "string"},
            "understanding": {"type": "string"},
            "needs_clarification": {"type": "boolean"},
            "selected_skill_id": {"type": ["string", "null"]},
            "plan": {"type": "array", "items": {"type": "string"}},
            "memory_updates": {"type": "object"},
            "proposal": {"type": ["object", "null"], "properties": {
                "proposal_type": {"enum": ["configuration_change", "task_execution", "industry_workflow"]},
                "requested_changes": {"type": "object"},
            }},
        },
    })

    def __init__(self, models: ModelRegistry, configurations: AgentConfigurationStore, model_client: ModelConversationClient | None, task_executor: TaskProposalExecutor | None = None, workflow_executor: TaskProposalExecutor | None = None, memory_store: ConversationMemoryStore | None = None) -> None:
        self.models = models
        self.configurations = configurations
        self.model_client = model_client
        self.task_executor = task_executor
        self.workflow_executor = workflow_executor
        self.memory_store = memory_store or ConversationMemoryStore()
        self._sessions: dict[str, ConversationSession] = {}
        self._messages: dict[str, list[ConversationMessage]] = {}
        self._proposals: dict[str, ConversationProposal] = {}
        self._bindings: dict[str, tuple[AgentInstance, SkillDefinition]] = {}
        self._lock = RLock()
        self._active_sessions: set[str] = set()
        self._active_proposals: set[str] = set()

    def bind(self, agent: AgentInstance, skill: SkillDefinition) -> None:
        if agent.skill_id != skill.skill_id: raise ConversationError("agent does not belong to Skill")
        with self._lock:self._bindings[agent.agent_id] = (agent, skill)

    def open_session(self, agent_id: str, created_by_identity_id: str, context: Mapping[str, Any] | None = None) -> ConversationSession:
        configuration = self.configurations.get(agent_id)
        identity_id = created_by_identity_id.strip()
        if not identity_id: raise ConversationError("created_by_identity_id is required")
        safe_context = MappingProxyType({str(key): value for key, value in (context or {}).items() if str(key).strip() and value is not None})
        if not str(safe_context.get("project_id") or "").strip(): raise ConversationError("conversation project_id is required")
        session = ConversationSession(f"conversation-{uuid4().hex}", agent_id, configuration.configuration_version, identity_id, self._now(), safe_context)
        agent, skill = self._binding(agent_id)
        memory = self.memory_store.read(identity_id, str(safe_context.get("project_id", "")))
        system = self._message(session, "system", self._system_prompt(configuration, agent, skill, safe_context, memory))
        with self._lock:self._sessions[session.session_id] = session;self._messages[session.session_id] = [system]
        return session

    def send(self, session_id: str, content: str, identity_id: str) -> tuple[ConversationMessage, ConversationProposal | None]:
        with self._lock:
            session = self._owned_session(session_id, identity_id)
            if session_id in self._active_sessions:raise ConversationError("conversation session is already active")
            self._active_sessions.add(session_id)
        text = content.strip()
        try:return self._send_active(session, text)
        finally:
            with self._lock:self._active_sessions.discard(session_id)

    def _send_active(self, session: ConversationSession, text: str) -> tuple[ConversationMessage, ConversationProposal | None]:
        if not text: raise ConversationError("conversation content is required")
        if self.model_client is None: raise ConversationError("real conversation model client is not configured")
        configuration = self.configurations.get(session.agent_id);session_id=session.session_id
        model = self.models.select(ModelRequirements(frozenset({"chat", "structured_output"})), preferred_model_id=configuration.model_id)
        with self._lock:self._messages[session_id].append(self._message(session, "user", text));messages=tuple(self._messages[session_id])
        raw = self.model_client.complete(model, messages, self.RESPONSE_SCHEMA)
        reply = raw.get("reply")
        if not isinstance(reply, str) or not reply.strip(): raise ConversationError("model response reply is invalid")
        assistant = self._message(session, "assistant", reply.strip())
        with self._lock:self._messages[session_id].append(assistant)
        memory_updates = raw.get("memory_updates")
        if isinstance(memory_updates, Mapping) and memory_updates:
            self.memory_store.update(session.created_by_identity_id, str(session.context.get("project_id", "")), memory_updates)
        needs_clarification = raw.get("needs_clarification", False)
        if not isinstance(needs_clarification, bool): raise ConversationError("model clarification control is invalid")
        selected_skill_id = raw.get("selected_skill_id")
        if selected_skill_id is not None and selected_skill_id != self._binding(session.agent_id)[1].skill_id:
            raise ConversationError("model selected an unavailable Skill")
        if needs_clarification and raw.get("proposal") is not None:
            raise ConversationError("clarification response cannot create a proposal")
        plan = raw.get("plan", [])
        if not isinstance(plan, list) or any(not isinstance(step, str) or not step.strip() for step in plan):
            raise ConversationError("model execution plan is invalid")
        return assistant, self._proposal_from_model(session, configuration, raw.get("proposal"), tuple(plan))

    @staticmethod
    def _system_prompt(configuration: AgentConfiguration, agent: AgentInstance, skill: SkillDefinition, context: Mapping[str, Any], memory: Mapping[str, Any]) -> str:
        skill_prompt = ""
        prompt_file = skill.metadata.get("system_prompt_file")
        if isinstance(prompt_file, str) and prompt_file.strip():
            prompt_path = (skill.manifest_path.parent / prompt_file).resolve()
            if not prompt_path.is_relative_to(skill.manifest_path.parent.resolve()) or not prompt_path.is_file():
                raise ConversationError("Skill system prompt file is invalid")
            skill_prompt = prompt_path.read_text(encoding="utf-8").strip()
        return (
            "你是可执行任务的专业 AI 机器人。先理解用户真正目标，再结合上下文回答。"
            "信息足够时直接完成；只有缺失信息会实质改变结果时才提出一个简短问题。"
            "复杂任务先形成可执行计划，选择当前 Skill 能力并持续推进；不得伪造工具结果。"
            "普通只读操作可直接执行，配置变更、写操作和高风险操作必须生成可确认提案。"
            "回复使用用户语言，先给结论，避免机械复述和关键词式答复。"
            f"\nSkill 专属规范：\n{skill_prompt}\n"
            f"agent={agent.name}; skill_id={skill.skill_id}; plugin={getattr(skill, 'plugin_id', 'industry')}; role={configuration.role}; "
            f"writable={str(configuration.writable).lower()}; permissions={list(skill.metadata.get('permissions', []))}; "
            f"context={dict(context)}; memory={dict(memory)}; return structured output"
        )

    def confirm(self, proposal_id: str, confirmed_by_identity_id: str) -> ConversationProposal:
        with self._lock:
            proposal = self._proposal(proposal_id)
            if proposal_id in self._active_proposals:raise ConversationError("proposal is already active")
            self._active_proposals.add(proposal_id)
        try:return self._confirm_active(proposal, confirmed_by_identity_id)
        finally:
            with self._lock:self._active_proposals.discard(proposal_id)

    def _confirm_active(self, proposal: ConversationProposal, confirmed_by_identity_id: str) -> ConversationProposal:
        identity_id = confirmed_by_identity_id.strip()
        if not identity_id: raise ConversationError("confirmed_by_identity_id is required")
        self._owned_session(proposal.session_id, identity_id)
        if proposal.status != "pending_confirmation": raise ConversationError("proposal is not pending confirmation")
        configuration = self.configurations.get(proposal.agent_id)
        try:
            if proposal.proposal_type == "configuration_change":
                agent, skill = self._binding(proposal.agent_id)
                if set(proposal.requested_changes) - {"model_id", "settings"}: raise ConversationError("configuration proposal contains forbidden fields")
                updated = self.configurations.update(
                    proposal.agent_id, expected_version=configuration.configuration_version,
                    updated_by_identity_id=identity_id, model_id=proposal.requested_changes.get("model_id"),
                    settings=proposal.requested_changes.get("settings"), skill=skill, agent=agent,
                )
                result: Mapping[str, Any] = {"configuration_version": updated.configuration_version}
            else:
                executor = self.workflow_executor if proposal.proposal_type == "industry_workflow" else self.task_executor
                if executor is None: raise ConversationError("real proposal executor is not configured")
                result = executor.execute(configuration, proposal.requested_changes, identity_id)
                if not result: raise ConversationError("task executor returned no result")
        except Exception:
            with self._lock:self._proposals[proposal.proposal_id] = replace(proposal, status="failed")
            raise
        applied = replace(proposal, status="applied", applied_result=MappingProxyType(dict(result)))
        with self._lock:self._proposals[proposal.proposal_id] = applied
        return applied

    def reject(self, proposal_id: str, rejected_by_identity_id: str) -> ConversationProposal:
        with self._lock:
            proposal = self._proposal(proposal_id);self._owned_session(proposal.session_id, rejected_by_identity_id)
            if proposal_id in self._active_proposals:raise ConversationError("proposal is already active")
            if proposal.status != "pending_confirmation": raise ConversationError("proposal is not pending confirmation")
            rejected = replace(proposal, status="rejected"); self._proposals[proposal_id] = rejected; return rejected

    def messages(self, session_id: str, identity_id: str) -> tuple[ConversationMessage, ...]:
        with self._lock:self._owned_session(session_id, identity_id); return tuple(self._messages[session_id])

    def proposals(self, session_id: str, identity_id: str) -> tuple[ConversationProposal, ...]:
        with self._lock:self._owned_session(session_id, identity_id); return tuple(item for item in self._proposals.values() if item.session_id == session_id)

    def _owned_session(self, session_id: str, identity_id: str) -> ConversationSession:
        owner = identity_id.strip()
        if not owner: raise ConversationError("identity_id is required")
        session = self._session(session_id)
        if session.created_by_identity_id != owner: raise ConversationError("conversation session is not owned by identity")
        return session

    def _proposal_from_model(self, session: ConversationSession, configuration: AgentConfiguration, raw: Any, plan: tuple[str, ...] = ()) -> ConversationProposal | None:
        if raw is None: return None
        if not isinstance(raw, Mapping): raise ConversationError("model proposal is invalid")
        proposal_type, requested = raw.get("proposal_type"), raw.get("requested_changes")
        if proposal_type not in {"configuration_change", "task_execution", "industry_workflow"}: raise ConversationError("model proposal_type is invalid")
        if not isinstance(requested, Mapping) or not requested: raise ConversationError("model requested_changes are invalid")
        requested = dict(requested)
        if plan and "plan" not in requested: requested["plan"] = list(plan)
        if configuration.role in {"tester", "inspector"} and proposal_type == "task_execution" and requested.get("read_only") is not True:
            raise ConversationError(f"{configuration.role} task proposal must be read-only")
        proposal = ConversationProposal(f"proposal-{uuid4().hex}", session.session_id, session.agent_id, str(proposal_type), "pending_confirmation", MappingProxyType(dict(requested)), True, self._now())
        with self._lock:self._proposals[proposal.proposal_id] = proposal
        return proposal

    def _message(self, session: ConversationSession, role: str, content: str) -> ConversationMessage:
        return ConversationMessage(f"message-{uuid4().hex}", session.session_id, session.agent_id, role, content, self._now())

    def _session(self, session_id: str) -> ConversationSession:
        with self._lock:
            try: return self._sessions[session_id]
            except KeyError as error: raise ConversationError(f"unknown conversation session: {session_id}") from error

    def _proposal(self, proposal_id: str) -> ConversationProposal:
        with self._lock:
            try: return self._proposals[proposal_id]
            except KeyError as error: raise ConversationError(f"unknown proposal: {proposal_id}") from error

    def _binding(self, agent_id: str) -> tuple[AgentInstance, SkillDefinition]:
        with self._lock:
            try: return self._bindings[agent_id]
            except KeyError as error: raise ConversationError("agent Skill binding is not configured") from error

    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()
