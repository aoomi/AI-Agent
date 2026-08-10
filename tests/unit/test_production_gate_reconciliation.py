from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")


def test_bulk_scope_sync_heals_stale_langgraph_from_confirmed_ledger():
    assert "def _reconcile_completed_production_stages" in BACKEND
    assert 'record.get("lifecycle") == "completed"' in BACKEND
    assert 'isinstance(record.get("confirmation"), dict)' in BACKEND
    assert 'reconciled_from="production_ledger"' in BACKEND
    bulk = BACKEND[BACKEND.index('if parsed.path == "/api/production/scopes/bulk"'):]
    assert "_reconcile_completed_production_stages(identity, PRODUCTION_LEDGER.list(identity))" in bulk


def test_reconciliation_stops_at_first_missing_or_unconfirmed_stage():
    helper = BACKEND[BACKEND.index("def _reconcile_completed_production_stages"):BACKEND.index("def _begin_production_request")]
    assert "if not stage_records:" in helper and "break" in helper
    assert "if not complete:" in helper


def test_stage_gate_uses_batch_or_episode_not_script_line_details():
    helper = BACKEND[BACKEND.index("def _stage_gate_records"):BACKEND.index("def _reconcile_completed_production_stages")]
    assert 'stage in {"script", "storyboard"}' in helper
    assert 'preferred = ("story_arc_batch", "episode_batch", "episode")' in helper
    assert 'scope_type") == scope_type' in helper
    assert '"line"' not in helper


def test_storyboard_uses_compact_directing_plan_then_deterministic_compiler():
    assert '"num_predict":num_predict' in BACKEND
    assert "num_ctx=4096, num_predict=512, timeout_seconds=240" in BACKEND
    assert "def _compile_storyboard_from_script" in BACKEND
    assert "_validate_storyboard(shots" in BACKEND
    assert "if missing_dialogue:" in BACKEND
    assert "len(missing_dialogue) >" not in BACKEND


def test_running_stage_rejects_duplicate_external_request_but_allows_internal_child_call():
    orchestrator = (ROOT / "plugins/builtin/short_drama/workflows/production_orchestrator.py").read_text(encoding="utf-8")
    assert 'state.get("stages", {}).get(canonical) == "running"' in orchestrator
    assert 'production stage is already running' in orchestrator
    assert 'production_stage and self.headers.get("X-Production-Dispatched") != "1"' in BACKEND
    assert "def _claim_production_stage_request" in BACKEND
    run_stage = BACKEND[BACKEND.index('if parsed.path == "/api/production/run-stage"'):]
    assert "with _claim_production_stage_request(body, stage) as cancel_event:" in run_stage


def test_restart_fails_unrecoverable_synchronous_running_stage():
    assert "def _recover_production_workflows" in BACKEND
    helper = BACKEND[BACKEND.index("def _recover_production_workflows"):BACKEND.index("def _begin_production_request")]
    assert 'state.get("stages", {}).get(current_stage) == "running"' in helper
    assert 'brain.report(identity, current_stage, "failed"' in helper
    assert '"image":"shot_images"' in helper
    assert '"video":"shot_videos"' in helper
    assert '_write_project_stage(identity["project_id"]' in helper
    main = BACKEND[BACKEND.index("def main() -> None:"):]
    assert "_recover_production_workflows()" in main


def test_assets_are_a_server_owned_langgraph_stage_not_a_frontend_legacy_call():
    assert 'if stage == "assets":' in BACKEND
    assert '_local_api("/api/characters/extract"' in BACKEND
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    extract = frontend[frontend.index("function extractProductionAssets"):frontend.index("async function generateAssetBaseline")]
    assert 'stage:"assets"' in extract
    assert "productionLedgerService.runStage" in extract
    assert extract.count("assetService.extractCharacters") == 1
    assert 'extraction_phase:"storyboard_preview"' in extract
    confirm = frontend[frontend.index("async function confirmStoryboards"):frontend.index("async function stopStoryboards")]
    assert "async function confirmStoryboards():Promise<boolean>" in confirm
    assert "return false" in confirm and "return true" in confirm
    assert "await syncProductionLedger(project)" in confirm
    enter = frontend[frontend.index("function enterAssetGeneration"):frontend.index("async function stopAllAssetGeneration")]
    assert "let assetEntryPromise:Promise<void> | undefined" in frontend
    assert "if (assetEntryPromise) return assetEntryPromise" in enter
    assert "const singleFlight = transaction.finally" in enter
    assert 'storyboardStatus.value !== "confirmed"' in enter
    assert "const confirmed = await confirmStoryboards()" in enter
    assert 'if (!confirmed || String(storyboardStatus.value) !== "confirmed") return' in enter


