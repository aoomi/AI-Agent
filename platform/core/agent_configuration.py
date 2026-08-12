"""Versioned agent configuration with immutable role permissions and model binding."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from threading import RLock
from typing import Any, Mapping
from uuid import uuid4

from ai_agent_discovery import AgentInstance, SkillDefinition
from ai_agent_llm_gateway import ModelDefinition, ModelRegistry, ModelRequirements


class AgentConfigurationError(ValueError):
    """Raised when an agent configuration violates version or permission rules."""


@dataclass(frozen=True, slots=True)
class AgentConfiguration:
    configuration_id: str
    configuration_version: int
    agent_id: str
    skill_id: str
    role: str
    model_id: str
    system_prompt_version: str
    settings: Mapping[str, Any]
    writable: bool
    updated_by_identity_id: str
    updated_at: str
    contract_version: str = "1.0"


class AgentConfigurationStore:
    def __init__(self, models: ModelRegistry) -> None:
        self._models = models
        self._history: dict[str, list[AgentConfiguration]] = {}
        self._lock = RLock()

    def create(
        self,
        *,
        agent: AgentInstance,
        skill: SkillDefinition,
        model_id: str,
        updated_by_identity_id: str,
        settings: Mapping[str, Any] | None = None,
    ) -> AgentConfiguration:
        with self._lock:
            if agent.agent_id in self._history:
                raise AgentConfigurationError(f"configuration already exists: {agent.agent_id}")
            self._validate_agent_skill(agent, skill)
            model = self._resolve_model(skill, model_id)
            configuration = self._build(
                configuration_id=f"agent-config-{uuid4().hex}", version=1, agent=agent, skill=skill,
                model=model, updated_by_identity_id=updated_by_identity_id, settings=settings or {},
            )
            self._history[agent.agent_id] = [configuration]
            return configuration

    def update(
        self,
        agent_id: str,
        *,
        expected_version: int,
        updated_by_identity_id: str,
        model_id: str | None = None,
        settings: Mapping[str, Any] | None = None,
        skill: SkillDefinition,
        agent: AgentInstance,
    ) -> AgentConfiguration:
        with self._lock:
            current = self.get(agent_id)
            if current.configuration_version != expected_version:
                raise AgentConfigurationError("configuration version conflict")
            self._validate_agent_skill(agent, skill)
            if current.skill_id != skill.skill_id or current.role != skill.metadata.get("agent_role"):
                raise AgentConfigurationError("agent role and Skill binding are immutable")
            model = self._resolve_model(skill, model_id or current.model_id)
            configuration = self._build(
                configuration_id=current.configuration_id, version=current.configuration_version + 1,
                agent=agent, skill=skill, model=model, updated_by_identity_id=updated_by_identity_id,
                settings=current.settings if settings is None else settings,
            )
            self._history[agent_id].append(configuration)
            return configuration

    def get(self, agent_id: str, version: int | None = None) -> AgentConfiguration:
        with self._lock:
            try: history = self._history[agent_id]
            except KeyError as error: raise AgentConfigurationError(f"unknown agent configuration: {agent_id}") from error
            if version is None: return history[-1]
            try: return next(item for item in history if item.configuration_version == version)
            except StopIteration as error: raise AgentConfigurationError(f"unknown configuration version: {version}") from error

    def history(self, agent_id: str) -> tuple[AgentConfiguration, ...]:
        with self._lock:
            self.get(agent_id)
            return tuple(self._history[agent_id])

    def _resolve_model(self, skill: SkillDefinition, model_id: str) -> ModelDefinition:
        raw_capabilities = skill.metadata.get("required_model_capabilities")
        if not isinstance(raw_capabilities, list) or not all(
            isinstance(value, str) for value in raw_capabilities
        ):
            raise AgentConfigurationError("Skill model capabilities are invalid")
        return self._models.select(
            ModelRequirements(frozenset(raw_capabilities)), preferred_model_id=model_id
        )

    @staticmethod
    def _validate_agent_skill(agent: AgentInstance, skill: SkillDefinition) -> None:
        if agent.skill_id != skill.skill_id:
            raise AgentConfigurationError("agent does not belong to Skill")
        role = skill.metadata.get("agent_role")
        if role not in {"developer", "tester", "inspector"}:
            raise AgentConfigurationError("Skill agent_role is invalid")
        permissions = skill.metadata.get("permissions")
        if not isinstance(permissions, list):
            raise AgentConfigurationError("Skill permissions are invalid")
        if role in {"tester", "inspector"} and "workspace.write" in permissions:
            raise AgentConfigurationError(f"{role} Skill cannot write workspace")

    @staticmethod
    def _contains_sensitive_key(value: Any) -> bool:
        forbidden = ("secret", "token", "password", "api_key", "authorization", "credential")
        if isinstance(value, Mapping):
            return any(
                any(word in str(key).lower() for word in forbidden)
                or AgentConfigurationStore._contains_sensitive_key(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple, set, frozenset)):
            return any(AgentConfigurationStore._contains_sensitive_key(item) for item in value)
        return False

    @staticmethod
    def _build(
        *,
        configuration_id: str,
        version: int,
        agent: AgentInstance,
        skill: SkillDefinition,
        model: ModelDefinition,
        updated_by_identity_id: str,
        settings: Mapping[str, Any],
    ) -> AgentConfiguration:
        identity_id = updated_by_identity_id.strip()
        if not identity_id:
            raise AgentConfigurationError("updated_by_identity_id is required")
        if AgentConfigurationStore._contains_sensitive_key(settings):
            raise AgentConfigurationError("agent settings contain sensitive fields")
        role = str(skill.metadata["agent_role"])
        permissions = skill.metadata["permissions"]
        return AgentConfiguration(
            configuration_id=configuration_id,
            configuration_version=version,
            agent_id=agent.agent_id,
            skill_id=skill.skill_id,
            role=role,
            model_id=model.model_id,
            system_prompt_version=str(skill.metadata.get("system_prompt_version", "1.0")),
            settings=MappingProxyType(dict(settings)),
            writable=role == "developer" and "workspace.write" in permissions,
            updated_by_identity_id=identity_id,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
