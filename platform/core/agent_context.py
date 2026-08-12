"""Project- and agent-isolated context storage."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from threading import RLock
from typing import Any, Mapping


class AgentContextError(ValueError):
    """Raised for missing or cross-scope agent context access."""


@dataclass(frozen=True, slots=True)
class AgentContext:
    tenant_id: str
    project_id: str
    agent_id: str
    values: Mapping[str, Any]


class AgentContextStore:
    def __init__(self) -> None:
        self._contexts: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._lock = RLock()

    def create(self, tenant_id: str, project_id: str, agent_id: str) -> AgentContext:
        key = self._key(tenant_id, project_id, agent_id)
        with self._lock:
            if key in self._contexts: raise AgentContextError("agent context already exists")
            self._contexts[key] = {}; return self.get(*key)

    def update(self, tenant_id: str, project_id: str, agent_id: str, values: Mapping[str, Any]) -> AgentContext:
        key = self._key(tenant_id, project_id, agent_id)
        if not isinstance(values,Mapping):raise AgentContextError("agent context values must be a mapping")
        if any(not str(name).strip() for name in values):raise AgentContextError("agent context keys must not be empty")
        if self._contains_sensitive_key(values):raise AgentContextError("agent context contains sensitive fields")
        with self._lock:
            try: context = self._contexts[key]
            except KeyError as error: raise AgentContextError("agent context does not exist in this scope") from error
            context.update(dict(values)); return self.get(*key)

    def get(self, tenant_id: str, project_id: str, agent_id: str) -> AgentContext:
        key = self._key(tenant_id, project_id, agent_id)
        with self._lock:
            try: values = self._contexts[key]
            except KeyError as error: raise AgentContextError("agent context does not exist in this scope") from error
            return AgentContext(*key, MappingProxyType(dict(values)))

    @staticmethod
    def _key(tenant_id: str, project_id: str, agent_id: str) -> tuple[str, str, str]:
        values = tuple(value.strip() for value in (tenant_id, project_id, agent_id))
        if not all(values):
            raise AgentContextError("tenant_id, project_id and agent_id are required")
        return values  # type: ignore[return-value]

    @staticmethod
    def _contains_sensitive_key(value: Any) -> bool:
        forbidden=("secret","token","password","api_key","authorization","credential")
        if isinstance(value,Mapping):return any(any(word in str(key).lower() for word in forbidden) or AgentContextStore._contains_sensitive_key(item) for key,item in value.items())
        if isinstance(value,(list,tuple,set,frozenset)):return any(AgentContextStore._contains_sensitive_key(item) for item in value)
        return False


@dataclass(frozen=True, slots=True)
class CollaborationContext:
    tenant_id: str
    project_id: str
    session_id: str
    developer_agent_id: str
    inspector_agent_id: str
    task_states: Mapping[str, str]
    evidence_references: tuple[str, ...]
    file_references: tuple[str, ...]


class CollaborationContextStore:
    """Scope-bound shared context where only the developer may mutate state."""

    def __init__(self) -> None:
        self._contexts: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._lock = RLock()

    def create(self, *, tenant_id: str, project_id: str, session_id: str, developer_agent_id: str, inspector_agent_id: str) -> CollaborationContext:
        key = self._key(tenant_id, project_id, session_id)
        developer_agent_id, inspector_agent_id = self._required(developer_agent_id, inspector_agent_id)
        with self._lock:
            if developer_agent_id == inspector_agent_id: raise AgentContextError("collaboration roles require distinct agents")
            if key in self._contexts: raise AgentContextError("collaboration context already exists")
            self._contexts[key] = {"developer_agent_id": developer_agent_id, "inspector_agent_id": inspector_agent_id, "task_states": {}, "evidence_references": [], "file_references": []}
            return self.get(*key, agent_id=developer_agent_id)

    def update(self, tenant_id: str, project_id: str, session_id: str, *, agent_id: str, task_states: Mapping[str, str] | None = None, evidence_references: tuple[str, ...] = (), file_references: tuple[str, ...] = ()) -> CollaborationContext:
        key = self._key(tenant_id, project_id, session_id)
        agent_id=self._required(agent_id)[0]
        if task_states is not None and not isinstance(task_states,Mapping):raise AgentContextError("collaboration task states must be a mapping")
        if isinstance(evidence_references,(str,bytes)) or not isinstance(evidence_references,tuple) or isinstance(file_references,(str,bytes)) or not isinstance(file_references,tuple):raise AgentContextError("collaboration references must be tuples")
        with self._lock:
            context = self._raw(key)
            if agent_id != context["developer_agent_id"]: raise AgentContextError("only the developer agent may mutate collaboration context")
            if task_states:
                if any(not str(task_id).strip() for task_id in task_states):raise AgentContextError("collaboration task identifiers are required")
                allowed = {"pending", "running", "waiting_inspection", "waiting_remediation", "waiting_human", "completed", "failed", "cancelled"}
                if any(state not in allowed for state in task_states.values()): raise AgentContextError("collaboration task state is invalid")
                context["task_states"].update(dict(task_states))
            context["evidence_references"].extend(self._references(evidence_references)); context["file_references"].extend(self._references(file_references))
            return self.get(*key, agent_id=agent_id)

    def get(self, tenant_id: str, project_id: str, session_id: str, *, agent_id: str) -> CollaborationContext:
        key = self._key(tenant_id, project_id, session_id)
        agent_id=self._required(agent_id)[0]
        with self._lock:
            context = self._raw(key)
            if agent_id not in {context["developer_agent_id"], context["inspector_agent_id"]}: raise AgentContextError("agent cannot access this collaboration context")
            return CollaborationContext(*key, context["developer_agent_id"], context["inspector_agent_id"], MappingProxyType(dict(context["task_states"])), tuple(context["evidence_references"]), tuple(context["file_references"]))

    def _raw(self, key: tuple[str, str, str]) -> dict[str, Any]:
        try: return self._contexts[key]
        except KeyError as error: raise AgentContextError("collaboration context does not exist in this scope") from error

    @classmethod
    def _key(cls, tenant_id: str, project_id: str, session_id: str) -> tuple[str, str, str]:
        return cls._required(tenant_id, project_id, session_id)  # type: ignore[return-value]

    @staticmethod
    def _required(*values: str) -> tuple[str, ...]:
        parsed = tuple(value.strip() for value in values)
        if not all(parsed): raise AgentContextError("collaboration scope identifiers are required")
        return parsed

    @staticmethod
    def _references(values: tuple[str, ...]) -> tuple[str, ...]:
        parsed = tuple(value.strip() for value in values)
        if any(not value or value.startswith("/") or ".." in value.split("/") or "\x00" in value for value in parsed):
            raise AgentContextError("collaboration references must be safe relative paths")
        return parsed
