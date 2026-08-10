import unittest
from types import SimpleNamespace
from ai_agent_adapters import LangGraphOrchestrator
from ai_agent_core import IndustryWorkflowService
class IndustryWorkflowConversationTest(unittest.TestCase):
 def test_create_connect_modify_and_run_workflow(self):
  service=IndustryWorkflowService(LangGraphOrchestrator());config=SimpleNamespace()
  self.assertEqual(service.execute(config,{"operation":"create","workflow_id":"w","industry_id":"generic","robot_ids":["a","b"],"mode":"serial"},"owner")["version"],1)
  self.assertEqual(service.execute(config,{"operation":"connect","workflow_id":"w","source_robot_id":"a","target_robot_id":"b"},"owner")["version"],2)
  service.bind_executor("a",lambda inputs,outputs:inputs["value"]+1);service.bind_executor("b",lambda inputs,outputs:outputs["a"]+1)
  result=service.execute(config,{"operation":"run","workflow_id":"w","thread_id":"thread","inputs":{"value":1}},"owner");self.assertEqual(result["result"]["outputs"]["b"],3)
if __name__=="__main__":unittest.main()
