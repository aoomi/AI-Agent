from pathlib import Path
import importlib.util
import re


ROOT = Path(__file__).resolve().parents[2]
BACKEND = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
WORKER = (ROOT / "plugins/builtin/short_drama/backend/asset_3d_worker.py").read_text(encoding="utf-8")
APP = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
ASSET_CARD = (ROOT / "plugins/builtin/short_drama/frontend/components/business/UnifiedAssetCard.vue").read_text(encoding="utf-8")
SPEC_3D = (ROOT / "docs/specs/短剧3D资产生产规范.md").read_text(encoding="utf-8")
SPEC_FULL = (ROOT / "docs/specs/短剧从剧本到成片生产规范.md").read_text(encoding="utf-8")
SPEC_AI = (ROOT / "plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md").read_text(encoding="utf-8")
SPEC_VIDEO = (ROOT / "docs/specs/视频模型选择规则.md").read_text(encoding="utf-8")
SPEC_GENRE = (ROOT / "docs/specs/题材音画参数模板.md").read_text(encoding="utf-8")
BACKEND_SPEC = importlib.util.spec_from_file_location("asset_3d_spec_runtime", ROOT / "plugins/builtin/short_drama/backend/compat_server.py")
assert BACKEND_SPEC and BACKEND_SPEC.loader
BACKEND_MODULE = importlib.util.module_from_spec(BACKEND_SPEC)
BACKEND_SPEC.loader.exec_module(BACKEND_MODULE)


def test_klein9b_reference_generation_is_fixed_to_8bit_8_steps():
    assert 'mlx-community/flux2-klein-9b-8bit' in BACKEND
    assert '"--base-model", "flux2-klein-9b", "--steps", "8"' in BACKEND
    assert 'model="FLUX.2 Klein 9B 8-bit"' in BACKEND
    assert 'reference_angle = "left_45_full" if kind == "character" else "three_quarter_45"' in BACKEND


def test_character_first_card_is_left_45_full_body():
    assert 'label:"左45°全身"' in APP
    assert 'label:"0°正面全身"' in APP
    assert '严格左45度完整全身照' in APP
    assert 'label:"90°侧面全身"' in APP
    assert 'label:"180°背面全身"' in APP
    assert 'label:"0°正面半身"' in APP
    assert 'reference_angle:kind === "character" ? "left_45_full" : "three_quarter_45"' in APP
    assert 'baseline_confirmed:Boolean(item.baseline_confirmed_at)' in APP


def test_character_3d_rejects_missing_or_unconfirmed_left45_baseline(monkeypatch):
    monkeypatch.setattr(BACKEND_MODULE, "_assert_image_job_runnable", lambda _job_id: None)
    invalid = (
        {"asset_kind":"character", "reference_angle":"left_45_full", "baseline_confirmed":True},
        {"asset_kind":"character", "reference_angle":"front_full", "source_baseline_url":"/x.png", "baseline_confirmed":True},
        {"asset_kind":"character", "reference_angle":"left_45_full", "source_baseline_url":"/x.png", "baseline_confirmed":False},
    )
    for payload in invalid:
        try:
            BACKEND_MODULE._generate_asset_3d(payload, "job")
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid character 3D input accepted: {payload}")


def test_runtime_ai_spec_uses_six_views_but_only_left45_as_3d_baseline():
    assert "人物资产固定六图" in SPEC_AI
    assert "先生成左45度全身基准并人工确认" in SPEC_AI
    for token in ("腰部裁切", "手部完全出画", "约占画高75%", "双肩不触边", "纯色无杂物背景"):
        assert token in SPEC_AI
    assert "TripoSR只读取已确认左45度全身基准图" in SPEC_AI


def test_prop_and_scene_use_one_confirmed_45_reference_then_blender_renders():
    assert 'label:"45°三分之二视图"' in APP
    assert 'label:"45°空场景全景"' in APP
    assert 'if (kind === "scene" || kind === "prop")' in APP
    assert 'await generateAsset3D(kind, item)' in APP
    assert 'for (const render of item.model3d_result?.renders || [])' in APP
    assert 'readOnly:true' in APP
    assert 'source_baseline = _reference_path(source_baseline_url)' in BACKEND
    assert 'shutil.copy2(source_baseline, reference)' in BACKEND


def test_four_character_references_reach_storyboard_generation_and_audit():
    assert 'usage:"clothing_body", url:character.image_url!' in APP
    assert 'asset.label === "0°正面半身" ? "face_primary" : "angle_continuity"' in APP
    assert 'usage:"clothing_body", url:asset.image_url!' in APP
    assert 'detail.label === "0°正面半身" ? "face_primary" : "angle_continuity"' in APP
    generator = BACKEND[BACKEND.index("def _generate_multireference_shot"):BACKEND.index("def _apply_storyboard_face_lock")]
    assert 'usage=angle_continuity' in generator
    assert 'All four references jointly constrain one character' in generator
    audit = BACKEND[BACKEND.index("def _audit_shot_consistency"):BACKEND.index("def _remote_cuda_image")]
    assert '{"face_primary", "clothing_body", "angle_continuity"}' in audit


