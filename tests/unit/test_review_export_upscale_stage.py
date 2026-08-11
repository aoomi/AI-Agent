import importlib.util
import json
from pathlib import Path
import pytest
import math
import threading
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
from plugins.builtin.short_drama.workflows.production_ledger import ProductionLedger, ProductionLedgerError


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
APP = ROOT / "plugins/builtin/short_drama/frontend/App.vue"


def load_backend():
    spec = importlib.util.spec_from_file_location("review_export_upscale_test", BACKEND)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module._checkpoint_production_stage = lambda *_args, **_kwargs: None
    return module


def command(episode=1, path="/base.mp4"):
    return {"episode":episode, "path":path, "source_version":"base", "target":{"width":1080, "height":1920, "fps":30, "mode":"quality"}}


def request(commands):
    return {"tenant_id":"tenant", "user_id":"user", "project_id":"project", "stage":"review_export", "operation":"upscale", "commands":commands, "context":{}}


def test_upscale_batch_is_server_owned_and_serial_with_real_audits():
    module = load_backend(); calls = []; temporary = TemporaryDirectory(); module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary.name) / "ledger.sqlite")
    def local(_body, _stage, endpoint, payload):
        calls.append((endpoint, payload.get("episode")))
        if endpoint == "/api/videos/upscale": return {"video_url":f"/e{payload['episode']}.mp4", "path":f"/e{payload['episode']}.mp4", "production_evidence":"real"}
        if endpoint == "/api/videos/audit": return {"status":"pass", "evidence":{"real":True}}
        return {"status":"pass", "evidence":{"provider":endpoint}}
    module._production_stage_local_api = local
    result = module._run_server_production_stage(request([
        {**command(1, "/base1.mp4"), "subtitles":[{"text":"a"}], "reference_urls":["/face.png"]},
        {**command(2, "/base2.mp4"), "subtitles":[], "reference_urls":[]},
    ]))
    assert [item["episode"] for item in result["items"]] == [1, 2]
    assert all(item["status"] == "waiting_confirmation" for item in result["items"])
    assert len({item["audit_batch_id"] for item in result["items"]}) == 1
    assert all(len(item["content_fingerprint"]) == 64 and item["production_evidence"] and item["audit_evidence"] for item in result["items"])
    assert [item[0] for item in calls] == [
        "/api/videos/upscale", "/api/subtitles/ocr-audit", "/api/videos/face-consistency-audit", "/api/videos/audit",
        "/api/videos/upscale", "/api/videos/audit",
    ]


def test_upscale_failure_does_not_fake_success_or_continue_next_episode():
    module = load_backend(); calls = []; temporary = TemporaryDirectory(); module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary.name) / "ledger.sqlite")
    def local(_body, _stage, endpoint, payload):
        calls.append((endpoint, payload.get("episode")))
        if endpoint == "/api/videos/upscale": return {"video_url":"/e.mp4", "path":"/e.mp4"}
        return {"status":"needs_fix", "issues":["bad"]}
    module._production_stage_local_api = local
    try:
        module._run_server_production_stage(request([command(1, "/1"), command(2, "/2")]))
    except RuntimeError as error:
        assert "final audit failed" in str(error)
    else:
        raise AssertionError("failed audit must fail the stage")
    assert not any(episode == 2 for _, episode in calls)
    assert module.PRODUCTION_LEDGER.list(request([])) == []


@pytest.mark.parametrize("commands", [
    [], None, [None], [{}],
    [command(0)], [command(-1)], [command("x")], [command("1.5")], [command(True)],
    [command(1), command(1, "/other.mp4")],
    [command(1, "")], [command(1, "relative.mp4")], [command(1, "http:///missing-host")],
    [{**command(1), "source_version":"enhanced"}],
    [{key:value for key, value in command(1).items() if key != "source_version"}],
    [{**command(1), "target":None}],
    [{**command(1), "target":{"width":0, "height":1920, "fps":30, "mode":"quality"}}],
    [{**command(1), "target":{"width":1080, "height":1920, "fps":30, "mode":"unknown"}}],
    [command(1), {**command(2), "path":""}],
])
def test_invalid_upscale_batch_fails_before_every_provider_call(commands):
    module = load_backend(); calls = []
    module._production_stage_local_api = lambda *_args, **_kwargs: calls.append(1)
    with pytest.raises(ValueError):
        module._run_server_production_stage(request(commands))
    assert calls == []


