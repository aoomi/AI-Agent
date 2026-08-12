"""Sequential Skill-agent scheduler with explicit interruption and recovery."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from threading import RLock
from typing import Any, Literal, Protocol
from uuid import uuid4

from ai_agent_discovery import AgentRegistry

from .agent_context import AgentContext, AgentContextStore
from .agent_lifecycle import AgentLifecycle, AgentState
from .agent_collaboration import RemediationInstruction


class SchedulerError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    status: Literal["completed", "waiting_human", "failed"]
    values: Mapping[str, Any]


AgentExecutor = Callable[[AgentContext], ExecutionResult]
class AgentGraphOrchestrator(Protocol):
    def compile(self, name: str, executors: Mapping[str, Any], *, mode: str, max_attempts: int, require_approval: bool): ...
    def invoke(self, name: str, thread_id: str, inputs: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def resume(self, name: str, thread_id: str, approved: bool) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class PipelineRun:
    run_id: str
    tenant_id: str
    project_id: str
    agent_ids: tuple[str, ...]
    current_index: int = 0
    status: str = "running"
    mode: str = "serial"
    retry_count: int = 0
    max_retries: int = 2


@dataclass(frozen=True, slots=True)
class ScheduledRemediation:
    instruction_id: str
    root_task_id: str
    developer_agent_id: str
    issue_ids: tuple[str, ...]
    remediation_round: int
    status: str = "pending"


class AgentScheduler:
    def __init__(self, registry: AgentRegistry, contexts: AgentContextStore) -> None:
        self.registry = registry
        self.contexts = contexts
        self.lifecycle = AgentLifecycle()
        self.executors: dict[str, AgentExecutor] = {}
        self.runs: dict[str, PipelineRun] = {}
        self.remediations: dict[str, ScheduledRemediation] = {}
        self.graph_orchestrator: AgentGraphOrchestrator | None = None
        self._lock = RLock()
        self._active_runs: set[str] = set()

    def use_graph_orchestrator(self, orchestrator: AgentGraphOrchestrator) -> None:
        self.graph_orchestrator = orchestrator

    def start_graph(self, *, graph_id: str, thread_id: str, executors: Mapping[str, Any], inputs: Mapping[str, Any], mode: str = "serial", max_attempts: int = 3, require_approval: bool = False) -> Mapping[str, Any]:
        if self.graph_orchestrator is None: raise SchedulerError("LangGraph orchestrator is not configured")
        self.graph_orchestrator.compile(graph_id, executors, mode=mode, max_attempts=max_attempts, require_approval=require_approval)
        return self.graph_orchestrator.invoke(graph_id, thread_id, inputs)

    def resume_graph(self, graph_id: str, thread_id: str, approved: bool) -> Mapping[str, Any]:
        if self.graph_orchestrator is None: raise SchedulerError("LangGraph orchestrator is not configured")
        return self.graph_orchestrator.resume(graph_id, thread_id, approved)

    def schedule_remediation(self, instruction: RemediationInstruction) -> ScheduledRemediation:
        with self._lock:
            if instruction.instruction_id in self.remediations: raise SchedulerError("remediation instruction is already scheduled")
            remediation = ScheduledRemediation(instruction.instruction_id, instruction.root_task_id, instruction.developer_agent_id, instruction.issue_ids, instruction.remediation_round)
            self.remediations[instruction.instruction_id] = remediation; return remediation

    def remediation(self, instruction_id: str) -> ScheduledRemediation:
        with self._lock:
            try: return self.remediations[instruction_id]
            except KeyError as error: raise SchedulerError("remediation task does not exist") from error

    def complete_remediation(self, instruction_id: str) -> ScheduledRemediation:
        with self._lock:
            remediation = self.remediation(instruction_id)
            if remediation.status != "pending": raise SchedulerError("remediation task is not pending")
            completed = replace(remediation, status="completed"); self.remediations[instruction_id] = completed; return completed

    def add_executor(self, agent_id: str, executor: AgentExecutor) -> None:
        self.registry.get(agent_id)
        with self._lock:self.executors[agent_id] = executor

    def start(self, tenant_id: str, project_id: str, agent_ids: tuple[str, ...], values: Mapping[str, Any], *, mode: str = "serial", max_retries: int = 2, auto_run: bool = True) -> PipelineRun:
        if not agent_ids:
            raise SchedulerError("pipeline requires at least one agent")
        if mode not in {"serial", "parallel"}: raise SchedulerError("scheduler mode must be serial or parallel")
        if not 0 <= max_retries <= 10: raise SchedulerError("max_retries must be between 0 and 10")
        for agent_id in agent_ids:
            self.contexts.create(tenant_id, project_id, agent_id)
        targets = agent_ids if mode == "parallel" else agent_ids[:1]
        for agent_id in targets: self.contexts.update(tenant_id, project_id, agent_id, values)
        run = PipelineRun(f"run-{uuid4().hex}", tenant_id, project_id, agent_ids, mode=mode, max_retries=max_retries)
        self.runs[run.run_id] = run
        return self.run(run.run_id) if auto_run else run

    def run(self, run_id: str) -> PipelineRun:
        with self._lock:
            if run_id in self._active_runs: raise SchedulerError("pipeline run is already active")
            self._active_runs.add(run_id)
        try:return self._run_once(run_id)
        finally:
            with self._lock:self._active_runs.discard(run_id)

    def _run_once(self, run_id: str) -> PipelineRun:
        run = self._get(run_id)
        if run.status == "paused": return run
        if run.mode == "parallel": return self._run_parallel(run)
        while run.current_index < len(run.agent_ids):
            agent_id = run.agent_ids[run.current_index]
            result = self._execute(run, agent_id)
            target = result.status
            if target != "completed":
                run = replace(run, status=target)
                self.runs[run_id] = run
                return run
            next_index = run.current_index + 1
            if next_index < len(run.agent_ids):
                self.contexts.update(run.tenant_id, run.project_id, run.agent_ids[next_index], {"upstream": dict(result.values)})
            run = replace(run, current_index=next_index)
            self.runs[run_id] = run
        run = replace(run, status="completed")
        self.runs[run_id] = run
        return run

    def _run_parallel(self, run: PipelineRun) -> PipelineRun:
        if run.current_index >= len(run.agent_ids): return run
        try:
            with ThreadPoolExecutor(max_workers=len(run.agent_ids)) as pool:
                futures = {agent_id: pool.submit(self._execute, run, agent_id) for agent_id in run.agent_ids}
                results = {agent_id: future.result() for agent_id, future in futures.items()}
        except Exception:
            failed = replace(run, status="failed")
            self.runs[run.run_id] = failed
            return failed
        statuses = {result.status for result in results.values()}
        status = "failed" if "failed" in statuses else "waiting_human" if "waiting_human" in statuses else "completed"
        completed = replace(run, current_index=len(run.agent_ids) if status == "completed" else 0, status=status)
        self.runs[run.run_id] = completed
        return completed

    def _execute(self, run: PipelineRun, agent_id: str) -> ExecutionResult:
        executor = self.executors.get(agent_id)
        if executor is None: raise SchedulerError(f"missing executor for {agent_id}")
        current = self.registry.get(agent_id)
        if current.status in {"idle", "failed", "completed"}:
            current = self.registry.update_status(agent_id, self.lifecycle.transition(AgentState(agent_id, current.status), "loading").status)
            current = self.registry.update_status(agent_id, self.lifecycle.transition(AgentState(agent_id, current.status), "running").status)
        elif current.status == "waiting_human":
            current = self.registry.update_status(agent_id, self.lifecycle.transition(AgentState(agent_id, current.status), "running").status)
        result = executor(self.contexts.get(run.tenant_id, run.project_id, agent_id))
        self.registry.update_status(agent_id, self.lifecycle.transition(AgentState(agent_id, current.status), result.status).status)
        self.contexts.update(run.tenant_id, run.project_id, agent_id, result.values)
        return result

    def pause(self, run_id: str) -> PipelineRun:
        run = self._get(run_id)
        if run.status != "running": raise SchedulerError("only running runs can pause")
        paused = replace(run, status="paused"); self.runs[run_id] = paused; return paused

    def retry(self, run_id: str) -> PipelineRun:
        run = self._get(run_id)
        if run.status != "failed": raise SchedulerError("only failed runs can retry")
        if run.retry_count >= run.max_retries: raise SchedulerError("maximum retries reached")
        self.runs[run_id] = replace(run, status="running", retry_count=run.retry_count + 1)
        return self.run(run_id)

    def manual_takeover(self, run_id: str) -> PipelineRun:
        run = self._get(run_id)
        if run.status in {"completed", "cancelled"}: raise SchedulerError("terminal run cannot be taken over")
        takeover = replace(run, status="waiting_human"); self.runs[run_id] = takeover; return takeover

    def resume(self, run_id: str, values: Mapping[str, Any]) -> PipelineRun:
        run = self._get(run_id)
        if run.status not in {"waiting_human", "paused"}:
            raise SchedulerError("only waiting_human or paused runs can resume")
        targets = run.agent_ids if run.mode == "parallel" else (run.agent_ids[run.current_index],)
        for agent_id in targets: self.contexts.update(run.tenant_id, run.project_id, agent_id, values)
        self.runs[run_id] = replace(run, status="running")
        return self.run(run_id)

    def _get(self, run_id: str) -> PipelineRun:
        with self._lock:
            try:return self.runs[run_id]
            except KeyError as error:raise SchedulerError("pipeline run does not exist") from error
