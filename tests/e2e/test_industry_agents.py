import unittest
from pathlib import Path
from ai_agent_discovery import IndustrySkillRegistry
class IndustryAgentsE2ETest(unittest.TestCase):
 def test_short_drama_template_covers_complete_eleven_node_flow(self):
  skills=IndustrySkillRegistry(Path(__file__).resolve().parents[2]/"plugins").scan();self.assertEqual({s.process_id for s in skills},{"requirements","outline","script","storyboard","assets","image","video","audio","subtitle","composition","review_export"})
if __name__=="__main__":unittest.main()
