from pathlib import Path
import json
import os
import shutil
import subprocess

import pytest


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
    assert 'production_stage and not _is_asset_subtask_request(parsed.path, body) and self.headers.get("X-Production-Dispatched") != "1"' in BACKEND
    assert "def _claim_production_stage_request" in BACKEND
    run_stage = BACKEND[BACKEND.index('if parsed.path == "/api/production/run-stage"'):]
    assert "with _claim_production_stage_request(body, stage) as cancel_event:" in run_stage


def test_restart_fails_unrecoverable_synchronous_running_stage():
    assert "def _recover_production_workflows" in BACKEND
    helper = BACKEND[BACKEND.index("def _recover_production_workflows"):BACKEND.index("def _begin_production_request")]
    assert 'state.get("stages", {}).get(current_stage) == "running"' in helper
    assert 'brain.report(identity, current_stage, "failed"' in helper
    assert "PROJECT_STAGE_STORAGE[current_stage]" in helper
    registrations = json.loads((ROOT / "plugins/builtin/short_drama/workflows/stage.registrations.json").read_text(encoding="utf-8"))
    storage = {row["stage"]:row["project_storage"] for row in registrations["stages"]}
    assert storage["image"] == "shot_images"
    assert storage["video"] == "shot_videos"
    assert '_write_project_stage(identity["project_id"]' in helper
    main = BACKEND[BACKEND.index("def main() -> None:"):]
    assert "_recover_production_workflows()" in main


def test_assets_are_a_server_owned_langgraph_stage_not_a_frontend_legacy_call():
    assert 'if stage == "assets":' in BACKEND
    assert '_production_stage_local_api(body, stage, "/api/characters/extract"' in BACKEND
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
    assert "if (assetEntryPromise && assetEntryPromiseKey === entryKey) return assetEntryPromise" in enter
    assert "const singleFlight = transaction.finally" in enter
    assert 'storyboardStatus.value !== "confirmed"' in enter
    assert "const confirmed = await confirmStoryboards()" in enter
    assert 'if (!confirmed || String(storyboardStatus.value) !== "confirmed") return' in enter
    extract_endpoint = BACKEND[BACKEND.index('if parsed.path == "/api/characters/extract"'):BACKEND.index('if parsed.path == "/api/assets/3d/generate"')]
    assert "except (json.JSONDecodeError, ValueError) as first_error" in extract_endpoint
    assert extract_endpoint.count("result = _ollama_json(") == 2
    assert "只重试一次" in extract_endpoint
    assert 'authoritativeAssets = await projectService.readStage<AssetStageData>' in enter
    assert 'authoritativeWorkflow = await productionLedgerService.workflow(productionTaskContext(project))' in enter
    assert '["pending_confirmation", "completed"].includes(String(authoritativeWorkflow?.workflow.stages.assets || ""))' in enter
    assert "if (!allAssetProfiles.value.length || !assetAuthorityReady())" in enter
    assert "await prepareAssetProfilesFromStoryboard(project)" in enter
    assert "if (!assetAuthorityReady())" in enter
    assert 'assetError.value ||= "资产权威阶段尚未完成，请先重试资产提取"' in enter
    assert enter.index("if (!assetAuthorityReady())") < enter.index('enqueueAssetOperation(`${project.id}:generate-all`')


