from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "plugins/builtin/short_drama/frontend/App.vue"


def test_scene_uses_one_45_degree_empty_reference() -> None:
    source = APP.read_text(encoding="utf-8")
    scene = source[source.index("  scene:["):source.index("  prop:[")]
    assert 'label:"45°空场景全景"' in scene
    assert "空间纵深、入口、墙地关系、固定陈设" in scene
    assert scene.count("label:") == 1


def test_scene_and_prop_do_not_generate_2d_variants() -> None:
    source = APP.read_text(encoding="utf-8")
    assert 'if (kind === "scene" || kind === "prop")' in source
    assert "item.detail_assets = []" in source
    assert "await generateAsset3D(kind, item)" in source
    assert "item.model3d_result?.renders" in source
