"""Persistent eleven-node orchestration with queue, events and human approval."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
import re
from typing import Callable, Mapping
from uuid import uuid4

from ai_agent_events import EventBus, PublishedEvent
from ai_agent_core import atomic_write_json
from ai_agent_queue import InMemoryTaskQueue, QueuedTask
from ai_agent_tenant import IdentityContext
from .production_orchestrator import ProductionOrchestrator


NODES = ("requirements", "outline", "script", "storyboard", "assets", "image", "video", "audio", "subtitle", "composition", "review_export")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,254}$")


class ShortDramaPipelineError(ValueError): pass


@dataclass(frozen=True, slots=True)
class NodeOutput:
    content: bytes
    media_type: str


NodeRunner = Callable[[Mapping[str, str]], NodeOutput]


@dataclass(frozen=True, slots=True)
class PipelineCheckpoint:
    run_id: str
    task_id: str
    tenant_id: str
    user_id: str
    project_id: str
    operation_key: str
    status: str
    next_index: int
    artifacts: Mapping[str, str]


class ShortDramaPipeline:
    def __init__(self, root: Path, queue: InMemoryTaskQueue, events: EventBus, runners: Mapping[str, NodeRunner]) -> None:
        self.root = root.resolve(); self.queue = queue; self.events = events; self.runners = dict(runners)
        missing = set(NODES) - self.runners.keys()
        if missing: raise ShortDramaPipelineError(f"missing node runners: {sorted(missing)}")
        self.orchestrator = ProductionOrchestrator(self.root / "production-kernel.sqlite")
        for stage in NODES:
            self.orchestrator.register_stage(stage, lambda inputs, key=stage: self._execute_stage(key, inputs), provider_id="legacy-provider-adapter")

    def start(self, context: IdentityContext, project_id: str, operation_key: str, initial_requirements: NodeOutput | None = None) -> PipelineCheckpoint:
        self._safe(project_id); self._safe(operation_key)
        run_id, task_id = f"run-{uuid4().hex}", f"task-{uuid4().hex}"
        task = QueuedTask(task_id, project_id, operation_key, "short_drama.pipeline", context, {"run_id": run_id})
        accepted, replayed = self.queue.enqueue(task)
        if replayed: return self.load(context, project_id, str(accepted.payload["run_id"]))
        self.queue.claim(context.tenant_id)
        artifacts: dict[str, str] = {}
        next_index = 0
        if initial_requirements is not None:
            if not initial_requirements.content or not initial_requirements.media_type:
                raise ShortDramaPipelineError("initial requirements output is empty")
            initial_checkpoint = PipelineCheckpoint(run_id, task_id, context.tenant_id, context.identity_id, project_id, operation_key, "running", 0, {})
            artifact_path = self._artifact_path(initial_checkpoint, "requirements", 1)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(initial_requirements.content)
            artifacts["requirements"] = str(artifact_path.relative_to(self.root))
            self.events.publish(PublishedEvent(f"event-{uuid4().hex}", "ASSET_STATUS_CHANGED", project_id, context, {"node_type": "requirements", "status": "available"}))
            next_index = 1
        checkpoint = PipelineCheckpoint(run_id, task_id, context.tenant_id, context.identity_id, project_id, operation_key, "running", next_index, artifacts)
        if initial_requirements is not None:
            self.orchestrator.report(self._identity(checkpoint), "requirements", "pending_confirmation")
            waiting = replace(checkpoint, status="waiting_human")
            self.queue.wait_for_human(task_id); self._save(waiting); self._task_event(context, waiting, "waiting_human", self._progress(1))
            return waiting
        self._save(checkpoint); return self._run(context, checkpoint)

    def approve(self, context: IdentityContext, project_id: str, run_id: str) -> PipelineCheckpoint:
        checkpoint = self.load(context, project_id, run_id)
        if checkpoint.status != "waiting_human": raise ShortDramaPipelineError("only waiting_human run can be approved")
        state = self.orchestrator.state(self._identity(checkpoint)); completed_stage = str(state.get("current_stage") or "")
        if completed_stage not in NODES: raise ShortDramaPipelineError("orchestrator has no stage awaiting approval")
        state = self.orchestrator.report(self._identity(checkpoint), completed_stage, "completed", confirmation={"confirmed_at":"legacy-user-approval"})
        checkpoint = replace(checkpoint, next_index=self._completed_count(state))
        if not state.get("next_stage"):
            self.queue.resume_human(checkpoint.task_id)
            self.queue.finish(checkpoint.task_id, "completed")
            completed = replace(checkpoint, status="completed")
            self._save(completed); self._task_event(context, completed, "completed", 100)
            return completed
        self.queue.resume_human(checkpoint.task_id)
        return self._run(context, replace(checkpoint, status="approved"))

    def cancel(self, context: IdentityContext, project_id: str, run_id: str) -> PipelineCheckpoint:
        checkpoint = self.load(context, project_id, run_id)
        if checkpoint.status in {"completed", "failed", "cancelled"}: raise ShortDramaPipelineError("terminal run cannot be cancelled")
        graph = self.orchestrator.state(self._identity(checkpoint)); current_stage = str(graph.get("current_stage") or "")
        if current_stage not in NODES: raise ShortDramaPipelineError("orchestrator has no cancellable stage")
        graph = self.orchestrator.report(self._identity(checkpoint), current_stage, "cancelled")
        self.queue.cancel(checkpoint.task_id)
        cancelled = replace(checkpoint, status=str(graph["status"]), next_index=self._projection_index(graph)); self._save(cancelled)
        self._task_event(context, cancelled, "cancelled", self._progress(cancelled.next_index)); return cancelled

    def resume(self, context: IdentityContext, project_id: str, run_id: str) -> PipelineCheckpoint:
        checkpoint = self.load(context, project_id, run_id)
        if checkpoint.status != "running": raise ShortDramaPipelineError("only running checkpoint can resume")
        return self._run(context, checkpoint)

    def load(self, context: IdentityContext, project_id: str, run_id: str) -> PipelineCheckpoint:
        path = self._checkpoint_path(context.tenant_id, project_id, run_id)
        try: data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error: raise ShortDramaPipelineError("checkpoint not found or invalid") from error
        stored = PipelineCheckpoint(**data)
        if stored.user_id != context.identity_id: raise ShortDramaPipelineError("checkpoint is not owned by identity")
        state = self.orchestrator.state(self._identity(stored))
        graph_status = str(state.get("status") or "idle")
        status = "running" if graph_status == "idle" else graph_status
        return replace(stored, status=status, next_index=self._projection_index(state))

    def _run(self, context: IdentityContext, checkpoint: PipelineCheckpoint) -> PipelineCheckpoint:
        artifacts = dict(checkpoint.artifacts)
        try:
            state = self.orchestrator.state(self._identity(checkpoint)); node = str(state.get("next_stage") or "requirements")
            if node not in NODES: raise ShortDramaPipelineError("orchestrator has no executable stage")
            execution = self.orchestrator.execute(self._identity(checkpoint), node, {"artifacts":artifacts})
            output = execution["output"]
            if not isinstance(output, Mapping): raise ShortDramaPipelineError(str(execution.get("error") or f"{node} returned empty output"))
            output = NodeOutput(bytes.fromhex(str(output["content_hex"])), str(output["media_type"]))
            if not output.content or not output.media_type: raise ShortDramaPipelineError(f"{node} returned empty output")
            index = NODES.index(node); artifact_path = self._artifact_path(checkpoint, node, index + 1)
            artifact_path.parent.mkdir(parents=True, exist_ok=True); artifact_path.write_bytes(output.content)
            artifacts[node] = str(artifact_path.relative_to(self.root))
            self.events.publish(PublishedEvent(f"event-{uuid4().hex}", "ASSET_STATUS_CHANGED", checkpoint.project_id, context, {"node_type": node, "status": "available"}))
            checkpoint = replace(checkpoint, status="waiting_human", next_index=self._projection_index(execution), artifacts=artifacts)
            self.queue.wait_for_human(checkpoint.task_id)
            self._save(checkpoint); self._task_event(context, checkpoint, "waiting_human", self._progress(checkpoint.next_index)); return checkpoint
        except Exception:
            self.queue.finish(checkpoint.task_id, "failed")
            failed = PipelineCheckpoint(checkpoint.run_id, checkpoint.task_id, checkpoint.tenant_id, checkpoint.user_id, checkpoint.project_id, checkpoint.operation_key, "failed", checkpoint.next_index, artifacts)
            self._save(failed); self._task_event(context, failed, "failed", self._progress(checkpoint.next_index)); raise

    def _task_event(self, context: IdentityContext, checkpoint: PipelineCheckpoint, status: str, progress: int) -> None:
        self.events.publish(PublishedEvent(f"event-{uuid4().hex}", "TASK_STATUS_CHANGED", checkpoint.project_id, context, {"task_id": checkpoint.task_id, "current_status": status, "progress_percent": progress}))

    def _execute_stage(self, node: str, inputs: Mapping[str, object]) -> Mapping[str, str]:
        artifacts = inputs.get("artifacts")
        if not isinstance(artifacts, Mapping): raise ShortDramaPipelineError("stage artifacts are required")
        output = self.runners[node]({str(key):str(value) for key, value in artifacts.items()})
        return {"content_hex":output.content.hex(), "media_type":output.media_type}

    @staticmethod
    def _identity(checkpoint: PipelineCheckpoint) -> dict[str, str]:
        return {"tenant_id":checkpoint.tenant_id, "user_id":checkpoint.user_id, "project_id":f"{checkpoint.project_id}:{checkpoint.run_id}"}

    @staticmethod
    def _progress(completed: int) -> int: return min(100, completed * 100 // len(NODES))

    @staticmethod
    def _completed_count(state: Mapping[str, object]) -> int:
        stages = state.get("stages") if isinstance(state.get("stages"), Mapping) else {}
        return sum(1 for stage in NODES if stages.get(stage) == "completed")

    @classmethod
    def _projection_index(cls, state: Mapping[str, object]) -> int:
        completed = cls._completed_count(state)
        return min(len(NODES), completed + (1 if state.get("status") == "waiting_human" else 0))

    def _save(self, checkpoint: PipelineCheckpoint) -> None:
        path = self._checkpoint_path(checkpoint.tenant_id, checkpoint.project_id, checkpoint.run_id)
        atomic_write_json(path, asdict(checkpoint), prefix="short-drama-checkpoint-")

    def _checkpoint_path(self, tenant: str, project: str, run: str) -> Path:
        for value in (tenant, project, run): self._safe(value)
        return self.root / tenant / project / "checkpoints" / f"{run}.json"

    def _artifact_path(self, checkpoint: PipelineCheckpoint, node: str, version: int) -> Path:
        return self.root / checkpoint.tenant_id / checkpoint.project_id / "artifacts" / f"{node}-v{version}.bin"

    @staticmethod
    def _safe(value: str) -> None:
        if not SAFE_ID.fullmatch(value): raise ShortDramaPipelineError("identifier is unsafe")