def test_normal_composition_is_one_server_owned_batch():
    assert 'if stage == "composition":' in BACKEND
    assert '_production_stage_local_api(body, stage, "/api/videos/merge"' in BACKEND
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
    assert composition.index('len(set(episodes)) != len(episodes)') < composition.index('_production_stage_local_api(body, stage, "/api/videos/merge"')


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
    assert '@primary="queueGenerateAllAssetImages"' in frontend
    assert "storyboardHasCompleteEpisode ? '生成图片'" in frontend
    assert 'label:"0°正面全身"' in frontend
    assert 'label:"90°侧面全身"' in frontend
    assert 'label:"180°背面全身"' in frontend
    assert 'label:"0°正面半身"' in frontend
    assert 'label:"左45°全身"' in frontend
    assert 'label:"右45°全身"' in frontend
    assert 'angle.label === "左45°全身" ? "left_45_full"' in frontend
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
    assert 'key:"baseline:front", label:"0°正面全身"' in slides
    assert 'variantSlide("左45°全身", left45)' in slides
    assert 'variantSlide("右45°全身", right45)' in slides
    assert slides.count('variantSlide(') == 5
    assert slides.index('variantSlide("0°正面半身", half)') < slides.index('key:"baseline:front", label:"0°正面全身"') < slides.index('variantSlide("左45°全身", left45)') < slides.index('variantSlide("右45°全身", right45)') < slides.index('variantSlide("90°侧面全身", side)') < slides.index('variantSlide("180°背面全身", back)')
    assert 'variantSlide("正面全身"' not in slides
    resume = frontend[frontend.index("function applyInterruptedStageRecovery"):frontend.index("type OutlineStageData")]
    assert "generateAllAssetImages()" not in resume
    assert "window.setTimeout(() => void generateShotVideos(), 50)" not in frontend
    recovery = frontend[frontend.index("async function recoverCompletedAssetImages"):frontend.index("const assetResultRecoveryTimer")]
    assert "void generateAllAssetImages()" not in recovery
    assert 'variant.status !== "generating"' in recovery
    assert 'const variantJobName = `${project.id}_${item.generation_nonce || "legacy"}_${group.kind}_${item.name}_angle_${variantIndex + 2}`' in recovery
    assert 'variant.status = "failed"' in recovery
    assert 'variant.error = userFacingGenerationError(completed.data.error)' in recovery
    failed_result = recovery[recovery.index('completed.data.status === "failed"'):]
    failed_result = failed_result[:failed_result.index("recovered = true")]
    assert 'item.status = "failed"' in failed_result
    assert 'item.status = "pending"' not in failed_result
    timer = frontend[frontend.index("const assetResultRecoveryTimer"):frontend.index("onBeforeUnmount(() => window.clearInterval(assetResultRecoveryTimer))")]
    assert 'item.status === "generating"' in timer
    assert 'variant.status === "generating"' in timer
    assert 'some(item => !item.image_url)' not in timer
    asset_card = (ROOT / "plugins/builtin/short_drama/frontend/components/business/UnifiedAssetCard.vue").read_text(encoding="utf-8")
    assert '<p v-if="item.error" class="outline-error asset-card-error">{{userError}}</p>' in asset_card
    assert "slide.status==='failed'?'生成失败':'等待生图'" in asset_card


def test_project_creation_resets_all_stage_projections_before_loading_new_project():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    reset = frontend[frontend.index("function resetProjectFlowProjection"):frontend.index("async function loadProjectFlowState")]
    for loader in (
        "loadOutlineState", "loadScriptState", "loadStoryboardState", "loadAssetState", "loadShotImageState",
        "loadShotVideoState", "loadMergeState", "loadFinalAuditState", "loadUpscaleState", "loadExportState",
    ):
        assert f"void {loader}(null, session)" in reset
    load = frontend[frontend.index("async function loadProjectFlowState"):frontend.index("function applyInterruptedStageRecovery")]
    assert load.index("resetProjectFlowProjection(session)") < load.index("projectLoadIsolation.begin") < load.index("await loadSkillBindings")
    save = frontend[frontend.index("async function saveProject"):frontend.index("async function deleteProject")]
    assert save.index("appRuntime.projectStore.replace(projectRecords.value, result.project.id)") < save.index("await loadProjectFlowState()")
    assert save.index("await loadProjectFlowState()") < save.index("notify(`项目")


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


