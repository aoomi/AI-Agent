import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
WORKER = ROOT / "plugins/builtin/short_drama/backend/mlx_json_worker.py"


def load_backend():
    spec = importlib.util.spec_from_file_location("compat_server_qwen35_test", BACKEND)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_01_exact_three_model_routes() -> None:
    module = load_backend()
    assert module.TEXT_LIGHT_MODEL == "qwen3.5:9b-q4_K_M"
    assert module.TEXT_FORMAL_MODEL == "qwen3-vl:32b"
    assert module.TEXT_AUDIT_MODEL == "qwen2.5:72b"


def test_02_outline_episode_structure_uses_qwen3_vl_32b() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    assert '_ollama_json(prompt, TEXT_FORMAL_MODEL, TEXT_FORMAL_ESTIMATED_MEMORY,' in source
    assert 'timeout_seconds=OUTLINE_JOB_TIMEOUT_SECONDS, owner_job_id=job_id).get("episodes", [])' in source
    assert "def _ollama_json(\n    prompt: str,\n    model: str = TEXT_LIGHT_MODEL" in source


def test_03_formal_tasks_use_qwen3_vl_32b() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    assert source.count("_ollama_json(prompt, TEXT_FORMAL_MODEL, TEXT_FORMAL_ESTIMATED_MEMORY") >= 4
    assert "base_prompt, TEXT_FORMAL_MODEL, TEXT_FORMAL_ESTIMATED_MEMORY," in source
    assert "num_ctx=4096, num_predict=512" in source


def test_04_audits_use_72b_and_register_auto_repair() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    assert 'if parsed.path == "/api/audit/narrative"' in source
    assert "result = _ollama_json(prompt, TEXT_AUDIT_MODEL, TEXT_AUDIT_ESTIMATED_MEMORY, timeout_seconds=1800, num_ctx=32768)" in source
    assert '("text.narrative.repair", "ollama-qwen25-72b", _narrative_repair)' in source
    assert 'phase = "final" if mode == "final" else "initial"' in source


def test_05_ollama_request_uses_selected_model_and_unloads_it() -> None:
    module = load_backend(); requests = []; unloaded = []
    module._require_memory = lambda value: None
    module._unload_ollama_model = lambda model=None: unloaded.append(model)
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return json.dumps({"response":json.dumps({"ok":True})}).encode()
    module.urlopen = lambda request, **_kwargs: (requests.append(request) or Response())
    assert module._ollama_json("x", module.TEXT_FORMAL_MODEL, 1) == {"ok":True}
    assert json.loads(requests[0].data)["model"] == module.TEXT_FORMAL_MODEL
    assert unloaded == [module.TEXT_FORMAL_MODEL]


def test_05b_qwen3_vl_accepts_structured_output_from_thinking_field() -> None:
    module = load_backend(); module._require_memory = lambda value: None; module._unload_ollama_model = lambda model=None: None
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return json.dumps({"response":"", "thinking":"{\"ok\":true}"}).encode()
    module.urlopen = lambda *_args, **_kwargs: Response()
    assert module._ollama_json("x", module.TEXT_FORMAL_MODEL, 1) == {"ok":True}


def test_06_audit_pass_schema_is_normalized() -> None:
    module = load_backend()
    module._ollama_json = lambda *_args, **_kwargs: {"status":"pass", "summary":"通过", "issues":[]}
    result = module._narrative_audit({"stage":"script", "audit_mode":"final", "content":{"scripts":[]}})
    assert result["status"] == "pass" and result["phase"] == "final"
    assert result["model"] == module.TEXT_AUDIT_MODEL


def test_07_audit_rejects_invalid_needs_fix_schema() -> None:
    module = load_backend()
    module._ollama_json = lambda *_args, **_kwargs: {"status":"needs_fix", "summary":"失败", "issues":[]}
    try: module._narrative_audit({"stage":"outline", "content":{}})
    except ValueError as error: assert "未提供问题" in str(error)
    else: raise AssertionError("invalid audit was accepted")


def test_08_mlx_missing_model_fails_before_inference() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        module.MLX_VLM_PYTHON = Path(temporary) / "python"
        try: module._mlx_json("test")
        except RuntimeError as error: assert "运行环境不存在" in str(error)
        else: raise AssertionError("missing runtime was accepted")


def test_09_heavy_models_are_serial_and_one_shot() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    assert 'with _claim_production_resource("text"' in source
    assert "_unload_ollama_model(model)" in source
    assert "subprocess.run(" in source and "timeout=900" in source
    assert 'if __name__ == "__main__":' in worker


def test_10_health_exposes_all_effective_routes() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    assert '"light": TEXT_LIGHT_MODEL' in source
    assert '"formal": TEXT_FORMAL_MODEL' in source
    assert '"audit": TEXT_AUDIT_MODEL' in source