def test_3d_api_has_unique_job_and_existing_lifecycle_guards():
    assert 'if parsed.path == "/api/assets/3d/generate"' in BACKEND
    assert 'job_id = str(uuid4())' in BACKEND
    assert 'subject_key = f"{project_id}:3d:{kind}:{asset_name}"' in BACKEND
    assert 'expected_subject = f"{project_id}:3d:{kind}:{asset_name}"' in BACKEND
    assert 'str(job.get("subject_key") or "") != expected_subject' in BACKEND
    assert 'ACTIVE_IMAGE_SUBJECTS[subject_key] = job_id' in BACKEND
    assert 'workflow":"asset_3d"' in BACKEND
    assert 'if parsed.path == "/api/assets/3d/status"' in BACKEND
    assert 'target=_execute_asset_3d_job' in BACKEND
    assert 'HTTPStatus.ACCEPTED' in BACKEND
    assert 'def _assert_image_job_runnable' in BACKEND
    assert 'current_status in {"failed", "completed"}' in BACKEND
    assert 'preflight_job.get("status") in {"failed", "completed"}' in BACKEND
    assert 'preflight_started' in BACKEND and 'preflight_hard_timeout' in BACKEND


def test_worker_runs_tripors_then_blender_and_emits_seven_audit_views():
    assert '"--pretrained-model-name-or-path", str(TRIPOSR_MODEL)' in WORKER
    assert '"--device", "mps"' in WORKER
    assert 'scene.render.engine = "BLENDER_EEVEE"' in WORKER
    assert 'scene.render.engine = "CYCLES"' in WORKER
    assert 'scene.cycles.samples = 64' in WORKER
    for label in ("front_0", "left_45", "right_45", "side_90", "back_180", "top", "bottom"):
        assert f'("{label}"' in WORKER
    assert '"RGB", "Alpha/Mask", "Depth/Z", "Normal"' in WORKER


def test_worker_enforces_asset_specific_face_caps_and_deliverables():
    assert '{"character": 50_000, "prop": 20_000, "scene": 200_000}' in WORKER
    assert 'asset_clean.glb' in WORKER
    assert 'asset_clean.blend' in WORKER
    assert '"origin_policy": "asset_ground_center"' in WORKER
    assert 'bpy.ops.mesh.delete_loose' in WORKER
    assert 'bpy.ops.mesh.fill_holes' in WORKER
    assert 'non_manifold_edges' in WORKER


def test_frontend_exposes_generate_stop_confirm_and_downloads():
    for token in ("generateAsset3D", "stopAsset3D", "confirmAsset3D", '@generate3d="generateAsset3D', '@confirm3d="confirmAsset3D', '@stop3d="stopAsset3D'):
        assert token in APP
    assert 'model3d_status' in APP
    assert 'model_url' in ASSET_CARD and 'blend_url' in ASSET_CARD
    assert 'item.model3d_job_id = accepted.job_id' in APP
    assert 'assetService.status3D' in APP
    assert 'assetService.confirm3D' in APP


def test_confirmed_3d_channels_are_consumed_by_storyboard_generation():
    for token in ('usage:"spatial_structure"', 'usage:"depth_control"', 'usage:"normal_control"', 'usage:"mask_control"'):
        assert token in APP
    assert 'if parsed.path == "/api/assets/3d/confirm"' in BACKEND
    assert 'version_root' in BACKEND and 'staged.replace(archive_root)' in BACKEND
    assert 'archive_root.replace(backup)' in BACKEND
    assert 'backup.replace(archive_root)' in BACKEND
    assert 'def _recover_asset_3d_archive_backups' in BACKEND


def test_identity_boundary_is_explicit_in_both_specs():
    statement = "TripoSR生成的3D渲染图仅用于审核模型结构、姿态、服装/道具的大致对应关系，不执行面部特征相似度比对；面部一致性只由2D身份审核链锁定。"
    assert statement in SPEC_3D
    assert statement in SPEC_FULL


def test_3d_scope_and_dynamic_spatial_anchors_are_normative():
    for token in ("场景", "道具", "人物", "灵兽", "原地动作", "行走", "奔跑", "跳跃", "受力", "倒地", "跪地", "抱起", "背负", "跟拍", "环绕", "变焦", "快速切镜", "0.1米"):
        assert token in SPEC_3D


