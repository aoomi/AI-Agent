"""Create one independent agent instance for each registered Skill."""

from __future__ import annotations

from dataclasses import dataclass, replace
from threading import RLock
from uuid import uuid4

from .skill_registry import SkillDefinition


class AgentRegistryError(ValueError):
    """Raised when an agent cannot be registered or resolved."""


@dataclass(frozen=True, slots=True)
class AgentInstance:
    agent_id: str
    skill_id: str
    name: str
    status: str = "idle"

@dataclass(frozen=True, slots=True)
class ProcessRobotInstance:
    agent_id: str; skill_id: str; name: str; tenant_id: str; project_id: str; status: str = "idle"


class AgentRegistry:
    STATUSES = frozenset({"idle","loading","running","waiting_human","completed","failed","cancelled"})
    def __init__(self) -> None:
        self._by_id: dict[str, AgentInstance] = {}
        self._by_skill: dict[str, str] = {}
        self._scoped: dict[tuple[str,str,str],ProcessRobotInstance] = {}
        self._scoped_by_id: dict[str,ProcessRobotInstance] = {}
        self._lock = RLock()

    def register_scoped(self, skill: object, tenant_id: str, project_id: str) -> tuple[ProcessRobotInstance,bool]:
        skill_id=str(getattr(skill,"skill_id",""));name=str(getattr(skill,"name",""));scope=(tenant_id.strip(),project_id.strip(),skill_id)
        if not all(scope): raise AgentRegistryError("tenant, project and Skill are required")
        with self._lock:
            existing=self._scoped.get(scope)
            if existing:return existing,True
            robot=ProcessRobotInstance(f"robot-{uuid4().hex}",skill_id,name,scope[0],scope[1]);self._scoped[scope]=robot;self._scoped_by_id[robot.agent_id]=robot;return robot,False

    def scoped(self, tenant_id:str, project_id:str, skill_id:str)->ProcessRobotInstance:
        with self._lock:
            try:return self._scoped[(tenant_id,project_id,skill_id)]
            except KeyError as error:raise AgentRegistryError("scoped process robot does not exist") from error

    def register(self, skill: SkillDefinition) -> tuple[AgentInstance, bool]:
        with self._lock:
            existing_id = self._by_skill.get(skill.skill_id)
            if existing_id is not None: return self._by_id[existing_id], True
            instance = AgentInstance(agent_id=f"agent-{uuid4().hex}", skill_id=skill.skill_id, name=skill.name)
            self._by_id[instance.agent_id] = instance; self._by_skill[skill.skill_id] = instance.agent_id; return instance, False

    def sync(self, skills: tuple[SkillDefinition, ...]) -> tuple[AgentInstance, ...]:
        return tuple(self.register(skill)[0] for skill in skills)

    def get(self, agent_id: str) -> AgentInstance:
        with self._lock:
            try: return self._by_id[agent_id]
            except KeyError as error:
                try:return self._scoped_by_id[agent_id]  # type: ignore[return-value]
                except KeyError:raise AgentRegistryError(f"unknown agent_id: {agent_id}") from error

    def for_skill(self, skill_id: str) -> AgentInstance:
        with self._lock:
            try: return self._by_id[self._by_skill[skill_id]]
            except KeyError as error: raise AgentRegistryError(f"unknown skill_id: {skill_id}") from error

    def update_status(self, agent_id: str, status: str) -> AgentInstance:
        if status not in self.STATUSES:raise AgentRegistryError("agent status is invalid")
        with self._lock:
            current = self.get(agent_id); updated = replace(current, status=status)
            if agent_id in self._by_id: self._by_id[agent_id] = updated
            else:
                self._scoped_by_id[agent_id] = updated  # type: ignore[assignment]
                scoped = updated  # type: ignore[assignment]
                self._scoped[(scoped.tenant_id, scoped.project_id, scoped.skill_id)] = scoped
            return updated
