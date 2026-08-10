import unittest
from pathlib import Path
from ai_agent_discovery import AgentRegistry,IndustrySkillRegistry
class IndustrySkillRegistryTest(unittest.TestCase):
 def test_short_drama_registers_eleven_process_skills_and_scoped_robots(self):
  root=Path(__file__).resolve().parents[2];skills=IndustrySkillRegistry(root/"plugins").scan();self.assertEqual(len(skills),11);registry=AgentRegistry();robots=[registry.register_scoped(skill,"tenant","project")[0] for skill in skills];self.assertEqual(len({r.agent_id for r in robots}),11);self.assertNotEqual(registry.register_scoped(skills[0],"tenant","other")[0].agent_id,robots[0].agent_id)
if __name__=="__main__":unittest.main()
