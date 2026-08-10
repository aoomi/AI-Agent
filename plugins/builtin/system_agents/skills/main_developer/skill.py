"""Main developer Skill declaration."""

SKILL_ID = "system_main_developer"
AGENT_ROLE = "developer"
WRITABLE = True


def describe() -> dict[str, object]:
    return {"skill_id": SKILL_ID, "agent_role": AGENT_ROLE, "writable": WRITABLE}