def test_upscale_ledger_confirmation_strictly_authorizes_enhanced_export():
    module = load_backend(); temporary = TemporaryDirectory(); module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary.name) / "ledger.sqlite")
    def local(_body, _stage, endpoint, payload):
        if endpoint == "/api/videos/upscale": return {"video_url":"/enhanced.mp4", "path":"/enhanced.mp4", "production_evidence":"real-upscale"}
        return {"status":"pass", "evidence":{"provider":"real-audit", "episode":payload.get("episode")}}
    module._production_stage_local_api = local
    payload = request([command(1, "/base.mp4")])
    result = module._run_server_production_stage(payload)
    item = result["items"][0]
    module.PRODUCTION_LEDGER.commit_upscale_authorities(result.pop("_authority_records"))
    records = module.PRODUCTION_LEDGER.list(payload)
    assert records[0]["scope_id"] == "upscale:1" and records[0]["lifecycle"] == "pending_confirmation"
    reloaded = ProductionLedger(module.PRODUCTION_LEDGER.database)
    module.PRODUCTION_LEDGER = reloaded
    restored = reloaded.list(payload)[0]
    assert restored["production_evidence"] == "real-upscale"
    assert restored["audit_evidence"] == {"ocr":{"status":"not_applicable", "reason":"no_subtitles"}, "face":{"status":"not_applicable", "reason":"no_reference_urls"}, "final":{"status":"pass", "evidence":{"provider":"real-audit", "episode":1}}}
    confirmed = module.PRODUCTION_LEDGER.confirm({**payload, "scope_type":"episode", "scope_id":"upscale:1"})
    assert confirmed["lifecycle"] == "completed"
    export_command = {"source_version":"enhanced", "items":[{"episode":1, "content_fingerprint":item["content_fingerprint"], "audit_batch_id":item["audit_batch_id"], "generation":item["generation"]}], "audit_results":[]}
    authority = module._validated_review_export_authority(payload, {**export_command, "items":[{"episode":1, "content_fingerprint":item["content_fingerprint"], "audit_batch_id":item["audit_batch_id"], "generation":item["generation"], "production_evidence":{"tampered":True}, "audit_evidence":{"tampered":True}}]}, [1], audit_required=False)
    assert authority[1]["production_evidence"] == "real-upscale"
    assert authority[1]["audit_evidence"] == restored["audit_evidence"]
    with pytest.raises(ValueError):
        module._validated_review_export_authority(payload, {**export_command, "items":[{"episode":1, "content_fingerprint":"tampered"}]}, [1], audit_required=False)
    old_batch = item["audit_batch_id"]
    second_result = module._run_server_production_stage(payload)
    second = second_result["items"][0]
    module.PRODUCTION_LEDGER.commit_upscale_authorities(second_result.pop("_authority_records"))
    assert second["audit_batch_id"] != old_batch
    with pytest.raises(ValueError):
        module._validated_review_export_authority(payload, export_command, [1], audit_required=False)


