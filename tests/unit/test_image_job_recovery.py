from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
FRONTEND = ROOT / "plugins/builtin/short_drama/frontend/App.vue"


def test_flux_scene_prop_variants_force_klein9b_cfg_1_5_and_20_steps() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    branch = backend.split('if references and asset_phase == "variant" and asset_kind in {"scene", "prop"}:', 1)[1].split("else:", 1)[0]
    assert 'guidance=1.5, steps=20' in branch
    assert '"cfg":1.5, "steps":20' in branch
    assert 'model=ASSET_3D_KLEIN9B_MODEL, base_model="flux2-klein-9b", quantize=8' in branch
    assert '"generation_workflow":"FLUX.2 Klein 9B MLX 8-bit"' in branch
    prop_retry = backend.split('name=f"{name}_no_person_retry"', 1)[1].split('if asset_phase == "baseline"', 1)[0]
    scene_retry = backend.split('name=f"{name}_empty_scene_retry_{validation_attempt + 2}"', 1)[1].split('if asset_phase == "baseline"', 1)[0]
    for retry in (prop_retry, scene_retry):
        assert 'guidance=1.5, steps=20' in retry
        assert 'model=ASSET_3D_KLEIN9B_MODEL, base_model="flux2-klein-9b", quantize=8' in retry
        assert 'if references and asset_phase == "variant"' in retry
    final_metadata = backend.split('if references and asset_phase == "variant" and asset_kind in {"scene", "prop"}:', 2)[2].split("if required_text:", 1)[0]
    for token in ('"generation_workflow":"FLUX.2 Klein 9B MLX 8-bit"', '"workflow_mode":"direct_fixed_angle_no_qwen"', '"base_model":"flux2-klein-9b"', '"quantization":"8-bit"', '"cfg":1.5', '"steps":20'):
        assert token in final_metadata


def test_qwen_character_dossier_supports_left_right_45_and_fixed_seed() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    frontend = FRONTEND.read_text(encoding="utf-8")
    qwen = backend.split("def _generate_qwen_character_variant(", 1)[1].split("def _generate_ipadapter_image", 1)[0]
    for pose in ("left_45_full", "right_45_full"):
        assert f'"{pose}"' in qwen
    assert 'character_sheet_urls: list[str] | None = None' in qwen
    assert 'graph["14"]["inputs"]["image3"]' in qwen
    assert 'fixed_seed = int(hashlib.sha256(identity_source.read_bytes()).hexdigest()[:8], 16)' in qwen
    assert 'graph["19"]["inputs"]["seed"] = fixed_seed' in qwen
    assert 'sheet_input.unlink(missing_ok=True)' in qwen
    assert 'except Exception:\n        identity_input.unlink(missing_ok=True)' in qwen
    assert qwen.index('except Exception:\n        identity_input.unlink(missing_ok=True)') < qwen.index('angle_prompt = (')
    assert 'character_sheet_reference_count' in qwen
    assert 'character_sheet_urls=[str(item.get("url") or "") for item in references[1:]' in backend
    assert 'label:"左45°全身"' in frontend and 'label:"右45°全身"' in frontend
    assert 'Maintain consistent character identity and costume details across all angles' in frontend
    assert 'slide.variant?.status === "waiting_confirmation"' in frontend
    assert 'variant.status = "waiting_confirmation"' in frontend
    assert 'asset.status === "confirmed" && asset !== variant' in frontend
    assert 'if (variant.status === "waiting_confirmation") return' in frontend
    assert 'if (item.status !== "confirmed") await generateAssetVariantsFromConfirmedBaseline(kind, item)' in frontend
    generator = backend.split("def _generate_image(", 1)[1].split("def _klein9b_houtu_loras", 1)[0]
    assert 'command.extend(["--guidance", str(float(guidance))])' in generator
    assert '"--steps", str(effective_steps)' in generator