def test_resolved_asset_stage_conflict_is_not_preserved_as_card_failure():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    backend = BACKEND
    assert 'function clearResolvedAssetStageConflict' in frontend
    assert "authoritativeSuccess" in frontend
    assert "successfulAssetStageStatuses" in frontend
    assert 'itemError === "production stage is already running: assets"' in frontend
    assert 'isDeferredAssetConfirmationError(itemError)' in frontend
    assert 'item.status = item.image_url ? "waiting_confirmation" : "pending"' in frontend
    merge = frontend[frontend.index("function mergeAssetProfiles"):frontend.index("function normalizeAssetName")]
    assert "clearResolvedAssetStageConflict" in merge
    load = frontend[frontend.index("async function loadAssetState"):frontend.index("async function persistAssetState")]
    assert load.count("clearResolvedAssetStageConflict(item, authoritativeSuccess)") == 3
    assert "authoritative_asset_success and" in backend
    assert 'str(value.get("error") or "").strip() == "production stage is already running: assets"' in backend
    assert 'value["status"] = "waiting_confirmation" if value.get("image_url") else "pending"' in backend
    assert 'value["error"] = ""' in backend


def test_storyboard_persists_each_completed_episode_and_frontend_creates_asset_cards_immediately():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    storyboard_backend = BACKEND.split('if stage == "storyboard":', 1)[1].split('if stage == "assets":', 1)[0]
    assert "_write_storyboard_stream_progress" in storyboard_backend
    assert "_checkpoint_production_stage(body, stage)" in storyboard_backend
    generator = frontend[frontend.index("async function generateStoryboards"):frontend.index("async function runStoryboardPrimaryAction")]
    assert "projectService.watchStage<StoryboardStageData>" in generator
    assert "after_revision:observedRevision" in generator
    assert "timeout_seconds:20" in generator
    assert "window.setTimeout(resolve, 500)" not in generator
    assert 'partial.stage.data.status !== "generating"' in generator
    assert generator.count("isCurrentProjectSession(project.id, session)") >= 4
    assert "seedAssetCardsFromStoryboard(project, incoming, session, controller.signal)" in generator
    assert generator.index("polling = false;") < generator.index("storyboardShots.value = mergeStoryboardEpisodeResults")
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
    assert 'if (!isCurrentProjectSession(project.id, session) || assetStatus.value === "failed") return' in queue
    assert 'await enqueueAssetOperation(`${project.id}:generate-all`, "生成资产图片", () => generateAllAssetImages(project, session))' in queue
    assert queue.index('runProductionAssetExtraction("manual", project, session, [episode], false)') < queue.index("await enqueueAssetOperation")
    extraction = frontend[frontend.index("async function runProductionAssetExtraction"):frontend.index("async function generateAssetBaseline")]
    assert 'extraction_phase:"storyboard_preview"' in extraction
    assert 'commitStage ? "waiting_confirmation" : "pending"' in extraction
    load_assets = frontend[frontend.index("async function loadAssetState"):frontend.index("async function persistAssetState")]
    stale = load_assets[load_assets.index("if (censusStale)"):]
    assert "await seedAssetCardsFromStoryboard" in stale
    assert "extractProductionAssets(" not in stale


def test_generate_button_reconciles_exact_stale_assets_conflict_before_starting_images():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    generate = frontend[frontend.index("function generateAllAssetImages"):frontend.index("async function confirmAsset(item")]
    assert 'String(assetError.value || "").trim() === "production stage is already running: assets"' in generate
    assert 'projectService.readStage<AssetStageData>' in generate
    assert 'stage.status !== "generating"' in generate
    assert '!String(stage.error || "").trim()' in generate
    assert 'assetError.value = ""' in generate
    assert 'const isCurrentBatch = () => isCurrentProjectSession(project.id, session) && !controller.signal.aborted' in generate
    read_stage = generate.index('await projectService.readStage<AssetStageData>')
    response_guard = generate.index('if (!isCurrentBatch()) return', read_stage)
    assert read_stage < response_guard < generate.index('characterProfiles.value = mergeAssetProfiles')