def test_normal_composition_is_one_server_owned_batch():
    assert 'if stage == "composition":' in BACKEND
    assert '_local_api("/api/videos/merge"' in BACKEND
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    merge = frontend[frontend.index("async function mergeEpisodes"):frontend.index("async function generateFinalVideo")]
    assert 'stage:"composition"' in merge
    assert "productionLedgerService.runStage" in merge
    assert "for (let episode" not in merge
    assert "await syncProductionLedger(project)" in merge
    assert "const session = projectSession" in merge
    assert "isCurrentProjectSession(project.id, session)" in merge
    assert "controller.signal.aborted" in merge


def test_composition_validates_unique_episodes_before_merging():
    composition = BACKEND.split('if stage == "composition":', 1)[1].split('raise ValueError("unsupported server narrative stage")', 1)[0]
    assert 'len(set(episodes)) != len(episodes)' in composition
    assert 'composition episode commands must be unique' in composition
    assert composition.index('len(set(episodes)) != len(episodes)') < composition.index('_local_api("/api/videos/merge"')


def test_asset_extraction_is_single_flight_and_streams_framework_during_storyboard_generation():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    load = frontend[frontend.index("async function loadProjectFlowState"):frontend.index("async function loadOutlineState")]
    assert 'storyboardStatus.value === "confirmed"' in load
    assert 'await seedAssetCardsFromStoryboard(project, storyboardShots.value, session)' in load
    assert 'extractProductionAssets(' not in load
    assert "const assetExtractionPromises = new Map<string, Promise<void>>()" in frontend
    assert "const key = `${project.id}:${session}`" in frontend
    assert "if (active) return active" in frontend
    assert "const transaction = runProductionAssetExtraction(source, project, session)" in frontend
    assert "assetExtractionPromises.get(key) === singleFlight" in frontend
    extraction = frontend[frontend.index("async function runProductionAssetExtraction"):frontend.index("async function generateAssetBaseline")]
    assert extraction.count("isCurrentProjectSession(project.id, session)") >= 6
    assert "controller.signal.aborted" in extraction
    assert "persistAssetState(project, session)" in extraction
    assert '@primary="generateAllAssetImages"' in frontend
    assert "storyboardHasCompleteEpisode ? '生成图片'" in frontend
    assert 'label:"0°正面全身"' in frontend
    assert 'label:"90°侧面全身"' in frontend
    assert 'label:"180°背面全身"' in frontend
    assert 'label:"0°正面半身"' in frontend
    assert 'label:"左45°全身"' in frontend
    assert 'label:"右45°全身"' in frontend
    assert 'angle.label === "0°正面全身" ? "front_full"' in frontend
    assert 'angle.label === "右45°全身" ? "right_45_full"' in frontend
    upload_gate = frontend[frontend.index("function assetUploadComplete"):frontend.index("const readyAssetEpisode")]
    assert 'hasCompleteAssetVariants("character", item)' in upload_gate
    assert '["90°侧面全身", "180°背面全身"]' not in upload_gate
    shot_reference_paths = frontend[frontend.index("async function generateOneShotImage"):frontend.index("async function generateShotImages")]
    assert shot_reference_paths.count('usage:"clothing_body"') == 2
    assert shot_reference_paths.count('usage:asset.label === "0°正面半身" ? "face_primary" : "angle_continuity"') == 1
    assert shot_reference_paths.count('usage:detail.label === "0°正面半身" ? "face_primary" : "angle_continuity"') == 1
    assert 'usage:"audit_only"' not in shot_reference_paths
    character_angles = frontend.split("character:[", 1)[1].split("scene:[", 1)[0]
    assert "45°全身基准照" not in character_angles
    slides = frontend[frontend.index('if (kind === "character")'):frontend.index('const angleDefinitions = fixedAssetAngles[kind]')]
    assert 'key:"baseline:left45", label:"左45°全身"' in slides
    assert 'variantSlide("0°正面全身", front)' in slides
    assert 'variantSlide("右45°全身", right45)' in slides
    assert slides.count('variantSlide(') == 5
    assert slides.index('variantSlide("0°正面半身", half)') < slides.index('variantSlide("0°正面全身", front)') < slides.index('key:"baseline:left45", label:"左45°全身"') < slides.index('variantSlide("右45°全身", right45)') < slides.index('variantSlide("90°侧面全身", side)') < slides.index('variantSlide("180°背面全身", back)')
    assert 'variantSlide("正面全身"' not in slides
    resume = frontend[frontend.index("function applyInterruptedStageRecovery"):frontend.index("type OutlineStageData")]
    assert "generateAllAssetImages()" not in resume
    assert "window.setTimeout(() => void generateShotVideos(), 50)" not in frontend
    recovery = frontend[frontend.index("async function recoverCompletedAssetImages"):frontend.index("const assetResultRecoveryTimer")]
    assert "void generateAllAssetImages()" not in recovery