def test_stale_image_jobs_are_failed_and_resumable() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    frontend = FRONTEND.read_text(encoding="utf-8")

    assert "ACTIVE_IMAGE_JOBS: set[str] = set()" in backend
    assert "ACTIVE_IMAGE_PROCESSES" in backend
    assert "def _recover_image_jobs()" in backend
    assert "def _monitor_image_jobs()" in backend
    assert "看门狗已回收无实际进程的图片任务" in backend
    assert "_terminate_process_tree" in backend
    assert "applyInterruptedStageRecovery(resumeStages)" in frontend
    resume = frontend[frontend.index("function applyInterruptedStageRecovery"):frontend.index("type OutlineStageData")]
    assert "generateAllAssetImages()" not in resume
    assert "上次资产任务已中断，请点击生成图片继续" in resume
    for call in ("generateOutline(", "generateScripts(", "generateStoryboards(", "generateShotImages(", "generateShotVideos(", "mergeEpisodes(", "auditFinalEpisodes(", "runUpscale(", "createExports("):
        assert call not in resume
    assert '"active_job" in payload' in frontend
    assert 'item.generation_nonce = activeJob.slice' in frontend
    assert 'includes("图片任务已中断")' in frontend
    assert 'APPLICATION_ROOT / "output"' in backend
    assert "Drama_Pipeline_ceshi/output" not in backend


def test_image_jobs_have_process_heartbeat_timeout_and_single_retry() -> None:
    backend = BACKEND.read_text(encoding="utf-8")

    assert '"job_id":job_id' in backend
    assert '"heartbeat_at":_iso_now()' in backend
    assert "IMAGE_TASK_TIMEOUT_SECONDS" in backend
    assert "IMAGE_QUEUE_TIMEOUT_SECONDS" in backend
    assert "max_attempts: int = 2" in backend
    assert "for attempt in range(max(1, max_attempts))" in backend
    assert "start_new_session=True" in backend
    assert "os.killpg" in backend
    assert "_cleanup_invalid_image_tasks()" in backend
    assert "_recover_image_jobs()" in backend
    assert 'status="retrying" if attempt < max_attempts - 1 else "failed"' in backend
    assert 'if attempt < max_attempts - 1: continue' in backend
    assert "job_id = str(uuid4())" in backend
    assert '"request_name":request_name' in backend
    assert "_save_image_jobs(jobs)\n                ACTIVE_IMAGE_JOBS.add(job_id)" in backend
    assert "def _persisted_image_process" in backend
    assert "IMAGE_TASK_SUPERVISOR" in backend
    assert 'if job.get("status") == "failed"' in backend
    assert "def _shutdown_image_jobs" in backend
    assert "HEAVY_TASK_LOCK = threading.RLock()" in backend


def test_live_image_job_keeps_asset_timer_running() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert 'profiles.some(item => item.status === "generating") ? "generating"' in source
    assert 'if (/道具资产验收失败/.test(message))' in source
    assert '道具图未通过：${failed.join("、")}，请继续生成' in source


def test_uploaded_asset_views_drive_multireference_storyboards() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    frontend = FRONTEND.read_text(encoding="utf-8")

    assert "def _generate_multireference_shot" in backend
    assert 'item.get("usage") != "audit_only"' in backend
    assert 'usage=face_primary as the sole face, makeup, hairline, close-up expression and lip-shape identity source' in backend
    assert 'usage=angle_continuity only to preserve side/back body silhouette' in backend
    assert 'usage=clothing_body only for body build' in backend
    assert '"identity_face_audit"' in backend
    assert 'identity_missing_or_duplicated' in backend
    assert 'visible_face_asymmetry' in backend
    assert "def _apply_storyboard_face_lock" in backend
    assert '"identity_lock":"single_front_face_primary"' in backend
    assert 'stage="storyboard_face_lock"' in backend
    assert 'hands_anatomically_valid' in backend
    assert 'body_anatomically_valid' in backend
    assert 'faces_anatomically_valid' in backend
    assert "def _audit_shot_consistency" in backend
    assert 'parsed.path in {"/api/shots/generate", "/api/shots/repair"} and references' in backend
    assert 'angle:"0°正面全身", usage:"clothing_body"' in frontend
    assert 'asset.label === "0°正面半身" ? "face_primary" : "angle_continuity"' in frontend
    assert 'single-face-v2-anatomy-gate' in frontend
    assert '旧版分镜未经过人脸与人体结构专项验收' in frontend
    assert "assetUploadComplete" in frontend
    assert "missingAssetsForShotImages" in frontend


