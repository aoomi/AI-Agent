from pathlib import Path
import importlib.util
import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
MEDIA_SERVICE = (ROOT / "plugins/builtin/short_drama/frontend/services/media.service.ts").read_text(encoding="utf-8")
START_COMFY = Path("/Users/aoo/AI/Projects/ShortDramaPipeline/bin/start_comfy.py").read_text(encoding="utf-8")


def test_chat_reverse_prompt_is_bounded_and_structured() -> None:
    assert '"sips", "-Z", "768"' in BACKEND
    assert '"prompt":"用连续中文短语描述画面的具体内容"' in BACKEND
    assert 'placeholder_terms = (' in BACKEND
    assert 'positive = evidence' in BACKEND
    assert 'parsed.path == "/api/vision"' in BACKEND


def test_image_upscale_is_real_comfy_workflow_and_has_ui_entry() -> None:
    assert 'parsed.path == "/api/images/upscale"' in BACKEND
    assert 'comfy_client.upscale_image_1080p' in BACKEND
    assert 'imageUpscale<T>' in MEDIA_SERVICE
    assert "AI图片超分" in FRONTEND


def test_video_enhancement_uses_realesrgan_and_rife() -> None:
    assert 'comfy_client.upscale_video_720p' in BACKEND
    assert 'RealESRGAN x4 + RIFE 4.9 interpolation' in BACKEND


def test_optional_identity_modes_are_isolated_and_exposed() -> None:
    assert 'parsed.path == "/api/images/identity-refine"' in BACKEND
    assert 'mode not in {"pulid", "reactor"}' in BACKEND
    assert 'identityRefine<T>' in MEDIA_SERVICE
    assert 'PuLID修正' in FRONTEND and 'ReActor修正' in FRONTEND
    assert '"ComfyUI_PuLID_Flux_ll"' in START_COMFY


def test_musetalk_remains_primary_with_latentsync_fallback() -> None:
    spec = importlib.util.spec_from_file_location("optional_media_video_stage", ROOT / "plugins/builtin/short_drama/backend/compat_server.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    command = {"identity":{}, "episode":1, "shot_number":1, "video":{}, "voice":{"text":"你好", "speaker":"voice"}}

    def execute(*, fail_primary=False, cancel_on_fallback=False):
        calls = []; checkpoints = 0; primary_failed = False
        def checkpoint(*_args, **_kwargs):
            nonlocal checkpoints
            checkpoints += 1
            if cancel_on_fallback and primary_failed:
                raise RuntimeError("production stage cancelled or lease lost: video")
        def local(_body, _stage, endpoint, _payload):
            nonlocal primary_failed
            calls.append(endpoint)
            if endpoint == "/api/audio/tts": return {"audio":{"url":"/audio.wav"}}
            if endpoint == "/api/videos/lipsync" and fail_primary:
                primary_failed = True
                raise RuntimeError("musetalk failed")
            if endpoint in {"/api/videos/lipsync", "/api/videos/latentsync"}: return {"video_url":"/synced.mp4", "path":"/synced.mp4", "model":"MuseTalk" if endpoint.endswith("lipsync") else "LatentSync-1.6"}
            return {}
        module._checkpoint_production_stage = checkpoint
        module._production_stage_local_api = local
        module._production_stage_local_get = lambda *_args, **_kwargs: {"status":"completed", "video":{"url":"/source.mp4"}}
        result = module._run_server_production_stage({"stage":"video", "commands":[command], "context":{}})
        return calls, result

    calls, result = execute()
    assert calls.count("/api/videos/lipsync") == 1
    assert "/api/videos/latentsync" not in calls
    assert result["items"][0]["lip_sync_model"] == "MuseTalk"
    calls, result = execute(fail_primary=True)
    assert calls.count("/api/videos/lipsync") == 1 and calls.count("/api/videos/latentsync") == 1
    assert result["items"][0]["lip_sync_model"] == "LatentSync-1.6"
    with pytest.raises(RuntimeError, match="cancelled or lease lost"):
        execute(fail_primary=True, cancel_on_fallback=True)

    generator = FRONTEND[FRONTEND.index("async function generateShotVideos"):FRONTEND.index("function retryShotVideo")]
    assert "mediaService.lipSync" not in generator
    assert "mediaService.latentSync" not in generator
    assert '"/api/videos/lipsync"' in BACKEND and '"/api/videos/latentsync"' in BACKEND