def test_upscale_fingerprint_binds_all_inputs_steps_and_is_key_order_stable():
    def fingerprint(command_payload, evidence_score=0.99):
        module = load_backend(); temporary = TemporaryDirectory(); module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary.name) / "ledger.sqlite")
        module.uuid4 = lambda: SimpleNamespace(hex="fixed-authority-batch")
        def local(_body, _stage, endpoint, payload):
            if endpoint == "/api/videos/upscale": return {"video_url":"/enhanced.mp4", "path":"/enhanced.mp4", "production_evidence":"model-v1", "frames":1800}
            return {"status":"pass", "evidence":{"provider":endpoint, "score":evidence_score}}
        module._production_stage_local_api = local
        return module._run_server_production_stage(request([command_payload]))["items"][0]
    base = {**command(1), "subtitles":[{"start":0, "text":"hello"}], "reference_urls":["/face.png"], "process_audits":[{"shot_number":1, "face":"pass"}], "content_compliance_status":"pass"}
    first = fingerprint(base)
    reordered = fingerprint(dict(reversed(list(base.items()))))
    assert first["content_fingerprint"] == reordered["content_fingerprint"]
    assert first["audit_evidence"]["ocr"]["status"] == "pass"
    assert first["audit_evidence"]["face"]["status"] == "pass"
    assert first["audit_evidence"]["final"]["status"] == "pass"
    mutations = [
        {**base, "subtitles":[{"start":0, "text":"changed"}]},
        {**base, "reference_urls":["/other-face.png"]},
        {**base, "process_audits":[{"shot_number":1, "face":"needs_fix"}]},
        {**base, "content_compliance_status":"not_audited"},
    ]
    assert all(fingerprint(item)["content_fingerprint"] != first["content_fingerprint"] for item in mutations)
    assert fingerprint(base, evidence_score=0.5)["content_fingerprint"] != first["content_fingerprint"]
    no_optional = fingerprint(command(1))
    assert no_optional["audit_evidence"]["ocr"] == {"status":"not_applicable", "reason":"no_subtitles"}
    assert no_optional["audit_evidence"]["face"] == {"status":"not_applicable", "reason":"no_reference_urls"}


@pytest.mark.parametrize("enabled_field,endpoint", [("subtitles", "/api/subtitles/ocr-audit"), ("reference_urls", "/api/videos/face-consistency-audit")])
def test_enabled_upscale_audit_without_real_evidence_fails_closed(enabled_field, endpoint):
    module = load_backend(); temporary = TemporaryDirectory(); module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary.name) / "ledger.sqlite")
    def local(_body, _stage, called, _payload):
        if called == "/api/videos/upscale": return {"video_url":"/enhanced.mp4", "path":"/enhanced.mp4", "production_evidence":"real"}
        if called == endpoint: return {"status":"pass"}
        return {"status":"pass", "evidence":{"real":True}}
    module._production_stage_local_api = local
    payload = {**command(1), enabled_field:[{"text":"x"}] if enabled_field == "subtitles" else ["/face.png"]}
    with pytest.raises(RuntimeError, match="lacks evidence"):
        module._run_server_production_stage(request([payload]))
    assert module.PRODUCTION_LEDGER.list(request([])) == []


def test_structured_production_evidence_is_preserved_and_noncanonical_values_fail():
    module = load_backend(); temporary = TemporaryDirectory(); module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary.name) / "ledger.sqlite")
    structured = {"model":{"name":"upscaler", "params":{"scale":4, "tiles":[512, 512]}}, "frames":[1, 2]}
    def local(_body, _stage, endpoint, _payload):
        if endpoint == "/api/videos/upscale": return {"video_url":"/e.mp4", "path":"/e.mp4", "production_evidence":structured}
        return {"status":"pass", "evidence":{"nested":{"score":1}}}
    module._production_stage_local_api = local
    item = module._run_server_production_stage(request([command(1)]))["items"][0]
    assert item["production_evidence"] == structured
    assert isinstance(item["production_evidence"], dict)

    for invalid in ({}, [], "", {"score":math.nan}, {"bad":object()}):
        module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary.name) / f"ledger-{len(str(invalid))}.sqlite")
        module._production_stage_local_api = lambda _body, _stage, endpoint, _payload, invalid=invalid: (
            {"video_url":"/e.mp4", "path":"/e.mp4", "production_evidence":invalid}
            if endpoint == "/api/videos/upscale" else {"status":"pass", "evidence":{"ok":True}}
        )
        with pytest.raises(RuntimeError, match="empty|canonical JSON"):
            module._run_server_production_stage(request([command(1)]))