def test_asset_baselines_use_style_specific_local_models() -> None:
    backend = BACKEND.read_text(encoding="utf-8")

    assert "def _generate_flux1_schnell_baseline" in backend
    assert '"class_type":"UnetLoaderGGUF"' in backend
    assert '"unet_name":"flux1-schnell-Q8_0.gguf"' in backend
    assert 'asset_phase == "baseline"' in backend
    assert '"base_model":"flux1-schnell-Q8_0.gguf"' in backend
    assert '"steps":4' in backend
    assert 'image["validation_evidence"] = validation_evidence' in backend
    assert 'image["validation_passed"] = True' in backend
    assert "for validation_attempt in range(5):" not in backend
    assert "def _schnell_test_loras(body: dict)" in backend
    assert 'if str(body.get("asset_phase", "")) == "variant":\n        return []' in backend
    assert 'if kind == "prop":\n        return []' in backend
    assert '"国风浅涂":"风格_国风仙韵_FLUX1_仅测试.safetensors"' in backend
    assert '"国风厚涂":"风格_油画仙韵_FLUX1_仅测试.safetensors"' not in backend
    assert "def _klein9b_houtu_loras(body: dict)" in backend
    assert 'if parsed.path == "/api/characters/generate" and asset_phase == "baseline"' in backend
    assert 'image.baseline.klein9b' in backend
    assert '"--lora-paths"' in backend
    assert 'project_style = str(project.get("style", "")' in backend
    assert "if not style_paths:\n        return []" in backend
    assert '"style":"项目提示词锁定"' in backend
    assert 'schnell_baseline = parsed.path == "/api/characters/generate" and asset_phase == "baseline"' in backend
    assert 'selected_lora = None if schnell_baseline or references else _automatic_lora' in backend
    assert 'if "LoRA 索引未登记" in str(error)' in backend
    assert "def _generate_ipadapter_image" in backend
    route_start = backend.index('if parsed.path in {"/api/characters/generate", "/api/shots/generate", "/api/shots/repair", "/api/assistant/images/generate"}')
    route_end = backend.index('if parsed.path == "/api/videos/generate"', route_start)
    route = backend[route_start:route_end]
    fixed_branch = route[route.index('"image.variant.qwen"'):route.index('if asset_phase != "variant" or not target_pose:')]
    assert '"image.variant.ipadapter"' in fixed_branch
    assert 'target_pose=target_pose' in fixed_branch
    assert 'clothing_reference_url' in fixed_branch
    assert 'job_id=job_id' in fixed_branch
    assert '"num_predict":640' in backend
    assert '"deterministic_full_frame"' in backend
    assert '_generate_qwen_character_variant' in backend
    assert 'if asset_phase == "variant" and target_pose:' in route
    assert 'stage="ipadapter_openpose"' in backend
    assert 'required = ("exactly_one_person", "correct_orientation"' in backend
    assert 'required += ("full_head_visible", "feet_visible"' in backend
    assert '"ckpt_name":"RealVisXL_V5.0_fp16.safetensors"' in backend
    fixed_start = backend.index("def _generate_ipadapter_image")
    fixed_end = backend.index("def _extract_openpose", fixed_start)
    fixed_workflow = backend[fixed_start:fixed_end]
    assert '"class_type":"LoraLoader"' not in fixed_workflow
    assert '"style_lora":"none"' in fixed_workflow
    assert '"character_lora":"none"' in fixed_workflow
    assert '"kind":"style"' in backend
    assert '"kind":"character"' in backend
    assert "not os.path.samefile(path, style_path)" in backend
    assert 'gender in {"女", "女性", "female", "woman", "girl", "f"}' in backend
    assert 'verdict.get("plain_gray_background") is True' not in backend
    assert 'def _validate_prop_asset' in backend
    assert '"exactly_one_isolated_prop"' in backend
    assert '"no_scene_or_environment"' in backend
    assert 'STRICT STUDIO PRODUCT PHOTOGRAPH' in backend
    assert 'one pale cyan carved jade pendant' in backend
    assert 'image["validation_passed"] = prop_valid' in backend
    assert 'if prop_valid: break' in backend
    assert "def _normalize_character_baseline_crop" in backend
    assert 'scale=(1664.0*0.45)/face_h' in backend
    assert 'hair_top*scale-1664*0.05' in backend
    assert '(928.0*0.96)/hair_width' in backend
    assert 'verdict.get("required_928x1664") is True' in backend
    assert 'and verdict.get("front_facing") is True' in backend
    assert 'and verdict.get("direct_gaze") is True' in backend
    assert 'abs(pose[1]) <= 3.0 and abs(pose[2]) <= 3.0' in backend


