from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "shared/contracts/domain.schema.json").read_text(encoding="utf-8"))
NOW = "2026-08-07T12:00:00Z"
VERSION = "1.0"

VALID_CASES = {
    "identity": {"identity_id": "identity-1", "identity_kind": "user", "display_name": "Owner", "is_active": True, "created_at": NOW, "contract_version": VERSION},
    "authorization": {"request_id": "request-1", "identity_id": "identity-1", "tenant_id": "tenant-default", "action": "project.read", "scope_kind": "project", "scope_id": "project-1", "decision": "denied", "denial_reason": "PERMISSION_MISSING", "evaluated_at": NOW, "contract_version": VERSION},
    "tenant": {"tenant_id": "tenant-default", "name": "Default", "status": "active", "created_at": NOW, "contract_version": VERSION},
    "project": {"project_id": "project-1", "tenant_id": "tenant-default", "owner_identity_id": "identity-1", "name": "Project", "status": "active", "created_at": NOW, "updated_at": NOW, "contract_version": VERSION},
    "project_transition": {"project_id": "project-1", "tenant_id": "tenant-default", "transition": "draft:active", "request_id": "request-1", "operation_key": "activate-project-1", "actor_identity_id": "identity-1", "occurred_at": NOW, "contract_version": VERSION},
    "task": {"task_id": "task-1", "tenant_id": "tenant-default", "project_id": "project-1", "operation_key": "create-project-1", "task_type": "contract_test", "status": "waiting_human", "progress_percent": 50, "created_at": NOW, "updated_at": NOW, "contract_version": VERSION},
    "task_transition": {"task_id": "task-1", "tenant_id": "tenant-default", "project_id": "project-1", "transition": "running:waiting_human", "request_id": "request-2", "operation_key": "pause-for-review", "actor_identity_id": "identity-1", "occurred_at": NOW, "contract_version": VERSION},
    "idempotency": {"request_id": "request-2", "operation_key": "pause-for-review", "request_fingerprint": "a" * 64, "outcome": "accepted", "task_id": "task-1", "evaluated_at": NOW, "contract_version": VERSION},
    "human_gate": {"gate_id": "gate-1", "task_id": "task-1", "tenant_id": "tenant-default", "project_id": "project-1", "gate_type": "content_review", "status": "pending", "created_at": NOW, "contract_version": VERSION},
    "plugin": {"plugin_id": "short_drama", "name": "Short Drama", "version": "1.0.0", "source": "builtin", "status": "discovered", "compatible_platform_versions": ["1.0"], "required_permissions": [], "contract_version": VERSION},
    "plugin_manifest": {"plugin_id": "short_drama", "name": "Short Drama", "version": "1.0.0", "platform_version_range": ">=1.0 <2.0", "provider": "Yingxu", "source": "builtin", "capabilities": ["script.write"], "permissions": ["model.invoke"], "dependencies": [{"capability": "image.generate", "kind": "replaceable_input"}], "data_scopes": ["project.assets"], "frontend_slots": ["workspace.preview"], "backend_entry": "backend/main.py", "migration_entry": "migrations/main.py", "uninstall_policy": "retain", "integrity_hash": "sha256:" + "a" * 64, "contract_version": VERSION},
    "plugin_transition": {"plugin_id": "short_drama", "transition": "installed:enabled", "request_id": "request-3", "operation_key": "enable-short-drama", "actor_identity_id": "identity-1", "occurred_at": NOW, "contract_version": VERSION},
    "asset": {"asset_id": "asset-1", "tenant_id": "tenant-default", "project_id": "project-1", "task_id": "task-1", "asset_type": "script", "status": "available", "storage_key": "projects/project-1/script.json", "media_type": "application/json", "byte_size": 0, "checksum_sha256": "a" * 64, "created_at": NOW, "contract_version": VERSION},
    "asset_version": {"asset_version_id": "asset-version-1", "asset_id": "asset-1", "tenant_id": "tenant-default", "project_id": "project-1", "task_id": "task-1", "version_number": 1, "parent_asset_version_id": "", "storage_key": "projects/project-1/script-v1.json", "media_type": "application/json", "byte_size": 0, "checksum_sha256": "a" * 64, "provenance": {"provider": "yingxu", "provider_version": "1.0.0", "model_id": "", "model_version": "", "prompt_version": "prompt-1", "source_asset_version_ids": []}, "created_at": NOW, "contract_version": VERSION},
    "asset_invalidation": {"invalidation_id": "invalidate-1", "tenant_id": "tenant-default", "project_id": "project-1", "scope_kind": "shot", "scope_id": "shot-1", "affected_asset_version_ids": ["asset-version-1"], "reason": "UPSTREAM_CHANGED", "preserve_history": True, "request_id": "request-4", "actor_identity_id": "identity-1", "invalidated_at": NOW, "contract_version": VERSION},
    "asset_export": {"export_id": "export-1", "tenant_id": "tenant-default", "project_id": "project-1", "task_id": "task-1", "asset_version_ids": ["asset-version-1"], "export_format": "json", "status": "queued", "output_storage_key": "", "checksum_sha256": "", "request_id": "request-5", "operation_key": "export-project-1", "created_at": NOW, "updated_at": NOW, "contract_version": VERSION},
    "error": {"code": 409, "msg": "conflict", "data": {"request_id": "request-1", "error_code": "OPERATION_CONFLICT", "details": {}}, "timestamp": 0},
    "event": {"event_id": "event-1", "event_type": "TASK_STATUS_CHANGED", "occurred_at": NOW, "request_id": "request-1", "trace_id": "trace-1", "tenant_id": "tenant-default", "project_id": "project-1", "actor_identity_id": "identity-1", "payload": {"task_id": "task-1", "previous_status": "running", "current_status": "waiting_human"}, "contract_version": VERSION},
}


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        {"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]},
        format_checker=FormatChecker(),
    )


