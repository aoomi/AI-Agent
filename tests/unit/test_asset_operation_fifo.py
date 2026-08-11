from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
APP_PATH = ROOT / "plugins/builtin/short_drama/frontend/App.vue"


def _load_backend():
    spec = importlib.util.spec_from_file_location("asset_fifo_backend", BACKEND_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_asset_confirmation_is_durable_but_stage_promotion_can_be_deferred(tmp_path):
    module = _load_backend()
    module.PRODUCTION_LEDGER = module.ProductionLedger(tmp_path / "ledger.sqlite")
    payload = {
        "tenant_id": "t", "user_id": "u", "project_id": "p",
        "stage": "assets", "scope_type": "asset", "scope_id": "scene:大厅",
        "lifecycle": "pending_confirmation", "content_fingerprint": "fp", "audit_batch_id": "batch",
    }
    module.PRODUCTION_LEDGER.upsert(payload)

    class Brain:
        def validate_completion(self, *_args, **_kwargs):
            raise ValueError("previous stage is not completed: storyboard")

        def report(self, _payload, stage, lifecycle, **evidence):
            return {"stage": stage, "lifecycle": lifecycle, **evidence}

    module._production_orchestrator = lambda: Brain()
    record, workflow = module._confirm_asset_scope_deferred(payload)
    assert record["lifecycle"] == "completed"
    assert record["confirmation"]["confirmed_at"]
    assert workflow["lifecycle"] == "pending_confirmation"
    assert workflow["deferred_confirmation"] is True
    assert workflow["deferred_reason"] == "previous stage is not completed: storyboard"


def test_asset_ui_operations_share_one_fifo_and_stop_invalidates_pending_work():
    frontend = APP_PATH.read_text(encoding="utf-8")
    assert "let assetOperationTail:Promise<void> = Promise.resolve()" in frontend
    assert "const queuedAssetOperationOwners = new Map<string, string>()" in frontend
    assert "queuedAssetOperationOwners.get(key) === ownerToken" in frontend
    assert "const scheduled = assetOperationTail.catch(() => undefined).then(async () =>" in frontend
    assert "while (assetImagesRunning.value)" in frontend
    assert "assetOperationTail = scheduled.then(() => undefined, () => undefined)" in frontend
    assert frontend.count("assetOperationEpoch += 1") >= 2
    for operation in (
        "queueGenerateAllAssetImages", "queueAssetSlideAcceptance", "queueAssetBaselineAcceptance",
        "queueAssetSlideRegeneration", "queueAssetSlideRepair", "queueAsset3D",
        "queueAsset3DConfirmation", "queueAssetUpscale",
    ):
        assert operation in frontend
    assert "return enqueueAssetOperation(`${project.id}:import:" in frontend
    assert '@stop3d="stopAsset3D(item)"' in frontend


def test_asset_fifo_real_function_order_owner_and_epoch_fences():
    frontend = APP_PATH.read_text(encoding="utf-8")
    source = frontend[frontend.index("function enqueueAssetOperation"):frontend.index("function queueGenerateAllAssetImages")]
    source = source.replace("key:string, label:string, operation:() => void | Promise<void>", "key, label, operation")
    node = "/Users/aoo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    script = f"""
const source = {json.dumps(source)};
let projectSession=1, activeProjectRecord={{value:{{id:'p1'}}}}, assetOperationTail=Promise.resolve(), assetOperationEpoch=0;
const queuedAssetOperationOwners=new Map(), queuedAssetOperationCount={{value:0}}, assetImagesRunning={{value:false}};
const crypto={{randomUUID:(()=>{{let n=0; return()=>`owner-${{++n}}`;}})()}}, window={{setTimeout}}, notices=[];
function notify(x){{notices.push(x)}} function isCurrentProjectSession(id,s){{return activeProjectRecord.value.id===id&&projectSession===s}}
eval(source);
const order=[]; let releaseA, releaseOld, releaseNew;
const waitFor=async(test)=>{{for(let i=0;i<20&&!test();i++) await new Promise(r=>setTimeout(r,0)); if(!test()) throw Error('wait timeout')}};
const a=enqueueAssetOperation('a','A',()=>new Promise(r=>{{releaseA=()=>{{order.push('a');r()}}}}));
const duplicate=enqueueAssetOperation('a','A duplicate',()=>{{order.push('duplicate')}});
const b=enqueueAssetOperation('b','B',()=>{{order.push('b')}});
setTimeout(async()=>{{
 await waitFor(()=>releaseA); if(queuedAssetOperationOwners.size!==2) throw Error('initial owners'); releaseA(); await Promise.all([a,b,duplicate]);
 if(order.join(',')!=='a,b'||order.includes('duplicate')) throw Error(`order=${{order}}`);
 const old=enqueueAssetOperation('same','old',()=>new Promise(r=>releaseOld=r)); await waitFor(()=>releaseOld);
 assetOperationEpoch+=1; queuedAssetOperationOwners.clear(); queuedAssetOperationCount.value=0;
 activeProjectRecord.value={{id:'p2'}}; projectSession+=1;
 const newer=enqueueAssetOperation('same','new',()=>new Promise(r=>releaseNew=r));
 await new Promise(r=>setTimeout(r,0)); if(releaseNew) throw Error('new task bypassed running old task');
 releaseOld(); await old; await waitFor(()=>releaseNew);
 const newOwner=queuedAssetOperationOwners.get('same');
 if(queuedAssetOperationOwners.get('same')!==newOwner||queuedAssetOperationCount.value!==1) throw Error('old finally removed new owner');
 releaseNew(); await newer;
 if(queuedAssetOperationOwners.has('same')||queuedAssetOperationCount.value!==0) throw Error('new owner not released');
 process.stdout.write('ok');
}},0);
"""
    completed = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    assert completed.stdout == "ok"


def test_production_conflicts_are_http_responses_not_broken_connections():
    backend = BACKEND_PATH.read_text(encoding="utf-8")
    production = backend[backend.index('if parsed.path.startswith("/api/production/")'):]
    assert '_confirm_asset_scope_deferred(payload)' in production
    assert 'except ValueError as error:' in production
    assert '"error":"production_stage_conflict"' in production


def test_deferred_storyboard_error_is_migrated_without_hiding_real_errors():
    frontend = APP_PATH.read_text(encoding="utf-8")
    assert 'const deferredAssetConfirmationError = "previous stage is not completed: storyboard"' in frontend
    assert 'const circularAssetConstructionError = "previous stage is not completed: assets"' in frontend
    assert 'const isDeferredAssetConfirmationError' in frontend
    assert 'message.endsWith(`：${error}`)' in frontend
    assert 'if (!isDeferredAssetConfirmationError(variant.error)) continue' in frontend
    assert 'variant.status = variant.image_url ? "waiting_confirmation" : "pending"' in frontend
    assert 'isDeferredAssetConfirmationError(item.error)' in frontend


def test_asset_construction_is_not_blocked_by_its_own_aggregate_stage_gate():
    backend = BACKEND_PATH.read_text(encoding="utf-8")
    assert 'def _is_asset_subtask_request(path: str, body: dict)' in backend
    assert 'path == "/api/assets/3d/generate"' in backend
    assert 'str(body.get("asset_kind") or "").strip() in {"character", "scene", "prop"}' in backend
    assert 'str(body.get("asset_phase") or "").strip() in {"baseline", "variant", "repair"}' in backend
    assert 'not _is_asset_subtask_request(parsed.path, body)' in backend
    module = _load_backend()
    for kind in ("character", "scene", "prop"):
        for phase in ("baseline", "variant", "repair"):
            assert module._is_asset_subtask_request("/api/characters/generate", {"asset_kind": kind, "asset_phase": phase})
    assert module._is_asset_subtask_request("/api/assets/3d/generate", {})
    assert not module._is_asset_subtask_request("/api/shots/generate", {"asset_kind": "character", "asset_phase": "baseline"})


def test_continue_generation_preserves_completed_asset_files():
    frontend = APP_PATH.read_text(encoding="utf-8")
    batch = frontend[frontend.index("async function runAssetImageBatch"):frontend.index("async function confirmAsset(")]
    assert 'const assetImageActionLabel = computed(() => generatedAssetCount.value === 0 ? "生成图片" : "继续生成图片")' in frontend
    assert "assetService.purgeGenerated" not in batch
    assert '].filter(({ item }) => !item.image_url);' in batch
    assert "preserve every completed asset" in batch


def test_asset_stage_rejects_missing_local_media_projection(tmp_path):
    module = _load_backend()
    module.OUTPUT_ROOT = tmp_path
    (tmp_path / "images").mkdir()
    existing = tmp_path / "images" / "kept.png"
    existing.write_bytes(b"png")
    data = {
        "characters": [
            {"name": "missing", "status": "waiting_confirmation", "image_url": "/api/result-media?filename=gone.png&subfolder=images", "baseline_confirmed_at": "now"},
            {"name": "kept", "status": "waiting_confirmation", "image_url": "/api/result-media?filename=kept.png&subfolder=images"},
        ],
        "scenes": [], "props": [],
    }
    sanitized = module._sanitize_asset_media_projection(data)
    assert sanitized["characters"][0]["image_url"] is None
    assert sanitized["characters"][0]["status"] == "pending"
    assert sanitized["characters"][0]["baseline_confirmed_at"] is None
    assert sanitized["characters"][1]["image_url"].endswith("kept.png&subfolder=images")


def test_character_baseline_uses_three_adaptive_validation_candidates():
    backend = BACKEND_PATH.read_text(encoding="utf-8")
    marker = backend.index("baseline_required_checks = (")
    section = backend[marker - 300:]
    section = section[:section.index('if parsed.path == "/api/characters/generate" and asset_kind == "prop":')]
    assert "_run_character_full_frame_candidate_loop(" in section
    assert "max_attempts=3" in section
    assert "baseline_required_checks" in section
    assert "failed_checks = [key for key in baseline_required_checks if verdict.get(key) is not True]" in section
    assert "automatic retry {retry_number - 1} of 2" in section
    assert "自动生成3次仍未通过规范验收" in section
    assert 'image["validation_attempts"] = validation_attempts' in section
