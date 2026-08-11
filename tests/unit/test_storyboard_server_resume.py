import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"


def load_backend(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._checkpoint_production_stage = lambda *_args, **_kwargs: None
    module._write_storyboard_stream_progress = lambda *_args, **_kwargs: None
    return module


def episode_shots(episode: int, marker: str):
    return [{
        "episode":episode, "shot_number":index + 1,
        "start_second":index * 4, "end_second":index * 4 + 4,
        "visual":f"{marker}-{index + 1}", "action":f"action-{index + 1}",
        "image_url":f"/preserved/{marker}/{index + 1}.png", "status":"confirmed",
        "version":7, "confirmation":{"by":"human"},
    } for index in range(15)]


def body(existing):
    return {
        "stage":"storyboard", "audit_enabled":False, "shots":existing,
        "scripts":[
            {"episode":1, "content":"episode one", "target_duration":60},
            {"episode":2, "content":"episode two", "target_duration":60},
        ],
        "context":{"duration":60},
    }


def test_resume_skips_complete_episode_and_preserves_it_byte_for_byte():
    module = load_backend("storyboard_resume_complete_test")
    existing = episode_shots(1, "existing")
    before = json.dumps(existing, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    calls = []

    def local_api(_body, _stage, endpoint, payload):
        calls.append((endpoint, payload["episode"]))
        return {"storyboard":{"shots":episode_shots(payload["episode"], "new")}}

    module._production_stage_local_api = local_api
    result = module._run_server_production_stage(body(copy.deepcopy(existing)))
    assert calls == [("/api/storyboard", 2)]
    assert result["generated_episodes"] == [2]
    preserved = [shot for shot in result["shots"] if shot["episode"] == 1]
    assert json.dumps(preserved, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == before


def test_partial_episode_is_not_treated_as_complete():
    module = load_backend("storyboard_resume_partial_test")
    calls = []
    module._production_stage_local_api = lambda _body, _stage, _endpoint, payload: (
        calls.append(payload["episode"]) or {"storyboard":{"shots":episode_shots(payload["episode"], "new")}}
    )
    result = module._run_server_production_stage(body(episode_shots(1, "partial")[:4]))
    assert calls == [1, 2]
    assert result["generated_episodes"] == [1, 2]
    assert len(result["shots"]) == 30
    assert not any(shot["visual"].startswith("partial") for shot in result["shots"])


def test_no_missing_episode_makes_zero_model_calls():
    module = load_backend("storyboard_resume_noop_test")
    calls = []
    module._production_stage_local_api = lambda *_args, **_kwargs: calls.append(1)
    existing = [*episode_shots(1, "one"), *episode_shots(2, "two")]
    result = module._run_server_production_stage(body(existing))
    assert calls == []
    assert result["generated_episodes"] == []
    assert result["shots"] == existing


def test_duplicate_existing_shot_is_rejected_before_model_call():
    module = load_backend("storyboard_resume_duplicate_test")
    calls = []
    module._production_stage_local_api = lambda *_args, **_kwargs: calls.append(1)
    duplicate = episode_shots(1, "one")
    duplicate.append(copy.deepcopy(duplicate[0]))
    try:
        module._run_server_production_stage(body(duplicate))
    except ValueError as error:
        assert "duplicate storyboard shot" in str(error)
    else:
        raise AssertionError("duplicate shot must fail closed")
    assert calls == []