def test_11_each_narrative_stage_audits_repairs_once_and_reaudits() -> None:
    module = load_backend()
    for stage, key, items in (
        ("outline", "episodes", [{"episode":1, "title":"一"}]),
        ("script", "scripts", [{"episode":1, "title":"一", "content":"正文"}]),
        ("storyboard", "shots", [{"episode":1, "shot_number":1, "visual":"画面"}]),
    ):
        content = {key:items, **({"plan":{"title":"项目"}} if stage == "outline" else {})}
        calls = []
        def invoke(capability, **inputs):
            calls.append(capability)
            if capability == "text.narrative.repair": return {"content":content, "repair_summary":"已修"}
            return {"status":"needs_fix", "summary":"需修", "issues":[{"location":"1", "description":"问题", "suggestion":"修正"}]} if calls.count("audit.narrative") == 1 else {"status":"pass", "summary":"通过", "issues":[]}
        module._invoke_production_capability = invoke
        repaired, audits = module._audit_and_repair_narrative(stage, {}, content)
        assert repaired == content
        assert calls == ["audit.narrative", "text.narrative.repair", "audit.narrative"]
        assert audits[-1]["status"] == "pass"


def test_12_pass_skips_repair_and_long_content_is_chunked() -> None:
    module = load_backend(); calls = []
    def invoke(capability, **inputs):
        calls.append((capability, len(inputs["body"]["content"]["scripts"])))
        return {"status":"pass", "summary":"通过", "issues":[]}
    module._invoke_production_capability = invoke
    scripts = [{"episode":index, "title":str(index), "content":"正文" * 2500} for index in range(1, 4)]
    repaired, audits = module._audit_and_repair_narrative("script", {}, {"scripts":scripts})
    assert repaired["scripts"] == scripts
    assert len(calls) == 3 and all(capability == "audit.narrative" and count == 1 for capability, count in calls)
    assert len(audits) == 3 and all(audit["status"] == "pass" for audit in audits)


def test_11_outline_batch_rejects_duplicate_titles_and_synopses() -> None:
    module = load_backend()
    previous = [{"episode":1, "title":"血脉之力初现", "synopsis":"苏璃首次释放血脉力量震慑众人"}]
    for episode in (
        {"episode":2, "title":"血脉之力初现", "synopsis":"全新事件"},
        {"episode":2, "title":"试炼风云", "synopsis":"苏璃首次释放血脉力量震慑众人"},
    ):
        try: module._validate_outline_episode_batch([episode], 2, 1, previous)
        except ValueError as error: assert "重复" in str(error)
        else: raise AssertionError("duplicate outline episode was accepted")


def test_12_outline_batch_requires_continuous_numbering() -> None:
    module = load_backend()
    try:
        module._validate_outline_episode_batch([{"episode":4, "title":"唯一标题", "synopsis":"唯一事件"}], 3, 1, [])
    except ValueError as error: assert "编号错误" in str(error)
    else: raise AssertionError("non-continuous episode numbering was accepted")


def test_13_outline_generation_carries_full_history_and_state_ledger() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    specification = (ROOT / "plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md").read_text(encoding="utf-8")
    assert "已生成分集与全剧状态" in backend
    assert 'productionLedgerService.runStage<{ plan:OutlinePlan; episodes:EpisodeOutline[]; audit:OutlineAudit | null }>' in frontend
    assert '"previous_episodes":episodes' in backend
    assert "全剧剧情状态表" in specification
    assert "标题必须唯一" in specification
    assert "禁止同名、错字、同音或共享关键字造成近形混淆" in specification


def _valid_episode(number: int, title: str, core: str, villain: str) -> dict:
    return {
        "episode":number, "title":title, "story_stage":f"第{number}集·推进阶段", "core_event":core,
        "protagonist_action":f"苏璃主动执行行动{number}", "ability_progression":f"能力{number}及代价",
        "villain_action":villain, "supporting_motivation":f"盟友动机推进{number}",
        "protection_set_piece":f"宗门护宠场面{number}", "irreversible_change":f"不可逆变化{number}",
        "new_information":f"新线索{number}", "resolved_setup":"无",
        "cliffhanger":f"玉佩显现第{number}道具体血色刻痕", "synopsis":f"第{number}集发生独立事件并改变人物关系",
    }


def test_14_outline_requires_complete_progression_fields() -> None:
    module = load_backend()
    episode = _valid_episode(1, "玉佩示警", "苏璃主动识破毒咒", "沈青梧调换解药并失去一名亲信")
    del episode["protagonist_action"]
    try: module._validate_outline_episode_batch([episode], 1, 1, [])
    except ValueError as error: assert "protagonist_action" in str(error)
    else: raise AssertionError("episode without protagonist action was accepted")


def test_15_outline_rejects_semantic_title_and_villain_repetition() -> None:
    module = load_backend()
    previous = [_valid_episode(1, "血书现形", "苏璃公开长老伪造的血书", "沈青梧策反执法长老围堵苏璃")]
    repeated = _valid_episode(2, "执法堂夜审", "苏璃查出内应名单迫使长老退位", "沈青梧收买执法长老围困苏璃")
    try: module._validate_outline_episode_batch([repeated], 2, 1, previous)
    except ValueError as error: assert "反派手段" in str(error)
    else: raise AssertionError("semantic repetition was accepted")