def test_asset_baseline_endpoint_uses_image_job_lock_not_whole_assets_stage_gate():
    backend = BACKEND
    mapping = backend[backend.index("PRODUCTION_ENDPOINT_STAGES = {"):backend.index("PRODUCTION_ENDPOINT_RESOURCES = {")]
    assert '"/api/characters/generate":"assets"' not in mapping
    resources = backend[backend.index("PRODUCTION_ENDPOINT_RESOURCES = {"):backend.index("def _forward_production_request")]
    assert '"/api/characters/generate":"image"' in resources


def test_automatic_asset_generation_keeps_original_project_session_fences():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    baseline = frontend[frontend.index("async function generateAssetBaseline"):frontend.index("async function generateAsset3D")]
    batch = frontend[frontend.index("function generateAllAssetImages"):frontend.index("async function confirmAsset(item")]
    assert "project = activeProjectRecord.value, session = projectSession" in baseline
    assert baseline.count("isCurrentProjectSession(project.id, session)") >= 4
    assert "persistAssetState(project, session)" in baseline
    assert "signal?:AbortSignal" in baseline
    assert "assetService.purgeGenerated" not in baseline
    assert "const previousImageUrl = item.image_url" in baseline
    assert 'item.status = previousImageUrl ? "waiting_confirmation" : "failed"' in baseline
    assert "}, signal);" in baseline
    assert "project = activeProjectRecord.value, session = projectSession" in batch
    assert batch.count("isCurrentProjectSession(project.id, session)") >= 3
    assert "generateAssetBaseline(target.kind, target.item, project, session, controller.signal)" in batch
    assert "persistAssetState(project, session)" in batch
    assert "assetBatchFlight && assetBatchFlightKey === flightKey" in batch
    assert "return assetBatchFlight" in batch
    assert "async function generateAllAssetImages" not in batch
    assert "function generateAllAssetImages" in batch
    assert "assetBatchFlight === singleFlight" in batch
    assert "activeAssetBatchToken === batchToken" in batch
    stop = frontend[frontend.index("async function stopAllAssetGeneration"):frontend.index("async function stopOutline")]
    assert "reclaimAssetBatchProjection(assetBatchFlight, assetBatchController.value, activeAssetBatchToken)" in stop
    assert "const stopEpoch = ++assetBatchEpoch" in stop
    assert "assetBatchEpoch !== stopEpoch" in stop
    assert "persistAssetState(project, session)" in stop
    reclaim = frontend[frontend.index("function reclaimAssetBatchProjection"):frontend.index("const assetSourceEpisodes")]
    assert "controller?.abort()" in reclaim
    assert "assetBatchFlight !== flight || assetBatchController.value !== controller || activeAssetBatchToken !== token" in reclaim
    assert 'assetBatchGenerating.value = false' in reclaim
    assert 'item.status === "generating"' in reclaim
    assert "if (assetBatchFlight && assetBatchFlightKey !== flightKey) reclaimAssetBatchProjection" in batch


def test_asset_batch_public_entry_returns_the_same_live_promise_dynamically():
    node = shutil.which("node")
    if not node:
        pytest.skip("node runtime is unavailable")
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    function_source = frontend[frontend.index("function generateAllAssetImages"):frontend.index("async function runAssetImageBatch")]
    script = f"""
const source = {json.dumps(function_source)};
const project = {{ id:'p1' }};
let activeProjectRecord = {{ value:project }}, projectSession = 7;
let assetBatchFlight, assetBatchFlightKey = '', activeAssetBatchToken = '', assetBatchEpoch = 0;
let assetBatchController = {{ value:undefined }}, assetImagesRunning = {{ value:false }};
let assetBatchGenerating = {{ value:false }}, activeAssetGenerationKey = {{ value:'' }};
let calls = 0, release;
const blocked = new Promise(resolve => release = resolve);
function isCurrentProjectSession(id, session) {{ return id === 'p1' && session === 7; }}
function reclaimAssetBatchProjection() {{ throw new Error('unexpected reclaim'); }}
function runAssetImageBatch() {{ calls += 1; return blocked; }}
async function persistAssetState() {{}}
eval(source);
const first = generateAllAssetImages(project, 7);
const second = generateAllAssetImages(project, 7);
if (first !== second || calls !== 1) throw new Error(`identity=${{first === second}} calls=${{calls}}`);
release(); Promise.all([first, second]).then(() => process.stdout.write('ok'));
"""
    completed = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True, env=os.environ.copy())
    assert completed.stdout == "ok"


