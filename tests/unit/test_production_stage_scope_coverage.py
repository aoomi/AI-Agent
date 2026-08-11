from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"


def load_backend(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def confirmed(stage: str, scope_type: str, scope_id: str) -> dict:
    fingerprint = f"fp:{stage}:{scope_type}:{scope_id}"
    audit_batch_id = f"batch:{stage}:{scope_type}:{scope_id}"
    return {
        "stage": stage,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "lifecycle": "completed",
        "content_fingerprint": fingerprint,
        "audit_batch_id": audit_batch_id,
        "confirmation": {"confirmed": True, "content_fingerprint": fingerprint, "audit_batch_id": audit_batch_id},
    }


def pending(stage: str, scope_type: str, scope_id: str) -> dict:
    return {
        "stage": stage,
        "scope_type": scope_type,
        "scope_id": scope_id,
        "lifecycle": "pending_confirmation",
        "confirmation": None,
    }


def prior_records() -> list[dict]:
    return [
        confirmed("requirements", "project", "project-a"),
        confirmed("outline", "project", "project-a"),
        confirmed("script", "episode", "1"),
        confirmed("storyboard", "shot", "1:1"),
        confirmed("storyboard", "shot", "1:2"),
        confirmed("assets", "asset", "character:hero"),
    ]


class FakeBrain:
    def __init__(self) -> None:
        self.stages = {
            stage: "completed"
            for stage in ("requirements", "outline", "script", "storyboard", "assets")
        }
        self.reports: list[tuple[str, str, dict]] = []

    def state(self, _identity: dict) -> dict:
        return {"stages": dict(self.stages)}

    def report(self, _identity: dict, stage: str, status: str, **metadata: object) -> dict:
        self.reports.append((stage, status, dict(metadata)))
        self.stages[stage] = status
        return self.state({})

    def begin(self, _identity: dict, stage: str, **_metadata: object) -> dict:
        if stage == "video" and self.stages.get("image") != "completed":
            raise ValueError("previous stage is not completed: image")
        return {"accepted": stage}


class FakeLedger:
    def __init__(self, records: list[dict]) -> None:
        self.records = records

    def list(self, _identity: dict) -> list[dict]:
        return list(self.records)


def configure(module, records: list[dict]) -> FakeBrain:
    brain = FakeBrain()
    module._production_orchestrator = lambda: brain
    module.PRODUCTION_LEDGER = FakeLedger(records)
    return brain


@pytest.mark.parametrize(
    "image_records",
    [
        [confirmed("image", "shot", "1:1"), pending("image", "shot", "1:2")],
        [confirmed("image", "shot", "1:1")],
    ],
)
def test_stage_entry_rejects_partial_or_missing_shot_coverage(image_records: list[dict]) -> None:
    module = load_backend("stage_scope_partial")
    brain = configure(module, [*prior_records(), *image_records])

    with pytest.raises(ValueError, match="previous stage is not completed: image"):
        module._begin_production_request(
            {"tenant_id": "tenant-a", "user_id": "user-a", "project_id": "project-a"},
            "video",
        )

    assert not any(stage == "image" and status == "completed" for stage, status, _ in brain.reports)


def test_stage_entry_promotes_only_after_one_episode_has_complete_shot_coverage() -> None:
    module = load_backend("stage_scope_complete")
    records = [*prior_records(), confirmed("image", "shot", "1:1"), confirmed("image", "shot", "1:2")]
    brain = configure(module, records)

    result = module._begin_production_request(
        {"tenant_id": "tenant-a", "user_id": "user-a", "project_id": "project-a"},
        "video",
    )

    assert result == {"accepted": "video"}
    image_reports = [item for item in brain.reports if item[0] == "image"]
    assert len(image_reports) == 1
    assert image_reports[0][1] == "completed"
    assert image_reports[0][2]["reconciled_from"] == "production_ledger"
    assert "trusted" not in image_reports[0][2]


def test_media_gate_allows_a_later_complete_episode_without_accepting_partial_first_episode() -> None:
    module = load_backend("stage_scope_episode")
    records = [
        confirmed("storyboard", "shot", "1:1"),
        confirmed("storyboard", "shot", "1:2"),
        confirmed("storyboard", "shot", "2:1"),
        confirmed("image", "shot", "1:1"),
        pending("image", "shot", "1:2"),
        confirmed("image", "shot", "2:1"),
    ]

    gate = module._stage_gate_records("image", records)

    assert [item["scope_id"] for item in gate] == ["1:1", "1:2", "2:1"]
    assert module._production_stage_gate_complete("image", records) is True


@pytest.mark.parametrize("stage", ["image", "video", "audio", "subtitle"])
def test_media_gate_rejects_and_retains_scope_outside_storyboard_census(stage: str) -> None:
    module = load_backend(f"stage_scope_extra_{stage}")
    records = [
        confirmed("storyboard", "shot", "1:1"),
        confirmed(stage, "shot", "1:1"),
        confirmed(stage, "shot", "1:2"),
    ]

    gate = module._stage_gate_records(stage, records)

    assert [item["scope_id"] for item in gate[:2]] == ["1:1", "1:2"]
    assert any(item.get("scope_id") == "unexpected-media:1:2" for item in gate)
    assert module._production_stage_gate_complete(stage, records) is False


@pytest.mark.parametrize("scope_id", ["01:1", "1:01", " 1:1", "1:1 ", "1/1", "1:0"])
def test_media_gate_rejects_noncanonical_or_invalid_scope_alias(scope_id: str) -> None:
    module = load_backend("stage_scope_invalid_alias")
    records = [confirmed("storyboard", "shot", "1:1"), confirmed("image", "shot", scope_id)]

    gate = module._stage_gate_records("image", records)

    assert gate[0]["scope_id"] == scope_id
    assert any(str(item.get("scope_id") or "").startswith("invalid-media:") for item in gate)
    assert module._production_stage_gate_complete("image", records) is False


def test_media_gate_rejects_duplicate_scope_and_non_shot_scope_type() -> None:
    module = load_backend("stage_scope_duplicate")
    records = [
        confirmed("storyboard", "shot", "1:1"),
        confirmed("image", "shot", "1:1"),
        confirmed("image", "shot", "1:1"),
        confirmed("image", "episode", "1"),
    ]

    gate = module._stage_gate_records("image", records)

    assert [item["scope_id"] for item in gate[:3]] == ["1:1", "1:1", "1"]
    assert any(item.get("scope_id") == "duplicate-media:1:1" for item in gate)
    assert any(str(item.get("scope_id") or "").startswith("invalid-scope-type:") for item in gate)
    assert module._production_stage_gate_complete("image", records) is False


def test_media_gate_rejects_duplicate_or_alias_collision_in_storyboard_census() -> None:
    module = load_backend("stage_scope_duplicate_target")
    duplicate = [
        confirmed("storyboard", "shot", "1:1"),
        confirmed("storyboard", "shot", "1:1"),
        confirmed("image", "shot", "1:1"),
    ]
    alias = [
        confirmed("storyboard", "shot", "1:1"),
        confirmed("storyboard", "shot", "01:1"),
        confirmed("image", "shot", "1:1"),
    ]

    assert module._production_stage_gate_complete("image", duplicate) is False
    assert module._production_stage_gate_complete("image", alias) is False


def test_media_gate_multiepisode_boundary_allows_one_complete_target_episode_but_not_extra_episode() -> None:
    module = load_backend("stage_scope_multiepisode")
    valid = [
        confirmed("storyboard", "shot", "1:1"),
        confirmed("storyboard", "shot", "1:2"),
        confirmed("storyboard", "shot", "2:1"),
        confirmed("image", "shot", "1:1"),
        confirmed("image", "shot", "2:1"),
    ]
    with_extra_episode = [*valid, confirmed("image", "shot", "3:1")]

    assert module._production_stage_gate_complete("image", valid) is True
    assert module._production_stage_gate_complete("image", with_extra_episode) is False
    assert any(item.get("scope_id") == "unexpected-media:3:1" for item in module._stage_gate_records("image", with_extra_episode))


@pytest.mark.parametrize("stage", ["image", "video", "audio", "subtitle"])
@pytest.mark.parametrize("evidence_case", ["missing_fingerprint", "missing_batch", "confirmation_mismatch", "valid"])
def test_media_gate_requires_current_fingerprint_batch_and_matching_confirmation(stage: str, evidence_case: str) -> None:
    module = load_backend(f"stage_scope_evidence_{stage}_{evidence_case}")
    media = confirmed(stage, "shot", "1:1")
    if evidence_case == "missing_fingerprint":
        media["content_fingerprint"] = ""
    elif evidence_case == "missing_batch":
        media["audit_batch_id"] = ""
    elif evidence_case == "confirmation_mismatch":
        media["confirmation"] = {
            **media["confirmation"],
            "content_fingerprint": "stale-fingerprint",
            "audit_batch_id": "stale-batch",
        }
    records = [confirmed("storyboard", "shot", "1:1"), media]

    expected = evidence_case == "valid"
    assert module._confirmed_production_gate_record(media) is expected
    assert module._production_stage_gate_complete(stage, records) is expected


def test_non_media_gate_does_not_require_media_fingerprint_confirmation_contract() -> None:
    module = load_backend("stage_scope_non_media_evidence")
    record = {
        "stage":"outline", "scope_type":"project", "scope_id":"project-a",
        "lifecycle":"completed", "confirmation":{"confirmed":True},
        "content_fingerprint":"", "audit_batch_id":"",
    }

    assert module._confirmed_production_gate_record(record) is True
    assert module._production_stage_gate_complete("outline", [record]) is True


@pytest.mark.parametrize("stage", ["image", "video", "audio", "subtitle"])
def test_media_gate_fails_closed_without_storyboard_census(stage: str) -> None:
    module = load_backend(f"stage_scope_no_census_{stage}")
    gate = module._stage_gate_records(stage, [confirmed(stage, "shot", "1:1")])

    assert any(item.get("scope_id") == "missing-storyboard-census" for item in gate)
    assert module._production_stage_gate_complete(stage, [confirmed(stage, "shot", "1:1")]) is False


def test_confirm_and_reconcile_share_one_gate_fact_definition() -> None:
    source = BACKEND_PATH.read_text(encoding="utf-8")
    assert source.count("_production_stage_gate_complete(") >= 4
    begin = source[source.index("def _begin_production_request"):source.index("class Handler")]
    assert "_reconcile_completed_production_stages(identity, records)" in begin
    assert "completed_records" not in begin
    assert 'evidence={"source":"production_ledger"}' not in begin
