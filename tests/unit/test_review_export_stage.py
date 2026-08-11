import importlib.util
from pathlib import Path
import threading
from tempfile import TemporaryDirectory

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
FRONTEND = ROOT / "plugins/builtin/short_drama/frontend/App.vue"


def load_backend(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_review_audit_batches_unique_episodes_and_preserves_evidence() -> None:
    module = load_backend("review_export_audit")
    calls = []
    module._local_api = lambda path, body: calls.append((path, body)) or {
        "status":"pass", "issues":[], "evidence":{"validator":"gate-v1"},
    }
    result = module._run_server_production_stage({
        "stage":"review_export", "operation":"audit", "context":{"tenant_id":"t"},
        "commands":[{"episode":1, "path":"one.mp4"}, {"episode":2, "path":"two.mp4"}],
    })
    assert [item[0] for item in calls] == ["/api/videos/audit", "/api/videos/audit"]
    assert [item["episode"] for item in result["items"]] == [1, 2]
    assert result["items"][0]["evidence"] == {"validator":"gate-v1"}


def test_review_audit_rejects_duplicate_episode_before_local_call() -> None:
    module = load_backend("review_export_duplicate")
    calls = []
    module._local_api = lambda path, body: calls.append(path) or {}
    with pytest.raises(ValueError, match="must be unique"):
        module._run_server_production_stage({
            "stage":"review_export", "operation":"audit",
            "commands":[{"episode":1}, {"episode":1}],
        })
    assert calls == []


def test_review_export_fails_closed_without_confirmed_audit() -> None:
    module = load_backend("review_export_gate")
    calls = []
    module._local_api = lambda path, body: calls.append(path) or {}
    with pytest.raises(ValueError, match="authoritative confirmed audit"):
        module._run_server_production_stage({
            "tenant_id":"tenant", "user_id":"user", "project_id":"project",
            "stage":"review_export", "operation":"export", "command":{
                "source_version":"base", "items":[{"episode":1, "path":"one.mp4", "content_fingerprint":"media-fp"}],
                "audit_results":[{"episode":1, "status":"pass", "confirmed":False}],
            },
        })
    assert calls == []


def test_review_export_audit_disabled_still_rejects_empty_media_ledger() -> None:
    module = load_backend("review_export_no_media")
    calls = []
    module._local_api = lambda path, body: calls.append((path, body)) or {}
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = module.ProductionLedger(Path(temporary) / "ledger.sqlite")
        with pytest.raises(ValueError, match="authoritative confirmed audit and media"):
            module._run_server_production_stage({
                "tenant_id":"t", "user_id":"u", "project_id":"p", "stage":"review_export", "operation":"export",
                "command":{"source_version":"base", "items":[{"episode":1, "path":"one.mp4", "content_fingerprint":"media-fp"}], "audit_required":False},
            })
    assert calls == []


def test_review_export_audit_disabled_allows_only_confirmed_base_media() -> None:
    module = load_backend("review_export_media_only")
    calls = []
    module._local_api = lambda path, body: calls.append(path) or {"files":[], "manifest_url":"manifest.json"}
    identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = module.ProductionLedger(Path(temporary) / "ledger.sqlite")
        module.PRODUCTION_LEDGER.upsert({**identity, "stage":"composition", "scope_type":"episode", "scope_id":"1", "lifecycle":"pending_confirmation", "content_fingerprint":"media-fp", "audit_batch_id":"media-batch"})
        module.PRODUCTION_LEDGER.confirm({**identity, "stage":"composition", "scope_type":"episode", "scope_id":"1"})
        result = module._run_server_production_stage({**identity, "stage":"review_export", "operation":"export", "command":{"source_version":"base", "items":[{"episode":1, "path":"one.mp4", "content_fingerprint":"media-fp"}], "audit_required":False}})
    assert result["manifest_url"] == "manifest.json"
    assert calls == ["/api/exports/create"]


def test_review_export_only_accepts_matching_authoritative_audit_and_media() -> None:
    module = load_backend("review_export_authoritative")
    calls = []
    module._local_api = lambda path, body: calls.append(path) or {"files":[], "manifest_url":"manifest.json"}
    identity = {"tenant_id":"tenant-a", "user_id":"user-a", "project_id":"project-a"}
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = module.ProductionLedger(Path(temporary) / "ledger.sqlite")
        for payload in (
            {"stage":"review_export", "scope_type":"episode", "scope_id":"review:1", "content_fingerprint":"audit-fp", "audit_batch_id":"audit-batch"},
            {"stage":"composition", "scope_type":"episode", "scope_id":"1", "content_fingerprint":"media-fp", "audit_batch_id":"media-batch"},
        ):
            module.PRODUCTION_LEDGER.upsert({**identity, **payload, "lifecycle":"pending_confirmation"})
            module.PRODUCTION_LEDGER.confirm({**identity, "stage":payload["stage"], "scope_type":payload["scope_type"], "scope_id":payload["scope_id"]})
        command = {
            "source_version":"base",
            "items":[{"episode":1, "path":"one.mp4", "content_fingerprint":"media-fp"}],
            "audit_results":[{"episode":1, "status":"pass", "confirmed":True, "content_fingerprint":"audit-fp", "audit_batch_id":"audit-batch"}],
        }
        result = module._run_server_production_stage({**identity, "stage":"review_export", "operation":"export", "command":command})
        assert result["manifest_url"] == "manifest.json"
        assert calls == ["/api/exports/create"]
        calls.clear()
        for mutation in (
            {"content_fingerprint":"forged"},
            {"audit_batch_id":"old-batch"},
            {"confirmed":False},
        ):
            forged = {**command, "audit_results":[{**command["audit_results"][0], **mutation}]}
            with pytest.raises(ValueError, match="authoritative confirmed audit"):
                module._run_server_production_stage({**identity, "stage":"review_export", "operation":"export", "command":forged})
        assert calls == []


def test_review_export_rejects_cross_tenant_and_stale_media_without_export_call() -> None:
    module = load_backend("review_export_scope")
    calls = []
    module._local_api = lambda path, body: calls.append(path) or {}
    owner = {"tenant_id":"tenant-a", "user_id":"user-a", "project_id":"project-a"}
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = module.ProductionLedger(Path(temporary) / "ledger.sqlite")
        for payload in (
            {"stage":"review_export", "scope_type":"episode", "scope_id":"review:1", "content_fingerprint":"audit-fp", "audit_batch_id":"audit-batch"},
            {"stage":"composition", "scope_type":"episode", "scope_id":"1", "content_fingerprint":"media-fp", "audit_batch_id":"media-batch"},
        ):
            module.PRODUCTION_LEDGER.upsert({**owner, **payload, "lifecycle":"pending_confirmation"})
            module.PRODUCTION_LEDGER.confirm({**owner, "stage":payload["stage"], "scope_type":payload["scope_type"], "scope_id":payload["scope_id"]})
        command = {"source_version":"base", "items":[{"episode":1, "path":"one.mp4", "content_fingerprint":"stale-media"}], "audit_results":[{"episode":1, "status":"pass", "confirmed":True, "content_fingerprint":"audit-fp", "audit_batch_id":"audit-batch"}]}
        with pytest.raises(ValueError, match="authoritative confirmed audit"):
            module._run_server_production_stage({**owner, "stage":"review_export", "operation":"export", "command":command})
        with pytest.raises(ValueError, match="authoritative confirmed audit"):
            module._run_server_production_stage({**owner, "tenant_id":"tenant-b", "stage":"review_export", "operation":"export", "command":{**command, "items":[{"episode":1, "path":"one.mp4", "content_fingerprint":"media-fp"}]}})
        assert calls == []


def test_review_export_source_version_never_cross_matches_base_and_enhanced() -> None:
    module = load_backend("review_export_source_version")
    calls = []
    module._local_api = lambda path, body: calls.append(path) or {"files":[], "manifest_url":"manifest.json"}
    identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = module.ProductionLedger(Path(temporary) / "ledger.sqlite")
        base_payload = {"stage":"composition", "scope_type":"episode", "scope_id":"1", "content_fingerprint":"base-fp", "audit_batch_id":"base-batch"}
        module.PRODUCTION_LEDGER.upsert({**identity, **base_payload, "lifecycle":"pending_confirmation"})
        module.PRODUCTION_LEDGER.confirm({**identity, "stage":"composition", "scope_type":"episode", "scope_id":"1"})
        enhanced_key = {**identity, "stage":"review_export", "scope_type":"episode", "scope_id":"upscale:1"}
        enhanced_generation = module.PRODUCTION_LEDGER.reserve_upscale_generation(enhanced_key)
        module.PRODUCTION_LEDGER.commit_upscale_authority({**enhanced_key, "generation":enhanced_generation, "content_fingerprint":"enhanced-fp", "audit_batch_id":"enhanced-batch", "production_evidence":{"provider":"upscaler"}, "audit_evidence":{"final":{"status":"pass", "evidence":{"score":1}}}})
        module.PRODUCTION_LEDGER.confirm(enhanced_key)
        for source_version, fingerprint, batch in (("base", "enhanced-fp", None), ("enhanced", "base-fp", "base-batch")):
            with pytest.raises(ValueError, match="authoritative confirmed audit and media"):
                module._run_server_production_stage({**identity, "stage":"review_export", "operation":"export", "command":{"source_version":source_version, "audit_required":False, "items":[{"episode":1, "path":"one.mp4", "content_fingerprint":fingerprint, "audit_batch_id":batch}]}})
        for source_version, fingerprint, batch, generation in (("base", "base-fp", None, None), ("enhanced", "enhanced-fp", "enhanced-batch", enhanced_generation)):
            module._run_server_production_stage({**identity, "stage":"review_export", "operation":"export", "command":{"source_version":source_version, "audit_required":False, "items":[{"episode":1, "path":"one.mp4", "content_fingerprint":fingerprint, "audit_batch_id":batch, "generation":generation}]}})
    assert calls == ["/api/exports/create", "/api/exports/create"]


def test_review_export_legacy_evidence_defaults_are_base_only() -> None:
    module = load_backend("review_export_legacy_evidence_boundary")
    identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = module.ProductionLedger(Path(temporary) / "ledger.sqlite")
        module.PRODUCTION_LEDGER.upsert({**identity, "stage":"composition", "scope_type":"episode", "scope_id":"1", "lifecycle":"pending_confirmation", "content_fingerprint":"base-fp", "audit_batch_id":"base-batch"})
        module.PRODUCTION_LEDGER.confirm({**identity, "stage":"composition", "scope_type":"episode", "scope_id":"1"})
        module.PRODUCTION_LEDGER.upsert_projection({**identity, "stage":"review_export", "scope_type":"episode", "scope_id":"upscale:1", "lifecycle":"completed", "content_fingerprint":"enhanced-fp", "audit_batch_id":"enhanced-batch", "production_evidence":{"forged":True}})
        base = module._validated_review_export_authority(identity, {"source_version":"base", "items":[{"episode":1, "content_fingerprint":"base-fp"}], "audit_results":[]}, [1], audit_required=False)
        assert base[1]["production_evidence"] == {"status":"not_available", "reason":"legacy_base_scope"}
        assert base[1]["audit_evidence"] == {"status":"not_applicable", "reason":"legacy_base_scope"}
        with pytest.raises(ValueError, match="authoritative confirmed audit and media"):
            module._validated_review_export_authority(identity, {"source_version":"enhanced", "items":[{"episode":1, "content_fingerprint":"enhanced-fp", "audit_batch_id":"enhanced-batch"}], "audit_results":[]}, [1], audit_required=False)


def test_review_export_multi_episode_missing_one_media_is_zero_side_effect() -> None:
    module = load_backend("review_export_multi_missing")
    calls = []
    module._local_api = lambda path, body: calls.append(path) or {}
    identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = module.ProductionLedger(Path(temporary) / "ledger.sqlite")
        module.PRODUCTION_LEDGER.upsert({**identity, "stage":"composition", "scope_type":"episode", "scope_id":"1", "lifecycle":"pending_confirmation", "content_fingerprint":"one-fp", "audit_batch_id":"one-batch"})
        module.PRODUCTION_LEDGER.confirm({**identity, "stage":"composition", "scope_type":"episode", "scope_id":"1"})
        with pytest.raises(ValueError, match=r"\[2\]"):
            module._run_server_production_stage({**identity, "stage":"review_export", "operation":"export", "command":{"source_version":"base", "audit_required":False, "items":[{"episode":1, "path":"one.mp4", "content_fingerprint":"one-fp"}, {"episode":2, "path":"two.mp4", "content_fingerprint":"two-fp"}]}})
    assert calls == []


def test_review_cancel_between_audits_never_submits_next_episode() -> None:
    module = load_backend("review_export_cancel")
    event = threading.Event(); calls = []
    def local(path, body):
        calls.append((path, body)); event.set()
        return {"status":"pass", "issues":[]}
    module._local_api = local
    with pytest.raises(RuntimeError, match="cancelled or lease lost"):
        module._run_server_production_stage({
            "stage":"review_export", "operation":"audit", "_cancel_event":event,
            "commands":[{"episode":1}, {"episode":2}],
        })
    assert len(calls) == 1


def test_review_transient_failure_retries_once_and_keeps_diagnostic_result() -> None:
    module = load_backend("review_export_retry")
    calls = []
    def local(path, body):
        calls.append((path, body))
        raise RuntimeError("audit provider unavailable")
    module._local_api = local
    result = module._run_server_production_stage({
        "stage":"review_export", "operation":"audit",
        "commands":[{"episode":1, "max_attempts":2}],
    })
    assert len(calls) == 2
    assert result["items"] == [{
        "episode":1, "status":"needs_fix", "issues":["audit provider unavailable"],
        "evidence":{"error_type":"RuntimeError", "attempt":2}, "attempts":2,
    }]


def test_frontend_final_audit_and_export_use_server_stage() -> None:
    source = FRONTEND.read_text(encoding="utf-8")
    audit = source[source.index("async function auditFinalEpisodes"):source.index("async function confirmEpisodeAudit")]
    export = source[source.index("function createExports"):source.index("async function downloadExportBatch")]
    assert 'stage:"review_export", operation:"audit"' in audit
    assert audit.count("productionLedgerService.runStage") == 1
    assert "while (attempts" not in audit
    assert "commands:[{" not in audit
    assert "mediaService.finalAudit" not in audit
    assert 'stage:"review_export", operation:"export"' in export
    assert "mediaService.createExport" not in export


def test_frontend_export_is_project_scoped_abortable_single_flight() -> None:
    source = FRONTEND.read_text(encoding="utf-8")
    export = source[source.index("function createExports"):source.index("async function downloadExportBatch")]
    abort = source[source.index("function abortProjectWork"):source.index("function isCurrentProjectSession")]
    assert "exportFlight && exportFlightProjectId === project.id" in export
    assert "return exportFlight" in export
    assert "const session = projectSession" in export
    assert "const controller = new AbortController()" in export
    assert "controller.signal" in export
    assert export.count("productionLedgerService.runStage") == 1
    assert "const isCurrentExport = () => epoch === exportFlightEpoch && isCurrentProjectSession(project.id, session) && !controller.signal.aborted" in export
    assert export.count("if (!isCurrentExport()) return") >= 6
    assert "if (exportFlight === flight)" in export
    assert "exportFlight = undefined" in export
    assert "exportController.value?.abort()" in abort
    assert "@pause=\"stopExports\"" in source


def test_export_stop_is_exact_server_stage_stop_and_fences_old_flight() -> None:
    source = FRONTEND.read_text(encoding="utf-8")
    stop = source[source.index("async function stopExports"):source.index("async function downloadExportBatch")]
    service = (ROOT / "plugins/builtin/short_drama/frontend/services/production-ledger.service.ts").read_text(encoding="utf-8")
    backend = BACKEND.read_text(encoding="utf-8")
    assert stop.count("productionLedgerService.stopStage") == 1
    assert '{ ...productionTaskContext(project), stage:"review_export" }' in stop
    assert "exportFlightEpoch += 1" in stop
    assert stop.index("exportFlight = undefined") < stop.index("await productionLedgerService.stopStage")
    assert "if (!stopped.stopped || !stopped.stage_cancelled)" in stop
    assert "停止导出失败" in stop
    assert 'postJson<{ stopped:boolean; stage_cancelled:boolean }>("/api/generation/stop"' in service
    stage_stop = backend[backend.index('if parsed.path == "/api/generation/stop" and body.get("stage")'):backend.index('if parsed.path == "/api/generation/stop" and body.get("kind")')]
    assert "_cancel_scoped_production_stage(body, stage)" in stage_stop
    assert '"production_stage_not_running"' in stage_stop
