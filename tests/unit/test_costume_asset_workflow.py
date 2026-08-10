from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
FRONTEND = ROOT / "plugins/builtin/short_drama/frontend/App.vue"
NARRATIVE_TYPES = ROOT / "plugins/builtin/short_drama/frontend/stores/narrative.store.ts"
ASSET_TYPES = ROOT / "plugins/builtin/short_drama/frontend/stores/asset.store.ts"
FULL_SPEC = ROOT / "docs/specs/短剧从剧本到成片生产规范.md"
ASSET_SPEC = ROOT / "docs/specs/短剧3D资产生产规范.md"
AI_SPEC = ROOT / "plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md"


def _module():
    spec = importlib.util.spec_from_file_location("costume_compat", BACKEND)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_storyboard_compiler_binds_costume_per_visible_character():
    module = _module()
    script = "\n".join(
        f"段落{index + 1}\n{index * 3}-{(index + 1) * 3}秒\n画面：苏璃完成动作{index + 1}\n动作：苏璃抬头{index + 1}\n台词：苏璃：来了{index + 1}\n情绪：坚定"
        for index in range(15)
    )
    shots = module._compile_storyboard_from_script(
        script, 1, "国风浅涂", {"camera_rules": ["微推"]}, [{"name": "苏璃"}]
    )
    assert shots[0]["characters"] == [{
        "id": "苏璃", "costume_id": module._costume_id("苏璃"), "costume_version": "v1",
        "action": "苏璃抬头1", "change_type": "initial",
    }]


def test_storyboard_compiler_tracks_explicit_costume_change():
    module = _module()
    blocks = []
    for index in range(15):
        visual = "苏璃换上战斗服迎敌" if index == 5 else f"苏璃推进剧情{index}"
        blocks.append(f"段落{index + 1}\n{index * 3}-{(index + 1) * 3}秒\n画面：{visual}\n动作：苏璃动作{index}\n台词：苏璃：台词{index}\n情绪：坚定")
    shots = module._compile_storyboard_from_script("\n".join(blocks), 1, "国风", {"camera_rules":["微推"]}, [{"name":"苏璃"}])
    assert shots[4]["characters"][0]["costume_id"] == module._costume_id("苏璃", "daily")
    assert shots[5]["characters"][0]["costume_id"] == module._costume_id("苏璃", "battle")
    assert shots[5]["characters"][0]["change_type"] == "change"
    assert shots[6]["characters"][0]["costume_id"] == module._costume_id("苏璃", "battle")


def test_storyboard_costume_change_is_scoped_to_named_character_clause():
    module = _module()
    blocks = []
    for index in range(15):
        visual = "苏璃换上战斗服，陆沉在旁守候" if index == 5 else f"苏璃与陆沉推进剧情{index}"
        blocks.append(f"段落{index + 1}\n{index * 3}-{(index + 1) * 3}秒\n画面：{visual}\n动作：苏璃与陆沉动作{index}\n台词：无\n情绪：坚定")
    shots = module._compile_storyboard_from_script("\n".join(blocks), 1, "国风", {"camera_rules":["微推"]}, [{"name":"苏璃"}, {"name":"陆沉"}])
    changed = {item["id"]:item for item in shots[5]["characters"]}
    continued = {item["id"]:item for item in shots[6]["characters"]}
    assert changed["苏璃"]["change_type"] == "change"
    assert changed["苏璃"]["costume_id"] == module._costume_id("苏璃", "battle")
    assert changed["陆沉"]["change_type"] == "continue"
    assert changed["陆沉"]["costume_id"] == module._costume_id("陆沉", "daily")
    assert continued["陆沉"]["costume_id"] == module._costume_id("陆沉", "daily")


def test_storyboard_costume_change_uses_actual_actor_in_same_clause():
    module = _module()
    changes = module._costume_changes_for_shot("陆沉看着苏璃换上战斗服", ["苏璃", "陆沉"])
    assert changes == {"苏璃":"battle"}
    together = module._costume_changes_for_shot("苏璃与陆沉换上战斗服", ["苏璃", "陆沉"])
    assert together == {"苏璃":"battle", "陆沉":"battle"}
    assert module._costume_changes_for_shot("苏璃脱下战斗服，换上日常服", ["苏璃"]) == {"苏璃":"daily"}
    assert module._costume_changes_for_shot("苏璃脱下战斗服露出日常服", ["苏璃"]) == {"苏璃":"daily"}
    assert module._costume_changes_for_shot("苏璃撕掉战斗服露出常服", ["苏璃"]) == {"苏璃":"daily"}
    assert module._costume_changes_for_shot("苏璃脱下战斗服，陆沉走来，换上礼服", ["苏璃", "陆沉"]) == {"陆沉":"formal"}


def test_storyboard_validator_rejects_incomplete_costume_binding():
    module = _module()
    shot = {
        "start_second": 0, "end_second": 3, "scene": "大殿", "shot_size": "中景", "camera": "微推",
        "visual": "苏璃入殿", "action": "抬头", "dialogue": "无", "sound": "同期声", "image_prompt": "国风",
        "characters": [{"id": "苏璃", "costume_id": ""}],
    }
    try:
        module._validate_storyboard([shot] * 15, 45, "")
    except ValueError as error:
        assert "costume_id" in str(error)
    else:
        raise AssertionError("缺失服装版本必须被拒绝")


def test_costume_is_not_filtered_from_prop_extraction_and_has_runtime_metadata():
    source = BACKEND.read_text(encoding="utf-8")
    assert 'invalid_prop_tokens = ("金光", "光晕", "光效", "特效", "树木", "花草", "山景", "树林")' in source
    assert 'item["asset_type"] = "costume"' in source
    assert 'archive_bucket = "costumes" if is_costume' in source
    assert 'archive_id = _safe_name(job.get("costume_id")' in source
    assert '"costume_version":str(body.get("costume_version") or "v1")' in source
    assert '"日常服", "战斗服", "练功服", "常服", "华服"' in source
    assert "缺少明确owner，禁止作为无主服装入库" in source


def test_frontend_sends_costume_metadata_and_keeps_costumes_in_prop_store():
    app = FRONTEND.read_text(encoding="utf-8")
    assets = ASSET_TYPES.read_text(encoding="utf-8")
    narrative = NARRATIVE_TYPES.read_text(encoding="utf-8")
    assert 'asset_type:(item as PropProfile).category === "服装"' in app
    assert 'costume_id:(item as PropProfile).costume_id' in app
    assert '人物服装：${(shot.characters || [])' in app
    assert 'asset_type?:"prop"|"costume"' in assets
    assert "characters?:StoryboardCharacterCostume[]" in narrative
    assert "capability_not_implemented：独立服装穿衣蒙皮链尚未完成" in app
    assert "characters:shot.characters || []" in app


def test_server_blocks_costume_change_before_image_job_registration():
    source = BACKEND.read_text(encoding="utf-8")
    gate = source.index('"error":"capability_not_implemented"')
    registration = source.index('name = body.get("name") or f"shot_', gate)
    assert gate < registration
    assert 'parsed.path in {"/api/shots/generate", "/api/shots/repair"}' in source


def test_all_authoritative_specs_define_costume_asset_and_shot_binding():
    for path in (FULL_SPEC, ASSET_SPEC, AI_SPEC):
        text = path.read_text(encoding="utf-8")
        assert "costume_id" in text
        assert "costume_version" in text or "costume_id@version" in text
        assert "服装" in text and "道具" in text
        assert "45" in text and "TripoSR" in text and "Blender" in text
