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
  for robot,executor in ((" ",lambda:None),("robot",object())):
   with self.subTest(robot=robot),self.assertRaisesRegex(IndustryWorkflowError,"required"):service.bind_executor(robot,executor)
  for robots in (("robot","robot"),(" ",)):
   with self.subTest(robots=robots),self.assertRaisesRegex(IndustryWorkflowError,"creation is invalid"):
    service.execute(None,{"operation":"create","workflow_id":"workflow","industry_id":"industry","robot_ids":robots},"owner")
 def test_modify_rejects_unknown_mode_without_mutation(self):
  service=IndustryWorkflowService(Orchestrator());service.execute(None,{"operation":"create","workflow_id":"workflow","industry_id":"industry","robot_ids":("robot",)},"owner")
  with self.assertRaisesRegex(IndustryWorkflowError,"mode is invalid"):service.execute(None,{"operation":"modify","workflow_id":"workflow","mode":"unknown"},"owner")
  self.assertEqual(service.workflows["workflow"].version,1)

if __name__=="__main__":unittest.main()
