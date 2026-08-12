from __future__ import annotations

from pathlib import Path
import unittest

from ai_agent_discovery import AgentInstance, AgentMapper, AgentMappingError, SkillDefinition


def skill(skill_id: str = "writer", name: str = "Writer") -> SkillDefinition:
    return SkillDefinition(skill_id, name, "1", "main.py", "plugin", Path("manifest.yaml"), {})


class AgentMapperTest(unittest.TestCase):
    def test_bidirectional_mapping_preserves_skill_name(self) -> None:
        mapper = AgentMapper()
        definition = skill()
        agent = AgentInstance("agent-1", "writer", "Writer")
        mapper.bind(definition, agent)
        self.assertEqual(mapper.agent_for("writer"), agent)
        self.assertEqual(mapper.skill_for("agent-1"), definition)

    def test_mismatched_identity_is_rejected(self) -> None:
        with self.assertRaisesRegex(AgentMappingError, "preserve"):
            AgentMapper().bind(skill(), AgentInstance("agent-1", "director", "Director"))

    def test_agent_cannot_map_to_two_skills(self) -> None:
        mapper = AgentMapper()
        mapper.bind(skill(), AgentInstance("agent-1", "writer", "Writer"))
        with self.assertRaises(AgentMappingError):
            mapper.bind(skill("director", "Director"), AgentInstance("agent-1", "director", "Director"))

    def test_anonymous_mapping_controls_are_rejected(self) -> None:
        mapper=AgentMapper()
        for operation in (
            lambda:mapper.agent_for(""), lambda:mapper.skill_for(""),
            lambda:mapper.bind(skill("", "Writer"),AgentInstance("agent","","Writer")),
            lambda:mapper.bind(skill(),AgentInstance("","writer","Writer")),
        ):
            with self.assertRaisesRegex(AgentMappingError,"required"):operation()


if __name__ == "__main__":
    unittest.main()