def _authoritative_upscale(ledger, key, fingerprint, batch, production, audit):
    generation = ledger.reserve_upscale_generation(key)
    return ledger.commit_upscale_authority({
        **key, "generation":generation, "content_fingerprint":fingerprint,
        "audit_batch_id":batch, "production_evidence":production,
        "audit_evidence":audit, "progress":{"completed":1, "total":1},
    })


def test_partial_deep_watch_projection_only_updates_progress_and_preserves_authority():
    with TemporaryDirectory() as temporary:
        database = Path(temporary) / "ledger.sqlite"
        ledger = ProductionLedger(database)
        identity = {"tenant_id":"tenant", "user_id":"user", "project_id":"project"}
        key = {**identity, "stage":"review_export", "scope_type":"episode", "scope_id":"upscale:1"}
        production = {"model":{"name":"upscaler", "params":{"scale":4}}, "frames":[1, 2]}
        audit = {"final":{"status":"pass", "evidence":{"provider":"audit"}}}
        authoritative = _authoritative_upscale(ledger, key, "same-fp", "batch-1", production, audit)
        projected = ledger.upsert_projection({
            **key, "lifecycle":"completed", "content_fingerprint":"forged-fp",
            "audit_batch_id":"forged-batch", "generation":999, "confirmation":{"forged":True},
            "progress":{"completed":0, "total":1, "production_evidence":{"forged":True}, "audit_evidence":None},
            "expected_revision":authoritative["revision"],
        })
        assert projected["progress"] == {"completed":0, "total":1}
        assert projected["content_fingerprint"] == "same-fp"
        assert projected["audit_batch_id"] == "batch-1"
        assert projected["generation"] == authoritative["generation"]
        assert projected["lifecycle"] == "pending_confirmation"
        assert projected["production_evidence"] == production
        assert projected["audit_evidence"] == audit
        assert "production_evidence" not in projected["progress"]
        assert ProductionLedger(database).list(identity)[0] == projected


def test_upscale_generation_is_monotonic_immutable_and_replay_protected_after_reload():
    with TemporaryDirectory() as temporary:
        database = Path(temporary) / "ledger.sqlite"
        first = ProductionLedger(database)
        key = {"tenant_id":"tenant", "user_id":"user", "project_id":"project", "stage":"review_export", "scope_type":"episode", "scope_id":"upscale:1"}
        old = _authoritative_upscale(first, key, "fp-1", "batch-1", {"provider":"v1"}, {"final":{"status":"pass"}})
        first.confirm(key)
        second = ProductionLedger(database)
        generation = second.reserve_upscale_generation(key)
        assert generation == old["generation"] + 1
        with pytest.raises(Exception, match="stale|unreserved"):
            second.commit_upscale_authority({**key, "generation":old["generation"], "content_fingerprint":"fp-1", "audit_batch_id":"batch-1", "production_evidence":{"provider":"v1"}, "audit_evidence":{"final":{"status":"pass"}}})
        with pytest.raises(Exception, match="replay"):
            second.commit_upscale_authority({**key, "generation":generation, "content_fingerprint":"fp-1", "audit_batch_id":"batch-1", "production_evidence":{"provider":"v1"}, "audit_evidence":{"final":{"status":"pass"}}})
        current = second.commit_upscale_authority({**key, "generation":generation, "content_fingerprint":"fp-2", "audit_batch_id":"batch-2", "production_evidence":{"provider":"v2"}, "audit_evidence":{"final":{"status":"pass"}}})
        assert current["confirmation"] is None and current["generation"] == generation
        assert second.commit_upscale_authority({**key, "generation":generation, "content_fingerprint":"fp-2", "audit_batch_id":"batch-2", "production_evidence":{"provider":"v2"}, "audit_evidence":{"final":{"status":"pass"}}}) == current
        with pytest.raises(Exception, match="immutable"):
            second.commit_upscale_authority({**key, "generation":generation, "content_fingerprint":"fp-2", "audit_batch_id":"batch-2", "production_evidence":{"provider":"forged"}, "audit_evidence":{"final":{"status":"pass"}}})
        assert ProductionLedger(database).list(key)[0] == current


