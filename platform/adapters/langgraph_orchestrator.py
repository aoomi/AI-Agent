"""LangGraph-backed durable serial/parallel orchestration and human takeover."""
from __future__ import annotations
from typing import Annotated,Any,Callable,Mapping,TypedDict
import operator
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END,START,StateGraph
from langgraph.types import Command,RetryPolicy,interrupt
class GraphState(TypedDict,total=False):
 inputs:Mapping[str,Any]
 outputs:Annotated[dict[str,Any],operator.or_]
 approved:bool
GraphExecutor=Callable[[Mapping[str,Any],Mapping[str,Any]],Any]
class LangGraphOrchestratorError(ValueError):pass
class LangGraphOrchestrator:
 def __init__(self,checkpointer:Any|None=None):self.checkpointer=checkpointer or InMemorySaver();self._graphs={}
 def compile(self,name:str,executors:Mapping[str,GraphExecutor],*,mode:str="serial",max_attempts:int=3,require_approval:bool=False):
  if not executors or mode not in {"serial","parallel"}:raise LangGraphOrchestratorError("invalid graph definition")
  builder=StateGraph(GraphState);nodes=list(executors)
  if require_approval:
   def approval(state):return {"approved":bool(interrupt({"action":"manual_takeover","graph":name}))}
   builder.add_node("__approval__",approval);builder.add_edge(START,"__approval__")
   for node in (nodes[:1] if mode=="serial" else nodes):builder.add_edge("__approval__",node)
  else:
   for node in (nodes[:1] if mode=="serial" else nodes):builder.add_edge(START,node)
  for node,executor in executors.items():
   def run(state,fn=executor,key=node):return {"outputs":{key:fn(state.get("inputs",{}),state.get("outputs",{}))}}
   builder.add_node(node,run,retry_policy=RetryPolicy(max_attempts=max_attempts,retry_on=ConnectionError))
  if mode=="serial":
   for left,right in zip(nodes,nodes[1:]):builder.add_edge(left,right)
  for node in (nodes[-1:] if mode=="serial" else nodes):builder.add_edge(node,END)
  graph=builder.compile(checkpointer=self.checkpointer);self._graphs[name]=graph;return graph
 def invoke(self,name:str,thread_id:str,inputs:Mapping[str,Any])->Mapping[str,Any]:return self._graph(name).invoke({"inputs":dict(inputs),"outputs":{}},config={"configurable":{"thread_id":thread_id}})
 def compile_branching(self,name:str,executors:Mapping[str,GraphExecutor],*,entry_node:str,branches:Mapping[str,Mapping[str,str]],terminal_nodes:tuple[str,...],max_attempts:int=3):
  if entry_node not in executors or not terminal_nodes:raise LangGraphOrchestratorError("invalid branching graph")
  builder=StateGraph(GraphState)
  for node,executor in executors.items():
   def run(state,fn=executor,key=node):return {"outputs":{key:fn(state.get("inputs",{}),state.get("outputs",{}))}}
   builder.add_node(node,run,retry_policy=RetryPolicy(max_attempts=max_attempts,retry_on=ConnectionError))
  builder.add_edge(START,entry_node)
  for source,paths in branches.items():builder.add_conditional_edges(source,lambda state,key=source:str(state["outputs"][key]),dict(paths))
  for node in terminal_nodes:builder.add_edge(node,END)
  graph=builder.compile(checkpointer=self.checkpointer);self._graphs[name]=graph;return graph
 def resume(self,name:str,thread_id:str,approved:bool)->Mapping[str,Any]:return self._graph(name).invoke(Command(resume=approved),config={"configurable":{"thread_id":thread_id}})
 def _graph(self,name):
  try:return self._graphs[name]
  except KeyError as error:raise LangGraphOrchestratorError("graph is not compiled") from error