def test_cross_module_delivery_and_extreme_boundaries_are_normative():
    for token in ("禁止直接使用TripoSR人物模型的人脸渲染图", "头部强制蒙版", "最远人物", "tts_duration",
                  "spatial_visual_conflict", "fallback_review", "output/failed/3d/", "data/shared/3d/",
                  "registry.json", "资产ID", "gaze_target", "gaze_transition_duration"):
        assert token in SPEC_3D
    assert "Klein参考图阶段总尝试最多2次" in SPEC_3D
    assert "TripoSR阶段总尝试最多3次" in SPEC_3D
    assert "Blender阶段总尝试最多3次" in SPEC_3D
    assert "只统计已经耗尽单任务尝试并落为`failed`的独立服务端job" in SPEC_3D
    assert "禁止自动创建第四个job" in SPEC_3D
    assert "3D资产链按当前执行器分阶段计数" in SPEC_FULL
    assert "Klein最多2次、TripoSR最多3次、Blender最多3次" in SPEC_FULL
    for token in ("输入不合格", "许可不符", "模型或依赖缺失", "结构性错误不得自动重试", "重新通过内存门禁"):
        assert token in SPEC_AI


def test_ai_spec_has_unique_sections_and_runtime_receives_3d_preamble():
    for section in "一 二 三 四 五 六 七 八 九 十 十一 十二 十三 十四".split():
        assert len(re.findall(rf"(?m)^<!-- AI_SPEC_SECTION:{section} -->$", SPEC_AI)) == 1
    assert "男主角 → 女主角 → 其他人物 → 道具 → 场景" not in SPEC_AI
    assert "资产页面当前从上到下的可见顺序" in SPEC_AI
    for stage in ("outline", "script", "storyboard", "assets", "image", "video", "audio", "post", "final"):
        selected = BACKEND_MODULE._production_spec_for(stage)
        for token in ("3D头部必须蒙版隔离", "fallback_review", "当前租户资产域内全局唯一", "gaze_target"):
            assert token in selected


def test_full_chain_conflict_closures_reach_runtime_specs():
    for token in ("55—65秒", "问题段", "1—3个镜头", "首尾各保留2帧", "occlusion_start_frame",
                  "FaceNet/ArcFace", "_vN", "超过总镜头数30%", "3D建模独占GPU",
                  "data/shared/3d/registry.json", "style_fallback=true"):
        assert token in SPEC_FULL
    assert "60‑70秒" not in SPEC_AI and "60-70秒" not in SPEC_AI
    assert "单段时长超3s即按3s" not in SPEC_AI
    script_spec = BACKEND_MODULE._production_spec_for("script")
    storyboard_spec = BACKEND_MODULE._production_spec_for("storyboard")
    assets_spec = BACKEND_MODULE._production_spec_for("assets")
    video_spec = BACKEND_MODULE._production_spec_for("video")
    final_spec = BACKEND_MODULE._production_spec_for("final")
    assert "55—65秒" in script_spec and "问题段" in script_spec
    assert "1—3镜" in storyboard_spec and "首尾各保留2帧" in storyboard_spec
    assert "FaceNet/ArcFace" in assets_spec and "当前租户资产域内2D/3D全局唯一" in assets_spec
    assert "普通镜头I2V" in video_spec and "遮挡体及起止帧" in video_spec
    assert "超过30%" in final_spec and "最新审核通过版本" in final_spec
    assert "禁止静默整集重制" in final_spec and "1080×1920" in final_spec
    assert 'body["duration"] = _validated_episode_duration(body.get("duration", 60))' in BACKEND
    assert 'invalid_episode_duration' in BACKEND


def test_video_selection_and_genre_templates_are_authoritative():
    for token in ("普通单参考镜头使用I2V", "纯空镜", "R2V", "4—8秒", "2帧缓冲", "model_blocked"):
        assert token in SPEC_VIDEO
    for token in ("风格映射键", "SHA-256", "style_fallback=true", "单镜LoRA强度微调", "IP-Adapter不属于该例外"):
        assert token in SPEC_GENRE
    for genre in ("古装", "都市爽文", "仙侠", "甜宠", "悬疑", "民国", "科幻末世", "校园"):
        assert f"| {genre} |" in SPEC_GENRE


def test_unimplemented_normative_capabilities_are_not_claimed_as_live():
    assert "当前待开发项包括" in SPEC_FULL and "capability_not_implemented" in SPEC_FULL
    assert "partial_production" in SPEC_VIDEO and "H3 Ref2VA" in SPEC_VIDEO
    assert "T2V、通用多素材R2V自动选路" in SPEC_VIDEO and "仍为待开发项" in SPEC_VIDEO
    assert "pending_development" in SPEC_GENRE
    assert "能力状态门禁" in SPEC_AI and "禁止声称已执行" in SPEC_AI


def test_episode_duration_validator_rejects_instead_of_silent_clamp():
    for value in (55, 60, 65):
        assert BACKEND_MODULE._validated_episode_duration(value) == value
    for value in (54, 66, 100, "bad", 55.5, 65.9, True):
        try:
            BACKEND_MODULE._validated_episode_duration(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"duration should be rejected: {value}")
    assert "invalid_episode_duration" in BACKEND
    assert "max(55, min(65" not in BACKEND
