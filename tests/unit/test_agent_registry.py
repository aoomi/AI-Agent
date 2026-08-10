from __future__ import annotations

from pathlib import Path
import unittest

from ai_agent_discovery import AgentRegistry, AgentRegistryError, SkillDefinition


def skill(skill_id: str = "writer", name: str = "Writer") -> SkillDefinition:
    return SkillDefinition(skill_id, name, "1.0.0", "main.py", "short_drama", Path("manifest.yaml"), {})


class AgentRegistryTest(unittest.TestCase):
    def test_skill_creates_unique_idle_agent(self) -> None:
        registry = AgentRegistry()
        first, replayed = registry.register(skill("writer"))
        second, _ = registry.register(skill("director", "Director"))
        self.assertFalse(replayed)
        self.assertNotEqual(first.agent_id, second.agent_id)
        self.assertEqual(first.status, "idle")
        self.assertEqual(first.name, "Writer")

    def test_same_skill_registration_is_idempotent(self) -> None:
        registry = AgentRegistry()
        first, _ = registry.register(skill())
        replay, replayed = registry.register(skill())
        self.assertTrue(replayed)
        self.assertEqual(first, replay)

    def test_unknown_agent_is_rejected(self) -> None:
        with self.assertRaisesRegex(AgentRegistryError, "unknown agent_id"):
            AgentRegistry().get("missing")


if __name__ == "__main__":
    unittest.main()
