from pathlib import Path
import unittest

from ai_agent_discovery import SkillRegistry


ROOT = Path(__file__).resolve().parents[2]


class SystemAgentSkillsTest(unittest.TestCase):
    def test_developer_tester_and_inspector_skills_are_discoverable(self) -> None:
        skills = {skill.skill_id: skill for skill in SkillRegistry(ROOT / "plugins/builtin").scan()}
        self.assertEqual(skills["system_main_developer"].metadata["agent_role"], "developer")
        self.assertEqual(skills["system_software_tester"].metadata["agent_role"], "tester")
        self.assertEqual(skills["system_inspector"].metadata["agent_role"], "inspector")
        self.assertIn("workspace.write", skills["system_main_developer"].metadata["permissions"])
        self.assertNotIn("workspace.write", skills["system_software_tester"].metadata["permissions"])
        self.assertNotIn("workspace.write", skills["system_inspector"].metadata["permissions"])
        for skill_id in ("system_main_developer", "system_software_tester", "system_inspector"):
            prompt = skills[skill_id].manifest_path.parent / skills[skill_id].metadata["system_prompt_file"]
            self.assertTrue(prompt.is_file())
            self.assertTrue(prompt.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