def test_asset_stage_conflict_waits_for_existing_extraction_instead_of_failing():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    extraction = frontend[frontend.index("async function runProductionAssetExtraction"):frontend.index("async function generateAssetBaseline")]
    assert 'error.message.includes("production stage is already running: assets")' in extraction
    assert 'projectService.readStage<AssetStageData>' in extraction
    assert 'if (data.status === "generating") continue' in extraction
    assert '["waiting_confirmation", "confirmed", "completed"].includes(data.status)' in extraction
    assert 'data.error || "资产提取任务未完成，请重新生成"' in extraction
    assert 'characterProfiles.value = mergeAssetProfiles' in extraction
    assert 'assetStatus.value = "failed"' in extraction
    assert '资产提取任务仍在运行，请稍后继续生成图片' in extraction
    assert 'if (assetStatus.value === "failed") return' in frontend
    confirm = frontend[frontend.index("async function confirmAsset(item"):frontend.index("async function confirmAssetVariant")]
    assert "await productionLedgerService.confirmAsset" in confirm
    assert confirm.index("await productionLedgerService.confirmAsset") < confirm.index("await generateAssetVariantsFromConfirmedBaseline")
    assert 'item.status = "waiting_confirmation"' in confirm
    load_assets = frontend[frontend.index("async function loadAssetState"):frontend.index("async function persistAssetState")]
    assert 'variant.status = "waiting_confirmation"' in load_assets
    assert 'variant.status = group.kind' not in load_assets
    assert 'variant.status = "pending"' in confirm
    variants = frontend[frontend.index("async function generateAssetVariantsFromConfirmedBaseline"):frontend.index("async function regenerateAssetPhotoSlide")]
    assert "const session = projectSession" in variants
    assert "assetVariantControllers" in variants
    assert "controller.signal" in variants
    assert variants.count("stillCurrent()") >= 7
    assert "persistAssetState(project, session)" in variants


