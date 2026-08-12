from __future__ import annotations
import unittest
from ai_agent_adapters import LangGraphOrchestrator,LangGraphOrchestratorError
class LangGraphRuntimeContractTest(unittest.TestCase):
 def test_runtime_contracts_fail_closed(self):
  with self.assertRaisesRegex(LangGraphOrchestratorError,"checkpointer"):LangGraphOrchestrator(object())
  graph=LangGraphOrchestrator()
  for operation in (lambda:graph.compile("g",{"n":lambda *_:None},max_attempts=True),lambda:graph.compile("g",{"n":lambda *_:None},require_approval=1),lambda:graph.invoke("g","thread",[]),lambda:graph.resume("g","thread",1)):
   with self.subTest(operation=operation),self.assertRaises(LangGraphOrchestratorError):operation()
if __name__=="__main__":unittest.main()