def test_enhanced_export_requires_exact_confirmed_generation():
    module = load_backend()
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary) / "ledger.sqlite")
        identity = {"tenant_id":"tenant", "user_id":"user", "project_id":"project"}
        key = {**identity, "stage":"review_export", "scope_type":"episode", "scope_id":"upscale:1"}
        record = _authoritative_upscale(module.PRODUCTION_LEDGER, key, "fp", "batch", {"provider":"v1"}, {"final":{"status":"pass", "evidence":{"score":1}}})
        module.PRODUCTION_LEDGER.confirm(key)
        claim = {"source_version":"enhanced", "items":[{"episode":1, "content_fingerprint":"fp", "audit_batch_id":"batch", "generation":record["generation"]}], "audit_results":[]}
        assert module._validated_review_export_authority(identity, claim, [1], audit_required=False)[1]["generation"] == record["generation"]
        with pytest.raises(ValueError):
            module._validated_review_export_authority(identity, {**claim, "items":[{**claim["items"][0], "generation":record["generation"] + 1}]}, [1], audit_required=False)


def test_cross_instance_generation_allocation_and_latest_commit_are_atomic():
    with TemporaryDirectory() as temporary:
        database = Path(temporary) / "ledger.sqlite"
        ledgers = [ProductionLedger(database), ProductionLedger(database)]
        key = {"tenant_id":"tenant", "user_id":"user", "project_id":"project", "stage":"review_export", "scope_type":"episode", "scope_id":"upscale:1"}
        barrier = threading.Barrier(2); generations = []; commits = []; errors = []
        def worker(index):
            generation = ledgers[index].reserve_upscale_generation(key)
            generations.append(generation); barrier.wait()
            try:
                commits.append(ledgers[index].commit_upscale_authority({
                    **key, "generation":generation, "content_fingerprint":f"fp-{generation}",
                    "audit_batch_id":f"batch-{generation}", "production_evidence":{"generation":generation},
                    "audit_evidence":{"final":{"status":"pass", "generation":generation}},
                }))
            except ProductionLedgerError as error:
                errors.append(str(error))
        threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        assert sorted(generations) == [1, 2]
        assert len(commits) == 1 and commits[0]["generation"] == 2
        assert len(errors) == 1 and "stale or unreserved" in errors[0]
        reloaded = ProductionLedger(database).list(key)[0]
        assert reloaded["generation"] == 2 and reloaded["content_fingerprint"] == "fp-2"


