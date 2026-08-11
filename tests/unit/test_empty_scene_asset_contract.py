from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
APP_PATH = ROOT / "plugins/builtin/short_drama/frontend/App.vue"


def _load_backend():
    spec = importlib.util.spec_from_file_location("empty_scene_contract_backend", BACKEND_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scene_extraction_rejects_character_actions_and_rebuilds_empty_prompt():
    module = _load_backend()
    source = [
        {"name": "苏璃跪在地上", "location": "宗门广场", "image_prompt": "苏璃跪地"},
        {"name": "弟子们哄笑中纷纷上前抢夺", "location": "宗门广场"},
        {"name": "全宗门弟子突然齐声高呼", "location": "宗门广场"},
        {"name": "宗门大殿", "location": "宗门大殿", "layout": "高台与石柱", "lighting": "清晨冷光", "fixed_elements": ["牌匾"]},
    ]
    result = module._normalize_empty_scene_assets(source, ["苏璃"])
    assert [item["name"] for item in result] == ["宗门大殿"]
    prompt = result[0]["image_prompt"]
    assert "高台与石柱" in prompt
    assert "无人物、无人形、无人体、无文字" in prompt
    assert "苏璃" not in prompt


def test_storyboard_compiler_carries_detected_reusable_location_instead_of_character_action():
    module = _load_backend()
    assert module._scene_location_from_text("背景是古色古香的宗门试炼场，青石铺地") == "宗门试炼场"
    assert module._scene_location_from_text("地点在藏经阁，四周书架高耸") == "藏经阁"
    assert module._scene_location_from_text("地点：藏经阁，夜间冷光") == "藏经阁"
    for invalid in ("苏璃", "云长老", "苏璃被夺走玉佩", "苏璃跪在地上", "弟子们哄笑中纷纷上前抢夺", "全宗门弟子突然齐声高呼", "玉佩被夺走后藏进仓库", "病人被推进医院", "车辆失控冲入商场"):
        assert module._is_reusable_empty_scene_name(invalid, ["苏璃"]) is False
    assert module._is_reusable_empty_scene_name("宗门试炼场", ["苏璃", "云长老"]) is True
    for location in ("厨房", "客厅", "医院", "学校", "教室", "办公室", "公司", "商场", "酒店", "车站", "机场", "码头", "仓库", "工厂", "寺庙"):
        assert module._is_reusable_empty_scene_name(location, ["苏璃", "云长老"]) is True


def test_frontend_filters_historical_action_scenes_on_every_ingress():
    frontend = APP_PATH.read_text(encoding="utf-8")
    assert "function isReusableSceneAssetName" in frontend
    assert "function normalizeEmptySceneProfiles" in frontend
    assert frontend.count("normalizeEmptySceneProfiles(") >= 6
    assert "sceneProfiles.value = normalizeEmptySceneProfiles" in frontend
    assert "纯环境与建筑，无人物、无人形、无人体、无文字" in frontend


def test_scene_generation_rejects_invalid_subject_before_job_cleanup():
    backend = BACKEND_PATH.read_text(encoding="utf-8")
    body_parse = backend.index("body = self._body()")
    forwarding = backend.index("_forward_production_request", body_parse)
    early_gate = backend.index('parsed.path == "/api/characters/generate"', body_parse)
    assert body_parse < early_gate < forwarding
    assert "_project_character_names(body)" in backend[early_gate:forwarding]
    gate = backend.index('if requested_kind == "scene" and requested_phase == "baseline"')
    cleanup = backend.index("_cleanup_invalid_image_tasks()", gate)
    assert gate < cleanup
    assert "invalid_scene_asset_subject" in backend[gate:cleanup]
    assert "不能是人物动作或人物状态" in backend[gate:cleanup]


def test_authoritative_character_names_support_outline_plan_before_assets_exist(tmp_path):
    module = _load_backend()
    module.PROJECTS_FILE = tmp_path / "projects.json"
    module.PROJECTS_FILE.write_text(
        '{"version":1,"projects":[{"id":"p1","tenant_id":"t1","user_id":"u1","stage_state":{"outline":{"data":{"plan":{"characters":[{"name":"苏璃"},{"name":"云长老"}]}}}}}]}',
        encoding="utf-8",
    )
    assert module._project_character_names({"project_id":"p1", "tenant_id":"t1", "user_id":"u1"}) == ["苏璃", "云长老"]
    assert module._project_character_names({"project_id":"p1", "tenant_id":"other", "user_id":"u1"}) == []