def test_asset_variant_terminal_reconciliation_executes_completed_and_failed_paths():
    node = shutil.which("node")
    if not node:
        pytest.skip("node runtime is unavailable")
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    source = frontend[frontend.index("async function recoverCompletedAssetImages"):frontend.index("const assetResultRecoveryTimer")]
    source = source.replace("] as const", "]")
    source = source.replace('assetService.characterResult<{ status:string; image?:{ url:string }; error?:string }>', 'assetService.characterResult')
    script = f"""
const source = {json.dumps(source)};
const project = {{id:'p1'}};
let activeProjectRecord = {{value:project}}, assetResultRecoveryRunning = false;
let autoResumedInterruptedAssetJobs = new Set(), persisted = 0, revealed = 0;
let characterProfiles = {{value:[]}}, propProfiles = {{value:[]}}, sceneProfiles = {{value:[]}};
let assetStatus = {{value:'generating'}}, assetError = {{value:''}};
function assetBaselineJobName() {{ return 'unused'; }}
function userFacingGenerationError(value) {{ return String(value || 'failed'); }}
async function revealCompletedUnit() {{ revealed += 1; }}
async function persistAssetState() {{ persisted += 1; }}
const assetService = {{ characterResult:async name => responseByName[name] || null }};
let responseByName = {{}};
eval(source);
async function run(result) {{
  persisted = 0; revealed = 0; assetStatus.value = 'generating'; assetError.value = '';
  const variant = {{id:'character-angle-2', label:'左45°全身', status:'generating'}};
  const item = {{name:'苏璃', generation_nonce:'n1', image_url:'/baseline.png', status:'generating', detail_assets:[variant]}};
  characterProfiles.value = [item];
  responseByName = {{'p1_n1_character_苏璃_angle_2':{{ok:true,data:result}}}};
  await recoverCompletedAssetImages();
  return {{item, variant, persisted, revealed}};
}}
(async () => {{
  const done = await run({{status:'completed',image:{{url:'/angle.png'}}}});
  if (done.variant.image_url !== '/angle.png' || done.variant.status !== 'waiting_confirmation' || done.persisted !== 1 || done.revealed !== 1) throw new Error('completed variant was not durably projected');
  const failed = await run({{status:'failed',error:'服务重启已回收残留图片任务，请重新生成'}});
  if (failed.variant.status !== 'failed' || failed.item.status !== 'failed' || failed.persisted !== 1 || !failed.variant.error.includes('服务重启')) throw new Error('failed variant terminal state was not durably projected');
  process.stdout.write('ok');
}})();
"""
    completed = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True, env=os.environ.copy())
    assert completed.stdout == "ok"


