from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
WORKER = (ROOT / "plugins/builtin/short_drama/backend/asset_3d_worker.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")


def test_blender_produces_real_h3_source_video():
    assert 'source_video = output / "blender_source.mp4"' in WORKER
    assert 'bpy.ops.render.render(animation=True)' in WORKER
    assert '"fps":24, "frames":96' in WORKER
    assert '"source_video_url": _asset_3d_media_url(source_video)' in BACKEND
    assert '"source_video_spec": dict(report.get("source_video_spec") or {})' in BACKEND


def test_h3_ref2va_graph_uses_video_and_identity_as_separate_inputs():
    assert 'def _generate_h3_rv2v_video' in BACKEND
    assert '"class_type":"MiniMaxH3ReferenceToVideo"' in BACKEND
    assert '"ref_image_1":["5",0]' in BACKEND
    assert '"ref_video_1":["6",0]' in BACKEND
    assert '"class_type":"VHS_LoadVideoPath"' in BACKEND
    assert 'H3_REF2VA_MODEL = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"' in BACKEND


def test_video_route_selects_h3_only_when_both_references_exist():
    assert 'use_h3_rv2v = bool(body.get("source_video_url") and body.get("identity_reference_url"))' in BACKEND
    assert 'engine="minimax-h3-ref2va"' in BACKEND
    assert 'else "Wan2.2"' in BACKEND
    assert '("video.shot.h3_ref2va", "comfy-minimax-h3-ref2va", _generate_h3_rv2v_video)' in BACKEND


def test_frontend_forwards_confirmed_3d_video_and_approved_portrait():
    assert 'asset.model3d_status === "confirmed" && asset.model3d_result?.source_video_url' in FRONTEND
    assert 'source_video_url:matched3DAsset.model3d_result!.source_video_url' in FRONTEND
    assert 'identity_reference_url:matchedCharacter.image_url' in FRONTEND


def test_h3_prompt_is_cancelled_on_all_lifecycle_paths():
    stop = BACKEND[BACKEND.index("def _stop_video_generation"):BACKEND.index("def _resume_persisted_task")]
    recover = BACKEND[BACKEND.index("def _recover_video_jobs"):BACKEND.index("def _load_resources")]
    helper = BACKEND[BACKEND.index("def _generate_h3_rv2v_video"):BACKEND.index("def _generate_video_job")]
    assert "_cancel_job_comfy_prompts(job)" in stop
    assert recover.count("_cancel_job_comfy_prompts(job)") >= 2
    assert "finally:" in helper and "_cancel_comfy_prompt(prompt_id)" in helper
