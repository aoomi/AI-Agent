import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location("local_video_provider_contract", ROOT / "plugins/builtin/short_drama/backend/compat_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wan_provider_can_be_selected_even_when_h3_references_are_present():
    source = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    block = source[source.index("def _generate_video_job"):source.index("def _launch_waiting_video_job")]
    assert 'requested_provider == VIDEO_PROVIDER_H3' in block
    assert 'not requested_provider and bool(body.get("source_video_url")' in block
    assert 'width=704,height=1280,steps=30' in block
    assert 'engine=VIDEO_PROVIDER_WAN22' in block


def test_video_provider_ids_are_explicit_and_stable():
    module = _load_module()
    assert module.VIDEO_PROVIDER_IDS == {"wan2.2-ti2v-5b", "minimax-h3-ref2va"}