def test_schnell_baseline_finishes_without_implicit_qwen_repair() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    schnell_start = backend.index("def _generate_flux1_schnell_baseline")
    repair_start = backend.index("def _repair_schnell_output_with_qwen")
    variant_start = backend.index("def _reference_path")
    schnell = backend[schnell_start:repair_start]
    repair = backend[repair_start:variant_start]

    assert 'shutil.copy2(generated, schnell_target)' in schnell
    assert '_free_comfy_memory()' in schnell
    assert '_repair_schnell_output_with_qwen(' not in schnell
    assert '"workflow_mode":"single_model_baseline"' in schnell
    assert 'os.replace(temporary_target, target)' in schnell
    assert '"class_type":"UnetLoaderGGUF"' in schnell
    assert 'qwen_image_edit_2511_fp8mixed.safetensors' not in schnell
    assert 'if not source.is_file()' in repair
    assert 'shutil.copy2(source, input_path)' in repair
    assert '"unet_name":"qwen_image_edit_2511_bf16.safetensors"' in repair
    assert 'qwen_image_edit_2511_fp8mixed.safetensors' not in repair
    assert 'flux1-schnell-Q8_0.gguf' not in repair
    assert '"workflow_mode":"sequential_independent"' in repair
    assert '"class_type":"LoadImageMask"' in repair
    assert '"class_type":"SetLatentNoiseMask"' in repair
    assert '"denoise":0.45' in repair
    assert 'repair_mode":"masked_local_inpaint"' in repair
    assert 'qwen_prompt_id' in repair


