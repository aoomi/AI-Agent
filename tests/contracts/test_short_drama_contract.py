from __future__ import annotations

import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator,FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "shared/contracts/short-drama.schema.json").read_text(encoding="utf-8"))


class ShortDramaContractTest(unittest.TestCase):
    def test_pipeline_fixture_is_valid(self) -> None:
        fixture = {
            "run_id": "run-1", "tenant_id": "tenant-a", "project_id": "project-a",
            "task_id": "task-1", "operation_key": "operation-1", "status": "running",
            "current_node": "script", "completed_nodes": ["requirements", "outline"],
            "artifacts": [{"artifact_id": "artifact-1", "artifact_version": 1, "node_type": "outline", "storage_key": "projects/project-a/outline.json", "media_type": "application/json", "checksum_sha256": "a" * 64}],
            "contract_version": "1.0",
        }
        Draft202012Validator({"$ref": "#/$defs/pipeline_run", "$defs": SCHEMA["$defs"]}).validate(fixture)

    def test_unsafe_artifact_path_is_rejected(self) -> None:
        validator = Draft202012Validator({"$ref": "#/$defs/artifact", "$defs": SCHEMA["$defs"]})
        artifact = {"artifact_id": "a", "artifact_version": 1, "node_type": "outline", "storage_key": "../secret", "media_type": "text/plain", "checksum_sha256": "a" * 64}
        self.assertTrue(list(validator.iter_errors(artifact)))

    def test_node_catalog_has_exactly_eleven_nodes(self) -> None:
        self.assertEqual(len(SCHEMA["$defs"]["node_type"]["enum"]), 11)

    def test_langgraph_checkpoint_covers_all_nodes(self) -> None:
        nodes=SCHEMA["$defs"]["node_type"]["enum"]
        value={"checkpoint_id":"cp-1","thread_id":"thread-1","run_id":"run-1","current_nodes":["script"],"next_nodes":["storyboard"],"node_executions":[{"node_type":node,"status":"completed" if node in nodes[:2] else "pending","dependencies":[],"input_artifact_ids":[],"output_artifact_ids":[],"attempt":1 if node in nodes[:2] else 0,"max_attempts":3,"error_code":None} for node in nodes],"created_at":"2026-08-07T12:00:00Z","updated_at":"2026-08-07T12:00:00Z","contract_version":"1.0"}
        self.assertFalse(list(Draft202012Validator({"$ref":"#/$defs/checkpoint","$defs":SCHEMA["$defs"]},format_checker=FormatChecker()).iter_errors(value)))

    def test_lora_randomness_requires_explicit_exploration(self) -> None:
        validator=Draft202012Validator({"$ref":"#/$defs/lora_selection","$defs":SCHEMA["$defs"]})
        base={"mode":"automatic","drama_genre":"都市甜宠","selected_lora_id":"cn-romance","selected_lora_version":"1.0","locked":True,"match_reason":"genre exact match","exploration_seed":None,"contract_version":"1.0"}
        self.assertFalse(list(validator.iter_errors(base)));self.assertTrue(list(validator.iter_errors({**base,"exploration_seed":42})));self.assertFalse(list(validator.iter_errors({**base,"mode":"exploration","locked":False,"exploration_seed":42})))


if __name__ == "__main__": unittest.main()