def test_storyboard_persists_each_completed_episode_and_frontend_creates_asset_cards_immediately():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    storyboard_backend = BACKEND.split('if stage == "storyboard":', 1)[1].split('if stage == "assets":', 1)[0]
    assert "_write_storyboard_stream_progress" in storyboard_backend
    assert "cancel_event.is_set()" in storyboard_backend
    generator = frontend[frontend.index("async function generateStoryboards"):frontend.index("async function runStoryboardPrimaryAction")]
    assert "projectService.watchStage<StoryboardStageData>" in generator
    assert "after_revision:observedRevision" in generator
    assert "timeout_seconds:20" in generator
    assert "window.setTimeout(resolve, 500)" not in generator
    assert 'partial.stage.data.status !== "generating"' in generator
    assert generator.count("isCurrentProjectSession(project.id, session)") >= 4
    assert "seedAssetCardsFromStoryboard(project, incoming, session, controller.signal)" in generator
    assert generator.index("polling = false;") < generator.index("storyboardShots.value = response.result.shots")
    assert "await seedAssetCardsFromStoryboard(project, incoming, session, controller.signal)" in generator
    assert "for (const episode of [...completeStoryboardEpisodes.value].sort" in generator
    assert "queueStoryboardAssetExtraction(project, session, episode)" in generator
    seed = frontend[frontend.index("async function seedAssetCardsFromStoryboard"):frontend.index("function reconcileOutlineCharacters")]
    assert "characterProfiles.value = mergeAssetProfiles" in seed
    assert "sceneProfiles.value = mergeAssetProfiles" in seed
    assert "await persistAssetState" in seed
    prepare = frontend[frontend.index("async function prepareAssetProfilesFromStoryboard"):frontend.index("let assetResultRecoveryRunning")]
    assert "await storyboardAssetExtractionQueue" in prepare
    assert 'runProductionAssetExtraction("manual", project, session, episodes, true)' in prepare
    assert "characterProfiles.value = []" not in prepare
    assert "sceneProfiles.value = []" not in prepare
    assert "propProfiles.value = []" not in prepare
    queue = frontend[frontend.index("function queueStoryboardAssetExtraction"):frontend.index("function reconcileOutlineCharacters")]
    assert 'runProductionAssetExtraction("manual", project, session, [episode], false)' in queue
    extraction = frontend[frontend.index("async function runProductionAssetExtraction"):frontend.index("async function generateAssetBaseline")]
    assert 'extraction_phase:"storyboard_preview"' in extraction
    assert 'commitStage ? "waiting_confirmation" : "pending"' in extraction
    load_assets = frontend[frontend.index("async function loadAssetState"):frontend.index("async function persistAssetState")]
    stale = load_assets[load_assets.index("if (censusStale)"):]
    assert "await seedAssetCardsFromStoryboard" in stale
    assert "extractProductionAssets(" not in stale


def test_stage_progress_uses_revision_watch_with_backpressure_instead_of_fixed_polling():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    service = (ROOT / "plugins/builtin/short_drama/frontend/services/project.service.ts").read_text(encoding="utf-8")
    assert 'parsed.path == "/api/projects/stage/watch"' in BACKEND
    assert "PROJECT_STAGE_CONDITION.notify_all()" in BACKEND
    assert "PROJECT_STAGE_WATCH_SLOTS.acquire(blocking=False)" in BACKEND
    assert '"error":"stage_watch_backpressure"' in BACKEND
    assert "revision > after_revision" in BACKEND
    assert "PROJECT_STAGE_CONDITION.wait(remaining)" in BACKEND
    assert "PROJECT_STAGE_WATCH_SLOTS.release()" in BACKEND
    assert "def _reap_cancelled_stage_watches" in BACKEND
    assert "def _monitor_project_stage_watches" in BACKEND
    assert "def _project_stage_watch_key" in BACKEND
    assert "SERVICE_SHUTTING_DOWN.is_set()" in BACKEND
    main_finally = BACKEND[BACKEND.index("    finally:", BACKEND.index("def main() -> None:")):]
    assert "PROJECT_STAGE_CONDITION.notify_all()" in main_finally
    assert 'name="project-stage-watch-reaper"' in BACKEND
    assert "watchStage<T>" in service and "/api/projects/stage/watch" in service
    generator = frontend[frontend.index("async function generateStoryboards"):frontend.index("async function runStoryboardPrimaryAction")]
    assert "projectService.watchStage<StoryboardStageData>" in generator
    assert "const watchController = new AbortController()" in generator
    assert "watchController.signal" in generator
    assert 'projectService.cancelStageWatch({ ...projectIdentity, id:project.id, stage:"storyboard", request_id:requestId })' in generator
    assert generator.index("await cancelActiveWatch();") < generator.index("await progressPoll.catch")
    assert "window.setTimeout(resolve, 500)" not in generator


def test_storyboard_stop_requires_complete_exact_project_identity():
    cancel = BACKEND[BACKEND.index("def _cancel_production_stage"):BACKEND.index("def _sync_durable_tasks")]
    assert "if not tenant_id or not user_id or not project_id:" in cancel
    assert 'target_key = f"{tenant_id}:{user_id}:{project_id}:{stage}"' in cancel
    assert "if key != target_key: continue" in cancel
    stop_route = BACKEND[BACKEND.index('if parsed.path == "/api/generation/stop" and body.get("kind") == "storyboard"'):]
    assert "HTTPStatus.BAD_REQUEST" in stop_route
    assert '"error":"invalid_production_scope"' in stop_route