def test_fixed_angles_use_qwen_2511_official_multiple_angles_workflow() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    frontend = FRONTEND.read_text(encoding="utf-8")

    assert 'stage="ipadapter_openpose"' in backend
    assert '"ckpt_name":"RealVisXL_V5.0_fp16.safetensors"' in backend
    fixed_start = backend.index("def _generate_ipadapter_image")
    fixed_end = backend.index("def _extract_openpose", fixed_start)
    fixed_workflow = backend[fixed_start:fixed_end]
    assert '"class_type":"LoraLoader"' not in fixed_workflow
    assert '"class_type":"IPAdapterUnifiedLoaderFaceID"' in fixed_workflow
    assert '"preset":"FACEID PLUS V2"' in fixed_workflow
    assert '"class_type":"IPAdapterFaceID"' in fixed_workflow
    assert '"attn_mask":["24",0]' in fixed_workflow
    assert '"clip":["1",1]' in fixed_workflow
    assert '"steps":24' in fixed_workflow
    assert '"steps":12' in fixed_workflow
    assert '"denoise":profile["refine_denoise"]' in fixed_workflow
    assert '"refine_denoise":0.18' in fixed_workflow
    assert '"class_type":"VAEEncode"' in fixed_workflow
    assert '"control_net_name":"openpose-sdxl-1.0.safetensors"' in backend
    assert '"ipadapter_file":"ip-adapter-plus_sdxl_vit-h.safetensors"' in backend
    assert '"weight":profile["clothing_weight"],"weight_type":profile["clothing_weight_type"]' in backend
    assert '"end_at":profile["clothing_end"]' in backend
    assert '"model":["18",0]' in backend
    assert 'abs(pose[1]) <= 7.0' in backend
    assert '88.0 <= face_angle <= 92.0' in backend
    assert 'torso_rotation <= 3.0' in backend
    assert '"side_angle_tier"' in backend
    assert 'openpose_{target_pose}_7_5.png' in fixed_workflow
    assert 'side_depth_source_7_5.png' in fixed_workflow
    assert '"class_type":"DepthAnythingV2Preprocessor"' in fixed_workflow
    assert '"control_net_name":"xinsir-controlnet-depth-sdxl-1.0.safetensors"' in fixed_workflow
    assert '"workflow_mode":"two_stage_pose_then_identity_clothing"' in fixed_workflow
    assert "def _prepare_ipadapter_reference_crops" in backend
    assert "def _face_embedding_similarity" in backend
    assert "def _pose_proportion_metrics" in backend
    assert 'face_similarity >= 0.35' in backend
    assert 'clothing_similarity >= 0.82' in backend
    assert 'dimensions == (928, 1664)' in backend
    assert '"top_margin_about_5_percent"' in backend
    assert '"bottom_margin_about_5_percent"' in backend
    assert '"face_height_40_to_50_percent"' in backend
    assert '"head_to_body_ratio_7_to_7_8"' in backend
    assert 'deterministic_orientation' in backend
    assert '"exact_clothing_consistent"' in backend
    assert '"body_shape_consistent"' in backend
    assert 'for path in [reference, candidate]' in backend
    assert 'for path in [strict_clothing_reference, candidate]' in backend
    assert '_validate_character_variant(image.get("url", ""), image, "left_45_full")' in backend
    assert '"gender_and_age_match"' in backend
    assert '"face_hair_match"' in backend
    assert '"clothing_match"' in backend
    assert 'asset_phase == "repair"' in backend
    assert 'stage="qwen_repairing"' in backend
    route_start = backend.index('if parsed.path in {"/api/characters/generate", "/api/shots/generate", "/api/shots/repair", "/api/assistant/images/generate"}')
    route_end = backend.index('if parsed.path == "/api/videos/generate"', route_start)
    fixed_route = backend[route_start:route_end]
    assert '"image.variant.qwen"' in fixed_route
    assert '_invoke_production_capability(' in fixed_route
    qwen_start = backend.index('def _generate_qwen_character_variant')
    qwen_end = backend.index('def _latest_completed_asset_image_url', qwen_start)
    qwen_angle = backend[qwen_start:qwen_end]
    assert '"unet_name":"qwen_image_edit_2511_bf16.safetensors"' in qwen_angle
    assert '"lora_name":"qwen-image-edit-2511-multiple-angles-lora.safetensors","strength_model":1.0' in qwen_angle
    assert '"lora_name":"Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors","strength_model":1.0' in qwen_angle
    assert '"steps":4,"cfg":1.0' in qwen_angle
    assert '"image1":["3",0],"image2":["6",0]' in qwen_angle
    assert '"reference_latents_method":"index_timestep_zero"' in qwen_angle
    assert 'stage="qwen_variant"' in qwen_angle
    assert '_cancel_comfy_prompt(prompt_id)' in qwen_angle
    assert 'image = _generate_visual_persona_front_full(' not in fixed_route
    assert 'image = _generate_pshuman_view(' not in fixed_route
    assert '"control":1.05, "depth_control":0.55' in backend
    assert '"ip_weight":0.12' in backend
    assert 'assetError.value = `${item.name}：${userFacingGenerationError(item.error)}`' in frontend
    assert 'const firstFailedVariant = variants.find(variant => variant.status === "failed")' in frontend
    assert 'if (item.error) assetError.value = `${item.name}：${item.error}`' in frontend
    assert '"workflow_mode":"qwen_2511_multiple_angles"' in backend
    prop_scene_variant = backend[backend.index('if references and asset_phase == "variant" and asset_kind in {"scene", "prop"}'):]
    prop_scene_variant = prop_scene_variant[:prop_scene_variant.index("else:", 200)]
    assert '_repair_schnell_output_with_qwen(' not in prop_scene_variant
    assert '"image.generate"' in prop_scene_variant
    assert 'const identityReferenceUrl = item.image_url;' in frontend
    assert 'clothing_reference_url:clothingReferenceUrl' in frontend
    assert 'asset_phase:"repair"' in frontend
    unified_asset_card = (ROOT / "plugins/builtin/short_drama/frontend/components/business/UnifiedAssetCard.vue").read_text(encoding="utf-8")
    assert ':show-repair="Boolean(slide.imageUrl)"' in unified_asset_card
    assert "def _latest_completed_asset_image_url" in backend
    assert 'body["references"] = references' in backend
    assert 'body["clothing_reference_url"] = recovered_url' in backend


def test_in_world_text_is_blank_during_diffusion_and_rendered_deterministically() -> None:
    backend = BACKEND.read_text(encoding="utf-8")

    assert "def _required_image_text" in backend
    assert "def _blank_requested_text" in backend
    assert "def _apply_required_text_overlay" in backend
    assert "当前生图阶段禁止生成任何汉字、字母、数字、符号、书法、标志或水印" in backend
    assert 'required_text = _required_image_text(body, base_image_prompt)' in backend
    assert 'base_image_prompt = _blank_requested_text(base_image_prompt, required_text)' in backend
    assert '_apply_required_text_overlay(_local_media_path(image.get("url")), required_text, body)' in backend
    assert '"text_audit":"exact_source_render"' in backend
    assert 'hashlib.sha256(text.encode()).hexdigest()' in backend
    assert '/System/Library/Fonts/Supplemental/Songti.ttc' in backend
    assert "def _validate_scene_asset" in backend
    assert "no_text_letters_numbers_or_signage" in backend
    assert 'for validation_attempt in range(3)' in backend