def test_16_frontend_defaults_audits_and_sends_full_story_state() -> None:
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    backend = BACKEND.read_text(encoding="utf-8")
    assert 'auditEnabledSkills.value = [...allDefaultSkills]' in frontend
    assert 'stage:"outline", audit_enabled:narrativeAuditEnabled.value' in frontend
    assert 'const narrativeAuditPaused = ref(true)' in frontend
    assert '_audit_and_repair_narrative("outline"' in backend
    assert '_audit_and_repair_narrative("script"' in backend
    assert '_audit_and_repair_narrative("storyboard"' in backend
    assert 'if (outlineStatus.value !== "confirmed") {' in frontend
    assert "const confirmed = await confirmOutline();" in frontend
    assert '"all_episode_outlines":outlines' in backend
    assert '"previous_scripts":scripts' in backend


def test_17_outline_rejects_stage_regression() -> None:
    module = load_backend()
    episode = _valid_episode(2, "玉佩裂变", "苏璃封存异变玉佩", "沈青梧投放噬灵虫并失去虫母")
    episode["story_stage"] = "第1集·觉醒阶段"
    try: module._validate_outline_episode_batch([episode], 2, 1, [])
    except ValueError as error: assert "阶段倒流" in str(error)
    else: raise AssertionError("stage regression was accepted")


def test_18_outline_rejects_rephrased_irreversible_change() -> None:
    module = load_backend()
    previous = [_valid_episode(1, "戒律钟鸣", "苏璃查清戒律钟异响", "沈青梧盗走钟芯并暴露密道")]
    previous[0]["irreversible_change"] = "执法长老被罢免并永久失去席位"
    episode = _valid_episode(2, "密道封门", "苏璃主动封闭敌方密道", "沈青梧释放毒雾并损失毒囊")
    episode["irreversible_change"] = "执法长老遭撤职且再也不能进入长老席"
    try: module._validate_outline_episode_batch([episode], 2, 1, previous)
    except ValueError as error: assert "不可逆变化" in str(error)
    else: raise AssertionError("rephrased irreversible change was accepted")


def test_19_outline_rejects_poison_tactic_rephrasing() -> None:
    module = load_backend()
    previous = [_valid_episode(1, "茶盏藏毒", "苏璃验出席间毒茶", "沈青梧命人在茶中下药并损失毒师")]
    episode = _valid_episode(2, "酒坛破封", "苏璃封住灵脉入口", "沈青梧往酒里投毒并失去药囊")
    try: module._validate_outline_episode_batch([episode], 2, 1, previous)
    except ValueError as error: assert "反派手段" in str(error)
    else: raise AssertionError("poison tactic rephrasing was accepted")


def test_20_outline_rejects_ability_regression_and_missing_cost() -> None:
    module = load_backend()
    previous = [_valid_episode(1, "灵光二醒", "苏璃开启二阶灵视", "沈青梧毁坏阵眼并失去阵师")]
    previous[0]["ability_progression"] = "二阶灵视，使用后虚弱一刻钟"
    previous[0]["irreversible_change"] = "护山阵眼永久碎裂"
    regressed = _valid_episode(2, "灵光黯淡", "苏璃追踪残余灵气", "沈青梧伪造密令并暴露笔迹")
    regressed["ability_progression"] = "一阶灵视，使用代价为短暂失明"
    regressed["irreversible_change"] = "密令落款公开暴露"
    try: module._validate_outline_episode_batch([regressed], 2, 1, previous)
    except ValueError as error: assert "能力退阶" in str(error)
    else: raise AssertionError("ability regression was accepted")
    no_cost = _valid_episode(2, "灵光追迹", "苏璃追踪残余灵气", "沈青梧伪造密令并暴露笔迹")
    no_cost["ability_progression"] = "三阶灵视，可看穿所有伪装，无需代价"
    no_cost["irreversible_change"] = "密令落款公开暴露"
    try: module._validate_outline_episode_batch([no_cost], 2, 1, previous)
    except ValueError as error: assert "缺少明确代价" in str(error)
    else: raise AssertionError("ability without cost was accepted")


def test_21_unrelated_irreversible_changes_are_allowed() -> None:
    module = load_backend()
    previous = [_valid_episode(1, "断掌之誓", "苏璃救下受伤掌门", "沈青梧焚毁账册并失去账房")]
    previous[0]["irreversible_change"] = "掌门永久失去右手"
    episode = _valid_episode(2, "宗主失明", "苏璃带宗主撤离暗室", "沈青梧封死暗室并失去钥匙")
    episode["irreversible_change"] = "宗主永久失去左眼"
    assert module._validate_outline_episode_batch([episode], 2, 1, previous) == [episode]
