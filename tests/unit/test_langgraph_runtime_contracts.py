from __future__ import annotations
import unittest
from ai_agent_adapters import LangGraphOrchestrator,LangGraphOrchestratorError
class LangGraphRuntimeContractTest(unittest.TestCase):
 def test_graph_executor_cannot_mutate_nested_caller_inputs(self):
  graph=LangGraphOrchestrator()
  def executor(inputs,_outputs):inputs["routing"]["regions"][0]="graph";return "ok"
  graph.compile("g",{"node":executor});inputs={"routing":{"regions":["local"]}}
  graph.invoke("g","thread",inputs)
  self.assertEqual(inputs["routing"]["regions"][0],"local")
 def test_runtime_contracts_fail_closed(self):
  with self.assertRaisesRegex(LangGraphOrchestratorError,"checkpointer"):LangGraphOrchestrator(object())
  graph=LangGraphOrchestrator()
  for operation in (lambda:graph.compile(1,{"n":lambda *_:None}),lambda:graph.compile("g",{1:lambda *_:None}),lambda:graph.compile("g",{"n":lambda *_:None},max_attempts=True),lambda:graph.compile("g",{"n":lambda *_:None},require_approval=1),lambda:graph.compile_branching("g",{"n":lambda *_:None},entry_node="n",branches=[],terminal_nodes=("n",)),lambda:graph.compile_branching("g",{1:lambda *_:None},entry_node="n",branches={},terminal_nodes=("n",)),lambda:graph.compile_branching("g",{"n":lambda *_:None},entry_node="n",branches={},terminal_nodes=["n"]),lambda:graph.invoke("g",1,{}),lambda:graph.invoke("g","thread",[]),lambda:graph.resume("g","thread",1),lambda:graph._graph(1)):
   with self.subTest(operation=operation),self.assertRaises(LangGraphOrchestratorError):operation()
 def test_graph_inputs_and_results_require_standard_json(self):
  graph=LangGraphOrchestrator();graph.compile("g",{"node":lambda inputs,_outputs:inputs.get("value")})
  for value in (float("nan"),object()):
   with self.subTest(value=value),self.assertRaisesRegex(LangGraphOrchestratorError,"inputs must be standard JSON"):graph.invoke("g",f"input-{id(value)}",{"value":value})
  bad=LangGraphOrchestrator();bad.compile("g",{"node":lambda *_:float("nan")})
  with self.assertRaisesRegex(LangGraphOrchestratorError,"result must be standard JSON"):bad.invoke("g","result",{})
if __name__=="__main__":unittest.main()
