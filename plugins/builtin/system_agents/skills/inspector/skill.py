"""Read-only inspector Skill declaration."""

SKILL_ID = "system_inspector"
AGENT_ROLE = "inspector"
WRITABLE = False


def describe() -> dict[str, object]:
    return {"skill_id": SKILL_ID, "agent_role": AGENT_ROLE, "writable": WRITABLE}
