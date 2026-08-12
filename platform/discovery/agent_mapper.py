"""Enforce the public one-to-one Skill-to-agent relationship."""

from __future__ import annotations
from threading import RLock

from .agent_registry import AgentInstance
from .skill_registry import SkillDefinition


class AgentMappingError(ValueError):
    """Raised when a one-to-one mapping would be violated."""


class AgentMapper:
    def __init__(self) -> None:
        self._skill_to_agent: dict[str, AgentInstance] = {}
        self._agent_to_skill: dict[str, SkillDefinition] = {}
        self._lock = RLock()

    def bind(self, skill: SkillDefinition, agent: AgentInstance) -> None:
        if not isinstance(skill,SkillDefinition) or not isinstance(agent,AgentInstance):
            raise AgentMappingError("Skill and agent models are required")
        if any(not isinstance(value,str) or not value.strip() for value in (skill.skill_id,skill.name,agent.agent_id,agent.skill_id,agent.name)):
            raise AgentMappingError("Skill and agent identities are required")
        if agent.skill_id != skill.skill_id or agent.name != skill.name:
            raise AgentMappingError("agent must preserve Skill identity and name")
        with self._lock:
            current_agent = self._skill_to_agent.get(skill.skill_id); current_skill = self._agent_to_skill.get(agent.agent_id)
            if current_agent not in (None, agent) or current_skill not in (None, skill): raise AgentMappingError("Skill and agent mapping must remain one-to-one")
            self._skill_to_agent[skill.skill_id] = agent; self._agent_to_skill[agent.agent_id] = skill

    def agent_for(self, skill_id: str) -> AgentInstance:
        if not isinstance(skill_id,str):raise AgentMappingError("skill_id is required")
        skill_id=skill_id.strip()
        if not skill_id:raise AgentMappingError("skill_id is required")
        with self._lock:
            try: return self._skill_to_agent[skill_id]
            except KeyError as error: raise AgentMappingError(f"unmapped skill_id: {skill_id}") from error

    def skill_for(self, agent_id: str) -> SkillDefinition:
        if not isinstance(agent_id,str):raise AgentMappingError("agent_id is required")
        agent_id=agent_id.strip()
        if not agent_id:raise AgentMappingError("agent_id is required")
        with self._lock:
            try: return self._agent_to_skill[agent_id]
            except KeyError as error: raise AgentMappingError(f"unmapped agent_id: {agent_id}") from error
