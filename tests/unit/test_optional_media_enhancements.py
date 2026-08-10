from pathlib import Path


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
    primary = FRONTEND.index("mediaService.lipSync")
    fallback = FRONTEND.index("mediaService.latentSync", primary)
    assert primary < fallback
    assert 'item.lip_sync_model = "MuseTalk"' in FRONTEND
