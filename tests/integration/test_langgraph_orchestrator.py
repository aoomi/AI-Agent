import unittest
from ai_agent_adapters import LangGraphOrchestrator
from ai_agent_core import AgentContextStore,AgentScheduler
from ai_agent_discovery import AgentRegistry
class LangGraphOrchestratorTest(unittest.TestCase):
 def test_serial_parallel_and_retry(self):
  graph=LangGraphOrchestrator();calls=[]
  def first(inputs,outputs):calls.append("first");return inputs["x"]+1
  def second(inputs,outputs):calls.append("second");return outputs["first"]+1
  graph.compile("serial",{"first":first,"second":second});result=graph.invoke("serial","thread-1",{"x":1});self.assertEqual(result["outputs"]["second"],3);self.assertEqual(calls,["first","second"])
  graph.compile("parallel",{"a":lambda i,o:"a","b":lambda i,o:"b"},mode="parallel");self.assertEqual(graph.invoke("parallel","thread-2",{})["outputs"],{"a":"a","b":"b"})
  attempts=[]
  def flaky(i,o):attempts.append(1);(_ for _ in ()).throw(ConnectionError()) if len(attempts)<2 else None;return "ok"
  graph.compile("retry",{"flaky":flaky},max_attempts=2);self.assertEqual(graph.invoke("retry","thread-3",{})["outputs"]["flaky"],"ok")
 def test_interrupt_and_resume_manual_takeover(self):
  graph=LangGraphOrchestrator();graph.compile("approval",{"work":lambda i,o:"done"},require_approval=True);paused=graph.invoke("approval","thread-4",{});self.assertIn("__interrupt__",paused);resumed=graph.resume("approval","thread-4",True);self.assertTrue(resumed["approved"]);self.assertEqual(resumed["outputs"]["work"],"done")
 def test_scheduler_delegates_to_langgraph(self):
  scheduler=AgentScheduler(AgentRegistry(),AgentContextStore());scheduler.use_graph_orchestrator(LangGraphOrchestrator());result=scheduler.start_graph(graph_id="g",thread_id="t",executors={"x":lambda i,o:"ok"},inputs={});self.assertEqual(result["outputs"]["x"],"ok")
 def test_branching_routes_to_selected_process_robot(self):
  graph=LangGraphOrchestrator();graph.compile_branching("branch",{"router":lambda i,o:i["route"],"left":lambda i,o:"L","right":lambda i,o:"R"},entry_node="router",branches={"router":{"left":"left","right":"right"}},terminal_nodes=("left","right"));result=graph.invoke("branch","branch-1",{"route":"right"});self.assertEqual(result["outputs"]["right"],"R");self.assertNotIn("left",result["outputs"])
 def test_invalid_graph_topology_fails_before_compile(self):
  graph=LangGraphOrchestrator()
  with self.assertRaisesRegex(Exception,"invalid branching"):graph.compile_branching("branch",{"router":lambda i,o:"missing"},entry_node="router",branches={"router":{"x":"missing"}},terminal_nodes=("missing",))
  graph.compile("valid",{"node":lambda i,o:"ok"})
  with self.assertRaisesRegex(Exception,"thread_id"):graph.invoke("valid","",{})
if __name__=="__main__":unittest.main()
