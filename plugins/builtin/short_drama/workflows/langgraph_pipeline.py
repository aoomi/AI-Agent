"""Compatibility facade over the single production orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ai_agent_core import atomic_write_json

from .pipeline import NODES, NodeOutput, NodeRunner, ShortDramaPipelineError
from .production_orchestrator import ProductionOrchestrator


class ShortDramaLangGraphPipeline:
    """Legacy API surface; all decisions and checkpoints belong to ProductionOrchestrator."""

    def __init__(self, root: Path, runners: Mapping[str, NodeRunner]) -> None:
        if not isinstance(root, Path):
            raise ShortDramaPipelineError("pipeline root must be a Path")
        self.root = root.resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.runners = dict(runners); missing = set(NODES) - self.runners.keys()
        if missing: raise ShortDramaPipelineError(f"missing node runners: {sorted(missing)}")
        self.orchestrator = ProductionOrchestrator(self.root / "production-kernel.sqlite")
        for stage in NODES:
            self.orchestrator.register_stage(stage, lambda inputs, key=stage: self._execute(key, inputs), provider_id="legacy-langgraph-adapter")

    def start(self, run_id: str, requirements: NodeOutput) -> dict[str, Any]:
        if not requirements.content or not requirements.media_type: raise ShortDramaPipelineError("requirements returned empty output")
        artifacts = {"requirements":self._write(run_id, "requirements", requirements)}
        self._save_artifacts(run_id, artifacts)
        result = self.orchestrator.report(self._identity(run_id), "requirements", "pending_confirmation")
        return {**result, "artifacts":artifacts, "__interrupt__":[{"value":{"action":"confirm_stage","stage":"requirements","run_id":run_id}}]}

    def resume(self, run_id: str, approved: bool) -> dict[str, Any]:
        identity = self._identity(run_id); state = self.orchestrator.state(identity); current = str(state.get("current_stage") or "")
        artifacts = self._load_artifacts(run_id)
        if not approved:
            result = self.orchestrator.report(identity, current, "cancelled")
            return {**result, "artifacts":artifacts}
        advanced = self.orchestrator.report(identity, current, "completed", confirmation={"confirmed_at":"legacy-user-approval"})
        next_stage = str(advanced.get("next_stage") or "")
        if not next_stage:
            return {**advanced, "artifacts":artifacts}
        execution = self.orchestrator.execute(identity, next_stage, {"run_id":run_id, "artifacts":artifacts})
        output = execution.get("output")
        if not isinstance(output, Mapping): raise ShortDramaPipelineError(str(execution.get("error") or "stage execution failed"))
        artifacts[next_stage] = str(output["path"]); self._save_artifacts(run_id, artifacts)
        return {**execution, "artifacts":artifacts, "__interrupt__":[{"value":{"action":"confirm_stage","stage":next_stage,"run_id":run_id}}]}

    def state(self, run_id: str) -> dict[str, Any]:
        return {**self.orchestrator.state(self._identity(run_id)), "artifacts":self._load_artifacts(run_id)}

    def _execute(self, node: str, inputs: Mapping[str, Any]) -> Mapping[str, str]:
        run_id = str(inputs.get("run_id") or ""); artifacts = inputs.get("artifacts")
        if not run_id or not isinstance(artifacts, Mapping): raise ShortDramaPipelineError("run and artifacts are required")
        output = self.runners[node]({str(key):str(value) for key, value in artifacts.items()})
        return {"path":self._write(run_id, node, output)}

    def _write(self, run_id: str, node: str, output: NodeOutput) -> str:
        if not output.content or not output.media_type: raise ShortDramaPipelineError(f"{node} returned empty output")
        path = self.root / run_id / f"{node}.bin"; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(output.content)
        return str(path.relative_to(self.root))

    def _manifest(self, run_id: str) -> Path:
        return self.root / run_id / "artifacts.json"

    def _save_artifacts(self, run_id: str, artifacts: Mapping[str, str]) -> None:
        atomic_write_json(self._manifest(run_id), dict(artifacts))

    def _load_artifacts(self, run_id: str) -> dict[str, str]:
        try: raw = json.loads(self._manifest(run_id).read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (OSError, json.JSONDecodeError, ValueError) as error: raise ShortDramaPipelineError("artifact manifest not found or invalid") from error
        if not isinstance(raw,dict) or any(key not in NODES or not isinstance(value,str) or not value for key,value in raw.items()):
            raise ShortDramaPipelineError("artifact manifest not found or invalid")
        return dict(raw)

    @staticmethod
    def _identity(run_id: str) -> dict[str, str]:
        return {"tenant_id":"legacy", "user_id":"pipeline", "project_id":run_id}