class DomainSchemaTest(unittest.TestCase):
    def test_all_contracts_accept_valid_and_boundary_fixtures(self) -> None:
        for name, fixture in VALID_CASES.items():
            with self.subTest(contract=name):
                validator(name).validate(fixture)

    def test_required_fields_reject_empty_objects(self) -> None:
        for name in VALID_CASES:
            with self.subTest(contract=name):
                self.assertTrue(list(validator(name).iter_errors({})))

    def test_invalid_enumerations_are_rejected(self) -> None:
        for name, field in (("identity", "identity_kind"), ("authorization", "action"), ("tenant", "status"), ("project", "status"), ("task", "status"), ("plugin", "status"), ("asset", "status"), ("event", "event_type")):
            fixture = deepcopy(VALID_CASES[name])
            fixture[field] = "invalid"
            with self.subTest(contract=name):
                self.assertTrue(list(validator(name).iter_errors(fixture)))

    def test_task_progress_boundaries_and_asset_path_safety(self) -> None:
        for progress in (0, 100):
            fixture = {**VALID_CASES["task"], "progress_percent": progress}
            validator("task").validate(fixture)
        for progress in (-1, 101):
            fixture = {**VALID_CASES["task"], "progress_percent": progress}
            self.assertTrue(list(validator("task").iter_errors(fixture)))
        unsafe = {**VALID_CASES["asset"], "storage_key": "../secret.txt"}
        self.assertTrue(list(validator("asset").iter_errors(unsafe)))

    def test_unknown_fields_and_wrong_contract_version_are_rejected(self) -> None:
        fixture = {**VALID_CASES["project"], "unexpected": True}
        self.assertTrue(list(validator("project").iter_errors(fixture)))
        fixture = {**VALID_CASES["project"], "contract_version": "2.0"}
        self.assertTrue(list(validator("project").iter_errors(fixture)))

    def test_null_payload_and_null_error_detail_are_rejected(self) -> None:
        event = {**VALID_CASES["event"], "payload": None}
        self.assertTrue(list(validator("event").iter_errors(event)))
        error = deepcopy(VALID_CASES["error"])
        error["data"]["details"] = {"secret": None}
        self.assertTrue(list(validator("error").iter_errors(error)))

    def test_event_type_requires_matching_payload(self) -> None:
        event = deepcopy(VALID_CASES["event"])
        event["event_type"] = "PROJECT_CREATED"
        self.assertTrue(list(validator("event").iter_errors(event)))
        event["payload"] = {"project_id": "project-1", "status": "active"}
        validator("event").validate(event)

    def test_error_code_catalog_is_closed(self) -> None:
        error = deepcopy(VALID_CASES["error"])
        error["data"]["error_code"] = "UNKNOWN_ERROR"
        self.assertTrue(list(validator("error").iter_errors(error)))

    def test_authorization_decision_controls_denial_reason(self) -> None:
        denied = deepcopy(VALID_CASES["authorization"])
        denied.pop("denial_reason")
        self.assertTrue(list(validator("authorization").iter_errors(denied)))
        allowed = {**denied, "decision": "allowed"}
        validator("authorization").validate(allowed)
        allowed["denial_reason"] = "PERMISSION_MISSING"
        self.assertTrue(list(validator("authorization").iter_errors(allowed)))

    def test_illegal_task_transition_is_rejected(self) -> None:
        fixture = {**VALID_CASES["task_transition"], "transition": "completed:running"}
        self.assertTrue(list(validator("task_transition").iter_errors(fixture)))

    def test_idempotency_outcomes_have_distinct_shapes(self) -> None:
        replayed = {**VALID_CASES["idempotency"], "outcome": "replayed", "original_request_id": "request-1"}
        validator("idempotency").validate(replayed)
        conflict = deepcopy(replayed)
        conflict["outcome"] = "conflict"
        conflict.pop("task_id")
        validator("idempotency").validate(conflict)
        conflict["task_id"] = "task-1"
        self.assertTrue(list(validator("idempotency").iter_errors(conflict)))

    def test_pending_human_gate_cannot_be_bypassed(self) -> None:
        pending = deepcopy(VALID_CASES["human_gate"])
        pending["decided_by_identity_id"] = "identity-1"
        pending["decided_at"] = NOW
        self.assertTrue(list(validator("human_gate").iter_errors(pending)))
        resolved = {**pending, "status": "approved"}
        validator("human_gate").validate(resolved)

    def test_plugin_permissions_dependencies_and_paths_are_closed(self) -> None:
        manifest = deepcopy(VALID_CASES["plugin_manifest"])
        manifest["permissions"] = ["subprocess.execute"]
        self.assertTrue(list(validator("plugin_manifest").iter_errors(manifest)))
        manifest = deepcopy(VALID_CASES["plugin_manifest"])
        manifest["dependencies"][0]["kind"] = "optional"
        self.assertTrue(list(validator("plugin_manifest").iter_errors(manifest)))
        manifest = deepcopy(VALID_CASES["plugin_manifest"])
        manifest["backend_entry"] = "../escape.py"
        self.assertTrue(list(validator("plugin_manifest").iter_errors(manifest)))

    def test_plugin_lifecycle_rejects_skipped_or_reversed_transitions(self) -> None:
        for transition in ("discovered:enabled", "uninstalled:enabled", "enabled:installed"):
            fixture = {**VALID_CASES["plugin_transition"], "transition": transition}
            self.assertTrue(list(validator("plugin_transition").iter_errors(fixture)))

    def test_asset_versions_and_invalidation_preserve_history(self) -> None:
        version = {**VALID_CASES["asset_version"], "version_number": 0}
        self.assertTrue(list(validator("asset_version").iter_errors(version)))
        invalidation = {**VALID_CASES["asset_invalidation"], "preserve_history": False}
        self.assertTrue(list(validator("asset_invalidation").iter_errors(invalidation)))
        invalidation = {**VALID_CASES["asset_invalidation"], "affected_asset_version_ids": []}
        self.assertTrue(list(validator("asset_invalidation").iter_errors(invalidation)))

    def test_asset_export_rejects_unsafe_output_and_empty_inputs(self) -> None:
        export = {**VALID_CASES["asset_export"], "output_storage_key": "../secret.zip"}
        self.assertTrue(list(validator("asset_export").iter_errors(export)))
        export = {**VALID_CASES["asset_export"], "asset_version_ids": []}
        self.assertTrue(list(validator("asset_export").iter_errors(export)))
        completed = {**VALID_CASES["asset_export"], "status": "completed"}
        self.assertTrue(list(validator("asset_export").iter_errors(completed)))
        completed.update(output_storage_key="exports/project-1.json", checksum_sha256="b" * 64)
        validator("asset_export").validate(completed)


if __name__ == "__main__":
    unittest.main()
