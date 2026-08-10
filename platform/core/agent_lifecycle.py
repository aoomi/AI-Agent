"""Closed lifecycle for Skill-backed agent instances."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


AgentStatus = Literal["idle", "loading", "running", "waiting_human", "completed", "failed"]
TRANSITIONS = frozenset({
    ("idle", "loading"), ("loading", "running"), ("loading", "failed"),
    ("running", "waiting_human"), ("running", "completed"), ("running", "failed"),
    ("waiting_human", "running"), ("waiting_human", "failed"),
    ("failed", "loading"), ("completed", "loading"),
})


class AgentLifecycleError(ValueError):
    """Raised when an agent lifecycle transition is forbidden."""


@dataclass(frozen=True, slots=True)
class AgentState:
    agent_id: str
    status: AgentStatus = "idle"


class AgentLifecycle:
    def transition(self, state: AgentState, target: AgentStatus) -> AgentState:
        if (state.status, target) not in TRANSITIONS:
            raise AgentLifecycleError(f"forbidden transition: {state.status}:{target}")
        return replace(state, status=target)
