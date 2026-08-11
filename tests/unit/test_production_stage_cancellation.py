import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import threading

import pytest

from ai_agent_queue import TaskLeaseRepository


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"


def load_backend(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("stage", ["outline", "script", "storyboard", "assets", "image", "video", "composition", "review_export"])
def test_cancelled_stage_never_submits_first_local_call(stage: str) -> None:
    module = load_backend(f"stage_cancel_before_{stage}")
    event = threading.Event(); event.set(); calls = []
    module._local_api = lambda path, body: calls.append((path, body)) or {}
    module._local_get = lambda path: calls.append((path, None)) or {}
    payload = {
        "stage":stage, "_cancel_event":event, "context":{"episode_count":2},
        "episodes":[{"episode":1}], "scripts":[{"episode":1, "content":"x"}],
        "commands":[{"episode":1, "shot_number":1}],
    }
    with pytest.raises(RuntimeError, match="cancelled or lease lost"):
        module._run_server_production_stage(payload)
    assert calls == []


def test_outline_cancelled_mid_batch_does_not_submit_next_batch() -> None:
    module = load_backend("stage_cancel_outline_mid_batch")
    event = threading.Event(); calls = []
    def local(path, _body):
        calls.append(path)
        if path.endswith("/plan"):
            return {"plan":{"general_outline":"x"}}
        event.set()
        return {"episodes":[{"episode":1}]}
    module._local_api = local
    with pytest.raises(RuntimeError, match="cancelled or lease lost"):
        module._run_server_production_stage({"stage":"outline", "_cancel_event":event, "context":{"episode_count":3}, "batch_size":1})
    assert calls == ["/api/outline/plan", "/api/outline/episodes"]


def test_outline_cancelled_after_initial_audit_does_not_repair_or_final_audit() -> None:
    module = load_backend("stage_cancel_outline_audit")
    event = threading.Event(); capability_calls = []

    def local(path, _body):
        if path.endswith("/plan"):
            return {"plan":{"general_outline":"x"}}
        return {"episodes":[{"episode":1, "title":"x"}]}

    def invoke(capability, **kwargs):
        capability_calls.append(capability)
        assert "_cancel_event" not in kwargs["body"]
        event.set()
        return {"status":"needs_fix", "issues":[{"issue":"x"}]}

    module._local_api = local
    module._invoke_production_capability = invoke
    with pytest.raises(RuntimeError, match="cancelled or lease lost"):
        module._run_server_production_stage({
            "stage":"outline", "_cancel_event":event, "audit_enabled":True,
            "context":{"episode_count":1}, "batch_size":1,
        })
    assert capability_calls == ["audit.narrative"]


def test_video_cancelled_during_poll_does_not_start_audio_or_next_command() -> None:
    module = load_backend("stage_cancel_video_poll")
    event = threading.Event(); api_calls = []; get_calls = []
    module._local_api = lambda path, _body: api_calls.append(path) or {}
    def local_get(path):
        get_calls.append(path); event.set(); return {"status":"pending"}
    module._local_get = local_get
    commands = [
        {"episode":1, "shot_number":1, "identity":{}, "video":{}, "voice":{"text":"对白"}},
        {"episode":1, "shot_number":2, "identity":{}, "video":{}},
    ]
    with pytest.raises(RuntimeError, match="cancelled or lease lost"):
        module._run_server_production_stage({"stage":"video", "_cancel_event":event, "commands":commands})
    assert api_calls == ["/api/videos/generate"]
    assert len(get_calls) == 1


def test_stage_cancel_is_exactly_tenant_scoped_and_uses_existing_lease_event() -> None:
    module = load_backend("stage_cancel_tenant_scope")
    with TemporaryDirectory() as temporary:
        module.TASK_LEASES = TaskLeaseRepository(Path(temporary) / "leases.sqlite")
        module.WORKER_ID = "worker"
        owner = {"tenant_id":"tenant-a", "user_id":"user-a", "project_id":"project", "stage":"image"}
        foreign = {"tenant_id":"tenant-b", "user_id":"user-a", "project_id":"project", "stage":"image"}
        with pytest.raises(RuntimeError, match="cancelled or lease lost"):
            with module._claim_production_stage_request(owner, "image") as event:
                assert module._cancel_scoped_production_stage(foreign, "image") == 0
                assert not event.is_set()
                assert module._cancel_scoped_production_stage(owner, "image") == 1
                assert event.is_set()
                module._checkpoint_production_stage({**owner, "_cancel_event":event}, "image")


def test_run_stage_checks_cancel_before_pending_confirmation_commit() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    handler = source[source.index('if parsed.path == "/api/production/run-stage"'):source.index("production_stage = PRODUCTION_ENDPOINT_STAGES", source.index('if parsed.path == "/api/production/run-stage"'))]
    assert handler.index("_run_server_production_stage(body)") < handler.index("_ensure_production_stage_request_active(cancel_event, stage)")
    assert handler.index("_ensure_production_stage_request_active(cancel_event, stage)") < handler.index("_commit_server_production_stage_result(")


def test_child_job_stop_scope_rejects_foreign_tenant() -> None:
    module = load_backend("stage_cancel_child_scope")
    job = {"request":{"tenant_id":"tenant-a", "user_id":"user", "project_id":"project"}}
    assert module._job_matches_scope(job, {"tenant_id":"tenant-a", "user_id":"user", "project_id":"project"})
    assert not module._job_matches_scope(job, {"tenant_id":"tenant-b", "user_id":"user", "project_id":"project"})
    legacy = {"subject_key":"tenant-a:user:project:1:1"}
    assert module._job_matches_scope(legacy, {"tenant_id":"tenant-a", "user_id":"user", "project_id":"project"})
    assert not module._job_matches_scope(legacy, {"tenant_id":"tenant-a", "user_id":"other", "project_id":"project"})


def test_stop_routes_cancel_stage_before_exact_child_and_support_video_keys() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    generation = source[source.index('if parsed.path == "/api/generation/stop"'):source.index('if parsed.path == "/api/audit/narrative"')]
    assert generation.index("_cancel_scoped_production_stage") < generation.index("_stop_text_generation")
    image = source[source.index('if parsed.path in {"/api/characters/stop", "/api/images/stop"}'):source.index('if parsed.path == "/api/tasks/resume"')]
    assert image.index("_cancel_scoped_production_stage") < image.index("_stop_image_generation")
    video = image[image.index('if parsed.path == "/api/videos/stop"'):image.index('if parsed.path == "/api/tasks/stop"')]
    assert 'for key in body.get("keys") or []:' in video
    assert video.index("_cancel_scoped_production_stage") < video.index("_stop_video_generation")
    assert 'stage in {"composition", "merged_episodes", "review_export", "final_audit", "export", "upscale"}' in image
