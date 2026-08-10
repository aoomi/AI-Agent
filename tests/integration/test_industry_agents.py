from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from ai_agent_adapters import LangGraphOrchestrator
from ai_agent_discovery import AgentRegistry,IndustrySkillRegistry
class IndustryAgentsIntegrationTest(unittest.TestCase):
 def test_short_drama_and_second_industry_use_same_generic_registration(self):
  root=Path(__file__).resolve().parents[2];short=IndustrySkillRegistry(root/"plugins").scan();self.assertEqual(sorted(s.process_id for s in short),["assets","audio","composition","image","outline","requirements","review_export","script","storyboard","subtitle","video"])
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"custom/retail/industry-skills";path.mkdir(parents=True);(path/"processes.yaml").write_text("industry_id: retail\nskills:\n  - skill_id: retail.catalog\n    name: 商品目录机器人\n    process_id: catalog\n    entrypoint: workflows/catalog.py\n    required_capabilities: [chat]\n    permissions: [workspace.read]\n  - skill_id: retail.publish\n    name: 发布机器人\n    process_id: publish\n    entrypoint: workflows/publish.py\n    required_capabilities: [tool_calling]\n    permissions: [workspace.read]\n")
   retail=IndustrySkillRegistry(Path(d)).scan();registry=AgentRegistry();robots=[registry.register_scoped(s,"tenant","project")[0] for s in retail];self.assertEqual(len(robots),2)
   graph=LangGraphOrchestrator();graph.compile("retail",{robots[0].agent_id:lambda i,o:"catalog",robots[1].agent_id:lambda i,o:"published"});result=graph.invoke("retail","retail-run",{});self.assertIn("published",result["outputs"].values())
if __name__=="__main__":unittest.main()
