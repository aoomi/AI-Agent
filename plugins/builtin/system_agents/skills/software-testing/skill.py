"""Read-only incremental software testing Skill declaration."""

SKILL_ID = "system_software_tester"
AGENT_ROLE = "tester"
WRITABLE = False


def describe() -> dict[str, object]:
    return {"skill_id": SKILL_ID, "agent_role": AGENT_ROLE, "writable": WRITABLE}
