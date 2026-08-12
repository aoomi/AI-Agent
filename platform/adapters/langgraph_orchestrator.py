"""LangGraph-backed durable serial/parallel orchestration and human takeover."""
from __future__ import annotations
from typing import Annotated,Any,Callable,Mapping,TypedDict
from threading import RLock
import operator
import json
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
 def __init__(self,checkpointer:Any|None=None):
  selected=checkpointer or InMemorySaver()
  if not callable(getattr(selected,"get_tuple",None)) or not callable(getattr(selected,"put",None)):raise LangGraphOrchestratorError("checkpointer contract is invalid")
  self.checkpointer=selected;self._graphs={};self._lock=RLock();self._active:set[tuple[str,str]]=set()
 def compile(self,name:str,executors:Mapping[str,GraphExecutor],*,mode:str="serial",max_attempts:int=3,require_approval:bool=False):
  if (not isinstance(name,str) or not isinstance(mode,str) or not name.strip() or not isinstance(executors,Mapping) or not executors or mode not in {"serial","parallel"}
      or isinstance(max_attempts,bool) or not isinstance(max_attempts,int) or not 1<=max_attempts<=10
      or not isinstance(require_approval,bool) or any(not isinstance(node,str) or not node.strip() or not callable(executor) for node,executor in executors.items())):raise LangGraphOrchestratorError("invalid graph definition")
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
  graph=builder.compile(checkpointer=self.checkpointer)
  with self._lock:self._graphs[name]=graph
  return graph
 def invoke(self,name:str,thread_id:str,inputs:Mapping[str,Any])->Mapping[str,Any]:
  if not isinstance(inputs,Mapping):raise LangGraphOrchestratorError("graph inputs must be a mapping")
  try:canonical_inputs=json.dumps(dict(inputs),allow_nan=False)
  except (TypeError,ValueError) as error:raise LangGraphOrchestratorError("graph inputs must be standard JSON") from error
  return self._invoke(name,thread_id,{"inputs":json.loads(canonical_inputs),"outputs":{}})
 def compile_branching(self,name:str,executors:Mapping[str,GraphExecutor],*,entry_node:str,branches:Mapping[str,Mapping[str,str]],terminal_nodes:tuple[str,...],max_attempts:int=3):
  if (not isinstance(name,str) or not isinstance(entry_node,str) or not isinstance(executors,Mapping) or not isinstance(branches,Mapping)
      or not isinstance(terminal_nodes,tuple) or any(not isinstance(node,str) or not node.strip() for node in terminal_nodes)
      or any(not isinstance(source,str) or not isinstance(paths,Mapping) or any(not isinstance(choice,str) or not choice.strip() or not isinstance(target,str) or not target.strip() for choice,target in paths.items()) for source,paths in branches.items())):
   raise LangGraphOrchestratorError("invalid branching graph")
  nodes=set(executors)
  branch_targets={target for paths in branches.values() for target in paths.values()}
  if (not name.strip() or entry_node not in executors or not terminal_nodes
      or isinstance(max_attempts,bool) or not isinstance(max_attempts,int) or not 1<=max_attempts<=10
      or any(not isinstance(node,str) or not node.strip() or not callable(executor) for node,executor in executors.items()) or not set(branches)<=nodes or not branch_targets<=nodes or not set(terminal_nodes)<=nodes):raise LangGraphOrchestratorError("invalid branching graph")
  builder=StateGraph(GraphState)
  for node,executor in executors.items():
   def run(state,fn=executor,key=node):return {"outputs":{key:fn(state.get("inputs",{}),state.get("outputs",{}))}}
   builder.add_node(node,run,retry_policy=RetryPolicy(max_attempts=max_attempts,retry_on=ConnectionError))
  builder.add_edge(START,entry_node)
  for source,paths in branches.items():builder.add_conditional_edges(source,lambda state,key=source:str(state["outputs"][key]),dict(paths))
  for node in terminal_nodes:builder.add_edge(node,END)
  graph=builder.compile(checkpointer=self.checkpointer)
  with self._lock:self._graphs[name]=graph
  return graph
 def resume(self,name:str,thread_id:str,approved:bool)->Mapping[str,Any]:
  if not isinstance(approved,bool):raise LangGraphOrchestratorError("graph approval must be boolean")
  return self._invoke(name,thread_id,Command(resume=approved))
 def _invoke(self,name:str,thread_id:str,value:Any)->Mapping[str,Any]:
  if not isinstance(name,str) or not isinstance(thread_id,str) or not name.strip() or not thread_id.strip():raise LangGraphOrchestratorError("graph name and thread_id are required")
  key=(name,thread_id)
  with self._lock:
   if key in self._active:raise LangGraphOrchestratorError("graph thread is already active")
   graph=self._graph(name);self._active.add(key)
  try:
   result=graph.invoke(value,config={"configurable":{"thread_id":thread_id}})
   public_state={key:item for key,item in dict(result).items() if key!="__interrupt__"}
   try:canonical_public_state=json.dumps(public_state,allow_nan=False)
   except (TypeError,ValueError) as error:raise LangGraphOrchestratorError("graph result must be standard JSON") from error
   snapshot=json.loads(canonical_public_state)
   if "__interrupt__" in result:snapshot["__interrupt__"]=result["__interrupt__"]
   return snapshot
  finally:
   with self._lock:self._active.discard(key)
 def _graph(self,name):
  if not isinstance(name,str) or not name.strip():raise LangGraphOrchestratorError("graph name is required")
  with self._lock:
   try:return self._graphs[name]
   except KeyError as error:raise LangGraphOrchestratorError("graph is not compiled") from error