def test_character_baseline_separates_identity_from_conflicting_camera_language():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    baseline = frontend[frontend.index("async function generateAssetBaseline"):frontend.index("async function generateAsset3D")]
    assert 'identity_prompt:kind === "character" ? identityPrompt : ""' in baseline
    backend = BACKEND
    section = backend[backend.index('if parsed.path == "/api/characters/generate" and asset_kind == "character" and asset_phase == "baseline"'):]
    assert "identity_description = re.sub(" in section
    assert "近照|半身\\s*(?:照)?|全身\\s*(?:照|视图)?" in section
    assert 'candidate["orientation_mirrored"] = False' in section
    assert 'lambda current: _validate_character_variant(' in section
    assert 'current.get("url", "")' in section
    validator = backend[backend.index("def _validate_character_variant"):backend.index("def _transcribe_media")]
    assert '_character_variant_verdict_passes(verdict, target_pose, bool(strict_clothing_reference))' in validator
    assert '"left_45_face_angle_30_to_60", *CHARACTER_FULL_BODY_ANATOMY_CHECKS' in backend


def test_all_notify_prompts_render_as_assistant_chat_messages_without_toast_overlay():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    notify = frontend[frontend.index("function notify"):frontend.index("async function writeClipboardText")]
    assert 'chats.value.push({ side:"left", text, status:"系统提示"' in notify
    assert "last?.notice && last.text === text" in notify
    assert "chatScroll.value.scrollTop = chatScroll.value.scrollHeight" in notify
    assert '<div v-if="toast" class="toast">' not in frontend
    assert "const toast = ref" not in frontend
    assert "filter(chat => !chat.notice)" in frontend


def test_asset_item_errors_do_not_leak_into_another_character_dialog():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    projection = frontend[frontend.index("const assetStageError"):frontend.index("const assetImagesRunning")]
    assert "message.startsWith(`${item.name}：`)" in projection
    assert 'return allAssetProfiles.value.some' in projection
    assert 'v-if="assetStageError' in frontend
    assert 'userFacingGenerationError(assetStageError)' in frontend
    confirm = frontend[frontend.index("async function confirmAsset("):frontend.index("async function confirmAssetVariant")]
    assert 'currentAssetError.startsWith(`${profile.name}：`)' in confirm
    assert 'if (allAssetProfiles.value.some' in confirm
    assert '{ name:`${item.name}-已确认0度正面全身基准图`, url:identityReferenceUrl }' in frontend


def test_storyboard_assets_auto_generate_without_manual_upload_reset():
    frontend = (ROOT / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
    entry = frontend[frontend.index("function enterAssetGeneration"):frontend.index("async function stopAllAssetGeneration")]
    assert 'const entryKey = `${project.id}:${session}`' in entry
    assert "assetEntryPromiseKey === entryKey" in entry
    assert "assetEntryPromise === singleFlight && assetEntryPromiseKey === entryKey" in entry
    assert "无需手动上传" in entry
    assert 'enqueueAssetOperation(`${project.id}:generate-all`' in entry
    assert "generateAllAssetImages(project, session)" in entry
    assert "isCurrentProjectSession(project.id, session)" in entry
    for destructive in ("item.image_url = undefined", "item.detail_assets = []", "item.generation_nonce = crypto.randomUUID()"):
        assert destructive not in entry
    assert "资产上传槽已创建" not in frontend
    batch = frontend[frontend.index("async function runAssetImageBatch"):frontend.index("async function confirmAsset(")]
    assert "const authoritativeAssetStageReady = async () =>" in batch
    assert "productionLedgerService.workflow(productionTaskContext(project))" in batch
    assert '["pending_confirmation", "completed"].includes' in batch
    assert 'await runProductionAssetExtraction("manual", project, session)' in batch
    assert batch.index("if (!await authoritativeAssetStageReady())") < batch.index("await generateAssetBaseline")


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
    assert "ACTIVE_PRODUCTION_STAGE_CANCEL_EVENTS.get(target_key)" in cancel
    assert "cancelled = int(TASK_LEASES.request_cancel" in cancel
    stop_route = BACKEND[BACKEND.index('if parsed.path == "/api/generation/stop" and body.get("kind") == "storyboard"'):]
    assert "HTTPStatus.BAD_REQUEST" in stop_route
    assert '"error":"invalid_production_scope"' in stop_route
