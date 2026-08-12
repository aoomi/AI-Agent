from __future__ import annotations

import unittest

from ai_agent_core import IndustryWorkflowError,IndustryWorkflowService

class Orchestrator:
 def compile(self,*args,**kwargs):pass
 def invoke(self,*args,**kwargs):return {}


class IndustryWorkflowContractTest(unittest.TestCase):
 def test_orchestrator_and_change_shapes_fail_closed(self):
  with self.assertRaisesRegex(IndustryWorkflowError,"orchestrator contract"):IndustryWorkflowService(object())
 def test_executor_and_workflow_controls_fail_closed(self):
  service=IndustryWorkflowService(Orchestrator())
  for robot,executor in ((" ",lambda:None),(1,lambda:None),("robot",object())):
   with self.subTest(robot=robot),self.assertRaisesRegex(IndustryWorkflowError,"required"):service.bind_executor(robot,executor)
  for robots in (("robot","robot"),(" ",),"robot",(1,)):
   with self.subTest(robots=robots),self.assertRaisesRegex(IndustryWorkflowError,"creation is invalid"):
    service.execute(None,{"operation":"create","workflow_id":"workflow","industry_id":"industry","robot_ids":robots},"owner")
  for changes,owner in (({"operation":"create","workflow_id":1,"industry_id":"industry","robot_ids":("robot",)},"owner"),({"operation":1,"workflow_id":"workflow"},"owner"),({"operation":"create","workflow_id":"workflow","industry_id":"industry","robot_ids":("robot",)},1)):
   with self.subTest(changes=changes),self.assertRaises(IndustryWorkflowError):service.execute(None,changes,owner)
 def test_modify_rejects_unknown_mode_without_mutation(self):
  service=IndustryWorkflowService(Orchestrator());service.execute(None,{"operation":"create","workflow_id":"workflow","industry_id":"industry","robot_ids":("robot",)},"owner")
  with self.assertRaisesRegex(IndustryWorkflowError,"mode is invalid"):service.execute(None,{"operation":"modify","workflow_id":"workflow","mode":"unknown"},"owner")
  with self.assertRaisesRegex(IndustryWorkflowError,"mode is invalid"):service.execute(None,{"operation":"modify","workflow_id":"workflow","mode":[]},"owner")
  self.assertEqual(service.workflows["workflow"].version,1)
 def test_run_rejects_non_string_thread_without_invoking_graph(self):
  service=IndustryWorkflowService(Orchestrator());service.bind_executor("robot",lambda *_:{})
  service.execute(None,{"operation":"create","workflow_id":"workflow","industry_id":"industry","robot_ids":("robot",)},"owner")
  with self.assertRaisesRegex(IndustryWorkflowError,"run contract"):
   service.execute(None,{"operation":"run","workflow_id":"workflow","thread_id":1},"owner")
 def test_connection_ids_are_normalized_before_membership(self):
  service=IndustryWorkflowService(Orchestrator());service.execute(None,{"operation":"create","workflow_id":"workflow","industry_id":"industry","robot_ids":("one","two")},"owner")
  result=service.execute(None,{"operation":"connect","workflow_id":"workflow","source_robot_id":" one ","target_robot_id":" two "},"owner")
  self.assertEqual(result["version"],2);self.assertEqual(service.workflows["workflow"].edges,(("one","two"),))

if __name__=="__main__":unittest.main()
