from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")


def test_silent_composition_is_explicit_and_does_not_generate_audio():
    block = BACKEND[BACKEND.index("def _composition_capability"):BACKEND.index("def _subtitle_reburn_capability")]
    assert 'audio_mode not in {"full_mix", "none"}' in block
    assert 'include_audio=audio_mode == "full_mix"' in block
    assert 'if audio_mode == "none":' in block
    assert 'concat_arguments.extend(["-an"])' in block
    silent = block[block.index('if audio_mode == "none":', block.index("_run_ffmpeg(concat_arguments")):]
    assert '"audio_mode":"none"' in silent
    assert '"production_evidence":"ffmpeg-concat-video-only-v1"' in silent
    assert '_invoke_production_capability("audio.bgm"' in block[block.index("return {"):]


def test_video_only_normalization_maps_no_audio_stream():
    block = BACKEND[BACKEND.index("def _normalize_shot_media"):BACKEND.index("def _subtitle_timestamp")]
    assert "if not include_audio:" in block
    assert '"-map", "0:v:0", "-an"' in block
