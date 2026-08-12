"""Conversation-configurable industry robot workflows."""
from __future__ import annotations
from dataclasses import dataclass,replace
from threading import RLock
from typing import Any,Callable,Mapping
class IndustryWorkflowError(ValueError):pass
@dataclass(frozen=True,slots=True)
class IndustryWorkflow:
 workflow_id:str;industry_id:str;created_by_identity_id:str;robot_ids:tuple[str,...];edges:tuple[tuple[str,str],...];mode:str;version:int=1
class IndustryWorkflowService:
 def __init__(self,orchestrator):self.orchestrator=orchestrator;self.workflows={};self.executors={};self._lock=RLock();self._active_workflows:set[str]=set();self._active_robots:set[str]=set()
 def bind_executor(self,robot_id:str,executor:Callable):
  robot_id=str(robot_id).strip()
  if not robot_id or not callable(executor):raise IndustryWorkflowError("workflow robot and executor are required")
  with self._lock:
   if robot_id in self._active_robots:raise IndustryWorkflowError("workflow executor is active")
   self.executors[robot_id]=executor
 def execute(self,configuration,changes:Mapping[str,Any],confirmed_by_identity_id:str)->Mapping[str,Any]:
  operation=changes.get("operation");workflow_id=str(changes.get("workflow_id",""))
  identity_id=str(confirmed_by_identity_id or "").strip()
  if not identity_id:raise IndustryWorkflowError("workflow identity is required")
  if operation=="create":
   robots=tuple(changes.get("robot_ids",()));mode=str(changes.get("mode","serial"));industry=str(changes.get("industry_id",""))
   if (not workflow_id or not industry or not robots or any(not str(robot).strip() for robot in robots)
       or len(set(robots))!=len(robots) or mode not in {"serial","parallel","branching"}):raise IndustryWorkflowError("workflow creation is invalid")
   with self._lock:
    if workflow_id in self.workflows:raise IndustryWorkflowError("workflow already exists")
    item=IndustryWorkflow(workflow_id,industry,identity_id,robots,(),mode);self.workflows[workflow_id]=item
  else:
   with self._lock:
    try:item=self.workflows[workflow_id]
    except KeyError as error:raise IndustryWorkflowError("workflow does not exist") from error
    if item.created_by_identity_id!=identity_id:raise IndustryWorkflowError("workflow is not owned by identity")
    if workflow_id in self._active_workflows:raise IndustryWorkflowError("workflow is already active")
   if operation=="connect":
    source,target=str(changes.get("source_robot_id","")),str(changes.get("target_robot_id",""))
    if source not in item.robot_ids or target not in item.robot_ids or source==target:raise IndustryWorkflowError("workflow connection is invalid")
    item=replace(item,edges=item.edges+((source,target),),version=item.version+1)
    with self._lock:self.workflows[workflow_id]=item
   elif operation=="run":
    with self._lock:
     missing=set(item.robot_ids)-self.executors.keys();executors={r:self.executors[r] for r in item.robot_ids if r in self.executors}
    if missing:raise IndustryWorkflowError("workflow robot executors are not bound")
    if item.mode=="branching":raise IndustryWorkflowError("branching workflow requires explicit route configuration")
    with self._lock:self._active_workflows.add(workflow_id);self._active_robots.update(item.robot_ids)
    try:
     self.orchestrator.compile(workflow_id,executors,mode=item.mode);result=self.orchestrator.invoke(workflow_id,str(changes.get("thread_id",workflow_id)),changes.get("inputs",{}));return {"workflow_id":workflow_id,"version":item.version,"result":dict(result)}
    finally:
     with self._lock:self._active_workflows.discard(workflow_id);self._active_robots.difference_update(item.robot_ids)
   elif operation=="modify":
    mode=str(changes.get("mode",item.mode))
    if mode not in {"serial","parallel","branching"}:raise IndustryWorkflowError("workflow mode is invalid")
    item=replace(item,mode=mode,version=item.version+1)
    with self._lock:self.workflows[workflow_id]=item
   else:raise IndustryWorkflowError("workflow operation is invalid")
  return {"workflow_id":item.workflow_id,"version":item.version,"mode":item.mode}