def test_public_scope_handlers_cannot_forge_upscale_authority_or_confirmation():
    module = load_backend()
    with TemporaryDirectory() as temporary:
        module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary) / "ledger.sqlite")
        module._reconcile_completed_production_stages = lambda *_args, **_kwargs: None
        key = {"tenant_id":"tenant", "user_id":"user", "project_id":"project", "stage":"review_export", "scope_type":"episode", "scope_id":"upscale:1"}
        original = _authoritative_upscale(module.PRODUCTION_LEDGER, key, "real-fp", "real-batch", {"provider":"real"}, {"final":{"status":"pass"}})
        confirmed = module.PRODUCTION_LEDGER.confirm(key)
        server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def post(path, payload):
            request = Request(f"http://127.0.0.1:{server.server_port}{path}", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        try:
            forged = {**key, "lifecycle":"failed", "content_fingerprint":"evil-fp", "audit_batch_id":"evil-batch", "generation":999, "confirmation":{"forged":True}, "production_evidence":{"evil":True}, "audit_evidence":{"evil":True}, "progress":{"completed":0, "total":1, "production_evidence":{"evil":True}}}
            status, single = post("/api/production/scopes", forged)
            assert status == 200
            status, bulk = post("/api/production/scopes/bulk", {"records":[forged], "replace_batch_scope_sets":True})
            assert status == 200
            for record in (single["record"], bulk["records"][0], module.PRODUCTION_LEDGER.list(key)[0]):
                assert record["content_fingerprint"] == "real-fp"
                assert record["audit_batch_id"] == "real-batch"
                assert record["generation"] == original["generation"]
                assert record["lifecycle"] == "completed"
                assert record["confirmation"] == confirmed["confirmation"]
                assert record["production_evidence"] == {"provider":"real"}
                assert record["audit_evidence"] == {"final":{"status":"pass"}}
            shell_key = {**key, "scope_id":"upscale:2"}
            _, shell = post("/api/production/scopes", {**shell_key, "lifecycle":"completed", "content_fingerprint":"fake", "audit_batch_id":"fake", "generation":1, "confirmation":{"fake":True}, "progress":{"completed":1, "total":1, "production_evidence":{"fake":True}}})
            assert shell["record"]["lifecycle"] == "idle"
            assert shell["record"]["generation"] == 0
            assert shell["record"]["content_fingerprint"] == ""
            assert shell["record"]["audit_batch_id"] == ""
            assert shell["record"]["confirmation"] is None
            assert shell["record"]["production_evidence"] is None
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_frontend_submits_upscale_once_through_server_stage_with_session_fence():
    source = APP.read_text(encoding="utf-8")
    block = source[source.index("function runUpscale"):source.index("async function confirmEnhancedEpisode")]
    public = block[:block.index("async function runUpscaleTransaction")]
    assert "async function runUpscale" not in public
    assert "return upscaleFlight" in public and "return flight" in public
    assert "upscaleFlightKey === flightKey" in public
    assert "upscaleFlight === flight" in public and "upscaleFlightEpoch === epoch" in public
    assert block.count("productionLedgerService.runStage") == 1
    for legacy in ("mediaService.upscale<", "mediaService.subtitleOcrAudit", "mediaService.faceAudit", "mediaService.finalAudit"):
        assert legacy not in block
    assert 'stage:"review_export", operation:"upscale"' in block
    assert 'source_version:"base"' in block
    assert 'target:{ width:1080, height:1920, fps:30, mode:"quality" }' in block
    assert "isCurrentProjectSession(project.id, session)" in block
    assert "controller.signal" in block
    assert 'upscaleStatus.value = "failed"' in block
    assert 'upscaleStatus.value = "skipped"; upscaleError.value = `增强版失败' not in block
    assert "if (!isCurrentUpscale()) return;" in block
    stop = block[block.index("async function stopUpscale"):]
    assert "upscaleFlightEpoch += 1" in stop and "upscaleFlight = undefined" in stop
    assert 'stopStage({ ...productionTaskContext(project), stage:"review_export" })' in stop
    confirm = source[source.index("async function confirmEnhancedEpisode"):source.index("function importEnhancedEpisode")]
    assert "productionLedgerService.confirm" in confirm and "upscale:${item.episode}" in confirm
    sync = source[source.index("async function syncProductionLedger"):source.index("watch([outlinePlan")]
    upscale_projection = sync[sync.index("for (const item of enhancedEpisodes.value)"):sync.index("for (const item of exportFiles.value)")]
    assert "content_fingerprint" not in upscale_projection
    assert "audit_batch_id" not in upscale_projection
    assert "production_evidence" not in upscale_projection
    assert "audit_evidence" not in upscale_projection
    export = source[source.index("function createExports"):source.index("async function downloadExportBatch")]
    assert 'audit_batch_id:exportSourceVersion.value === "enhanced"' in export
    assert 'generation:exportSourceVersion.value === "enhanced"' in export
