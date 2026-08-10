from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import contextmanager
import importlib.util
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import unittest

from ai_agent_core import ResourceScheduler, ResourceSchedulerError, WorkerRegistry, WorkerSnapshot, WorkloadRouter, WorkloadRoutingError
from short_drama_workflows.production_ledger import ProductionLedger
from short_drama_workflows.production_orchestrator import ProductionOrchestrator
from short_drama_workflows.story_bible import StoryBible, StoryBibleError
from short_drama_workflows.production_ledger import CANONICAL_STAGES, canonical_stage
from ai_agent_queue import DurableTaskRepository, TaskLeaseError, TaskLeaseRepository
from ai_agent_adapters import ProductionCapabilityError, ProductionCapabilityRegistry, production_capability_registry, ProductionExtensionError, ProductionExtensionRegistry, production_extension_registry
from ai_agent_core import atomic_write_json


class ProductionControlTests(unittest.TestCase):
    def test_langgraph_is_the_only_pipeline_progression_authority(self):
        root = Path(__file__).resolve().parents[2]
        pipeline = (root / "plugins/builtin/short_drama/workflows/pipeline.py").read_text(encoding="utf-8")
        self.assertNotIn("for index in range(checkpoint.next_index", pipeline)
        self.assertNotIn("NODES[checkpoint.next_index]", pipeline)
        self.assertNotIn("else stored.status", pipeline)
        self.assertIn("state = self.orchestrator.state(self._identity(checkpoint))", pipeline)
        self.assertIn('node = str(state.get("next_stage") or "requirements")', pipeline)

    def test_result_commit_rechecks_distributed_lease_and_frontend_only_submits_stage_commands(self):
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        frontend = (root / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
        self.assertIn("task ownership lease lost before result commit", backend)
        self.assertIn("def _run_server_production_stage", backend)
        for name in ("generateOutline", "generateScripts", "generateStoryboards", "generateShotImages", "generateShotVideos"):
            start = frontend.index(f"async function {name}(")
            end = frontend.find("\nasync function ", start + 1)
            section = frontend[start:end if end >= 0 else len(frontend)]
            self.assertIn("productionLedgerService.runStage", section)
        self.assertNotIn("legacyClientOutlineOrchestration", frontend)
        self.assertNotIn("legacyClientScriptOrchestration", frontend)
        self.assertNotIn("legacyClientStoryboardOrchestration", frontend)
        self.assertNotIn("legacyClientShotImageOrchestration", frontend)
        self.assertNotIn("legacyClientShotVideoOrchestration", frontend)

    def test_scope_confirmation_validates_graph_before_mutating_ledger(self):
        with TemporaryDirectory() as temporary:
            root = Path(__file__).resolve().parents[2]
            spec = importlib.util.spec_from_file_location("compat_atomic_confirmation_test", root / "plugins/builtin/short_drama/backend/compat_server.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.PRODUCTION_LEDGER = ProductionLedger(Path(temporary) / "ledger.sqlite")
            brain = ProductionOrchestrator(Path(temporary) / "graph.sqlite"); module.PRODUCTION_ORCHESTRATOR = brain
            payload = {"tenant_id":"t", "user_id":"u", "project_id":"p", "stage":"outline", "scope_type":"project", "scope_id":"all", "lifecycle":"pending_confirmation", "content_fingerprint":"v1", "audit_batch_id":"a1"}
            module.PRODUCTION_LEDGER.upsert(payload)
            with self.assertRaisesRegex(ValueError, "previous stage"):
                module._confirm_production_scope(payload)
            record = module.PRODUCTION_LEDGER.list(payload)[0]
            self.assertEqual(record["lifecycle"], "pending_confirmation"); self.assertIsNone(record["confirmation"])
            self.assertEqual(brain.state(payload)["stages"], {})

    def test_remote_worker_dispatch_forwards_request_without_routing_loop(self):
        received = {}
        class Echo(BaseHTTPRequestHandler):
            def do_POST(self):
                received["dispatched"] = self.headers.get("X-Production-Dispatched")
                received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                payload = json.dumps({"accepted":True}).encode(); self.send_response(202); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
            def log_message(self, *_): return
        server = ThreadingHTTPServer(("127.0.0.1", 0), Echo); thread = threading.Thread(target=server.serve_forever); thread.start()
        try:
            root = Path(__file__).resolve().parents[2]
            spec = importlib.util.spec_from_file_location("compat_remote_dispatch_test", root / "plugins/builtin/short_drama/backend/compat_server.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.WORKLOAD_ROUTER = WorkloadRouter(); module.WORKER_SCOPE = "scope"; module.WORKER_ID = "local"; module._heartbeat_local_worker = lambda: None
            module.WORKLOAD_ROUTER.heartbeat(WorkerSnapshot("remote", "scope", ("text",), 1, 0, 0, 100, time.time(), endpoint=f"http://127.0.0.1:{server.server_port}"))
            self.assertEqual(module._forward_production_request("/api/outline/plan", {"project_id":"p"}, False), (202, {"accepted":True, "_dispatch":{"worker_id":"remote", "endpoint":f"http://127.0.0.1:{server.server_port}"}}))
            self.assertEqual(received, {"dispatched":"1", "body":{"project_id":"p"}})
            self.assertIsNone(module._forward_production_request("/api/outline/plan", {}, True))
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_remote_gateway_failure_is_normalized_to_service_unavailable(self):
        class FailedGateway(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.dumps({"error":"bad_gateway"}).encode(); self.send_response(502); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
            def log_message(self, *_): return
        server = ThreadingHTTPServer(("127.0.0.1", 0), FailedGateway); thread = threading.Thread(target=server.serve_forever); thread.start()
        try:
            root = Path(__file__).resolve().parents[2]
            spec = importlib.util.spec_from_file_location("compat_remote_failure_test", root / "plugins/builtin/short_drama/backend/compat_server.py")
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.WORKLOAD_ROUTER = WorkloadRouter(); module.WORKER_SCOPE = "scope"; module.WORKER_ID = "local"; module._heartbeat_local_worker = lambda: None
            endpoint = f"http://127.0.0.1:{server.server_port}"
            module.WORKLOAD_ROUTER.heartbeat(WorkerSnapshot("remote", "scope", ("text",), 1, 0, 0, 100, time.time(), endpoint=endpoint))
            self.assertEqual(module._forward_production_request("/api/outline/plan", {}, False), (503, {"error":"workload_dispatch_failed", "message":"bad_gateway", "_dispatch":{"worker_id":"remote", "endpoint":endpoint}}))
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_task_lease_fences_expired_owner_and_late_results(self):
        with TemporaryDirectory() as temporary:
            leases = TaskLeaseRepository(Path(temporary) / "leases.sqlite")
            first = leases.acquire("job", "worker-a", ttl=10, now=100)
            with self.assertRaises(TaskLeaseError): leases.acquire("job", "worker-b", ttl=10, now=105)
            second = leases.acquire("job", "worker-b", ttl=10, now=111)
            self.assertGreater(second["generation"], first["generation"])
            self.assertFalse(leases.renew("job", "worker-a", int(first["generation"]), now=112))
            self.assertFalse(leases.release("job", "worker-a", int(first["generation"])))
            self.assertTrue(leases.owns("job", "worker-b", int(second["generation"]), now=112))

    def test_task_lease_allows_only_one_concurrent_executor(self):
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "leases.sqlite"; barrier = threading.Barrier(3); winners = []; conflicts = []
            def acquire(owner):
                repository = TaskLeaseRepository(database); barrier.wait()
                try: winners.append(repository.acquire("same-job", owner, ttl=10, now=100)["owner_id"])
                except TaskLeaseError: conflicts.append(owner)
            threads = [threading.Thread(target=acquire, args=(owner,)) for owner in ("worker-a:one", "worker-a:two")]
            for thread in threads: thread.start()
            barrier.wait()
            for thread in threads: thread.join()
            self.assertEqual(len(winners), 1); self.assertEqual(len(conflicts), 1)

    def test_workload_router_balances_by_resource_capacity_and_backpressure(self):
        router = WorkloadRouter(heartbeat_timeout=10, max_queue_depth=2)
        router.heartbeat(WorkerSnapshot("busy", "scope", ("image",), 2, 1, 1, 80, 100))
        router.heartbeat(WorkerSnapshot("idle", "scope", ("image", "video"), 2, 0, 0, 60, 100))
        self.assertEqual(router.route("image", estimated_memory=50, service_scope="scope", now=105).worker_id, "idle")
        with self.assertRaises(WorkloadRoutingError): router.route("video", estimated_memory=70, service_scope="scope", now=105)
        with self.assertRaises(WorkloadRoutingError): router.route("image", service_scope="scope", now=120)

    def test_worker_discovery_is_shared_between_process_instances(self):
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "workers.sqlite"; first = WorkerRegistry(database); second = WorkerRegistry(database)
            worker = WorkerSnapshot("remote", "scope", ("image",), 1, 0, 0, 100, 100, endpoint="http://127.0.0.1:8790")
            first.heartbeat(worker)
            self.assertEqual(second.list(service_scope="scope", heartbeat_timeout=10, now=105), [worker])
            self.assertEqual(second.list(service_scope="scope", heartbeat_timeout=10, now=120), [])

    def test_composition_requires_one_confirmed_media_package_per_shot(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("compat_media_package_test", root / "plugins/builtin/short_drama/backend/compat_server.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        def record(stage, fingerprint, batch):
            return {"stage":stage, "scope_type":"shot", "scope_id":"1", "lifecycle":"completed", "content_fingerprint":fingerprint, "audit_batch_id":batch, "confirmation":{"content_fingerprint":fingerprint, "audit_batch_id":batch}}
        valid = [record("video", "v", "package-1"), record("audio", "a", "package-1"), record("subtitle", "s", "package-1")]
        self.assertEqual(module._validated_composition_media_packages(valid), {"1":"package-1"})
        with self.assertRaisesRegex(ValueError, "media package mismatch"):
            module._validated_composition_media_packages([record("video", "v", "video-batch"), record("audio", "a", "audio-batch"), record("subtitle", "s", "subtitle-batch")])
        forged = valid.copy(); forged[1] = {**forged[1], "content_fingerprint":"changed"}
        with self.assertRaisesRegex(ValueError, "confirmed video/audio/subtitle"):
            module._validated_composition_media_packages(forged)

    def test_three_or_more_json_writers_use_one_atomic_primitive(self):
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / "state.json"
            atomic_write_json(target, {"ok": True})
            self.assertEqual(target.read_text(encoding="utf-8"), '{\n  "ok": true\n}')
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(backend.count("atomic_write_json("), 8)
        self.assertNotIn('json.dump(store, stream, ensure_ascii=False, indent=2)', backend)

    def test_production_capabilities_are_replaceable_and_disableable(self):
        self.assertIs(production_capability_registry(), production_capability_registry())
        registry = ProductionCapabilityRegistry()
        registry.register("image.baseline", "flux", lambda **inputs: {"engine": "flux", **inputs})
        self.assertTrue(registry.has("image.baseline"))
        self.assertEqual(registry.invoke("image.baseline", prompt="仙侠")["engine"], "flux")
        registry.register("image.baseline", "klein", lambda **inputs: {"engine": "klein", **inputs}, replace=True)
        self.assertEqual(registry.invoke("image.baseline", prompt="仙侠")["engine"], "klein")
        registry.enable("image.baseline", False)
        with self.assertRaises(ProductionCapabilityError):
            registry.invoke("image.baseline", prompt="仙侠")
        self.assertTrue(registry.unregister("image.baseline"))
        registry.register("audit.video", "inspector", lambda **_: {"status":"pass", "evidence":{"score":0.9}})
        self.assertEqual(registry.get("audit.video").provider_id, "inspector")

    def test_production_capabilities_support_multiple_providers_health_and_safe_fallback(self):
        registry = ProductionCapabilityRegistry()
        registry.register("video.shot", "local-a", lambda **_: {"provider":"local-a"}, priority=10)
        registry.register("video.shot", "local-b", lambda **_: {"provider":"local-b"}, priority=10)
        registry.register("video.shot", "remote-c", lambda **_: {"provider":"remote-c"}, priority=20)
        self.assertEqual([registry.invoke("video.shot")["provider"] for _ in range(4)], ["local-a", "local-b", "local-a", "local-b"])
        self.assertEqual(registry.invoke("video.shot", provider_id="remote-c")["provider"], "remote-c")
        selected, selected_result = registry.invoke_with_provider("video.shot")
        self.assertEqual(selected.provider_id, selected_result["provider"])
        registry.health("video.shot", "local-a", False)
        self.assertFalse(registry.get("video.shot", "local-a").healthy)
        self.assertEqual(registry.invoke("video.shot")["provider"], "local-b")
        registry.register("image.generate", "broken", lambda **_: (_ for _ in ()).throw(RuntimeError("down")), priority=1)
        registry.register("image.generate", "backup", lambda **_: {"provider":"backup"}, priority=2)
        with self.assertRaisesRegex(RuntimeError, "down"):
            registry.invoke("image.generate")
        self.assertEqual(registry.invoke("image.generate", allow_fallback=True)["provider"], "backup")
        registry.enable("video.shot", False, provider_id="local-b")
        self.assertEqual(registry.invoke("video.shot")["provider"], "remote-c")
        self.assertTrue(registry.unregister("video.shot", "remote-c"))
        with self.assertRaisesRegex(ProductionCapabilityError, "no healthy enabled provider"):
            registry.invoke("video.shot")

    def test_builtin_capability_refresh_does_not_remove_plugin_provider(self):
        registry = ProductionCapabilityRegistry()
        registry.register("image.generate", "plugin", lambda **_: {"provider":"plugin"}, priority=5, metadata={"builtin":False})
        registry.register("image.generate", "builtin", lambda **_: {"provider":"builtin-v1"}, priority=100, metadata={"builtin":True})
        registry.register("image.generate", "builtin", lambda **_: {"provider":"builtin-v2"}, priority=100, metadata={"builtin":True}, replace_provider=True)
        self.assertTrue(registry.has("image.generate", "plugin"))
        self.assertEqual(registry.invoke("image.generate")["provider"], "plugin")
        self.assertEqual(registry.invoke("image.generate", provider_id="builtin")["provider"], "builtin-v2")

    def test_production_infrastructure_is_replaceable_and_disableable(self):
        self.assertIs(production_extension_registry(), production_extension_registry())
        registry = ProductionExtensionRegistry()
        registry.register("storage.task_repository", "sqlite", lambda **values: {"backend":"sqlite", **values})
        self.assertEqual(registry.create("storage.task_repository", database="tasks.db")["database"], "tasks.db")
        registry.register("storage.task_repository", "postgres", lambda **values: {"backend":"postgres", **values}, replace=True)
        self.assertEqual(registry.get("storage.task_repository").provider_id, "postgres")
        registry.enable("storage.task_repository", False)
        with self.assertRaises(ProductionExtensionError):
            registry.create("storage.task_repository", database="tasks.db")
        self.assertTrue(registry.unregister("storage.task_repository"))

    def test_production_extensions_support_install_activate_rollback_and_provider_uninstall(self):
        registry = ProductionExtensionRegistry()
        registry.register("storage.task_repository", "sqlite", lambda **_: {"provider":"sqlite"}, metadata={"hot_swappable":False})
        registry.register("storage.task_repository", "postgres", lambda **_: {"provider":"postgres"}, metadata={"hot_swappable":False})
        self.assertEqual(registry.create("storage.task_repository")["provider"], "sqlite")
        installed = registry.list()
        self.assertEqual([(item.provider_id, item.active) for item in installed], [("sqlite", True), ("postgres", False)])
        registry.activate("storage.task_repository", "postgres")
        self.assertEqual(registry.create("storage.task_repository")["provider"], "postgres")
        self.assertEqual(registry.create("storage.task_repository", provider_id="sqlite")["provider"], "sqlite")
        registry.activate("storage.task_repository", "sqlite")
        self.assertEqual(registry.create("storage.task_repository")["provider"], "sqlite")
        self.assertTrue(registry.unregister("storage.task_repository", "sqlite"))
        self.assertEqual(registry.create("storage.task_repository")["provider"], "postgres")

    def test_builtin_extension_refresh_preserves_plugin_and_active_binding(self):
        registry = ProductionExtensionRegistry()
        registry.register("routing.workload", "builtin", lambda **_: {"version":1}, metadata={"builtin":True})
        registry.register("routing.workload", "plugin", lambda **_: {"version":"plugin"}, metadata={"builtin":False})
        registry.activate("routing.workload", "plugin")
        registry.register("routing.workload", "builtin", lambda **_: {"version":2}, metadata={"builtin":True}, replace_provider=True)
        self.assertEqual(registry.get("routing.workload").provider_id, "plugin")
        self.assertEqual(registry.create("routing.workload")["version"], "plugin")
        self.assertEqual(registry.create("routing.workload", provider_id="builtin")["version"], 2)
        registry.enable("routing.workload", False, provider_id="plugin")
        with self.assertRaisesRegex(ProductionExtensionError, "no active provider"):
            registry.create("routing.workload")
        registry.activate("routing.workload", "builtin")
        self.assertEqual(registry.create("routing.workload")["version"], 2)

    def test_rejected_extension_replacement_is_atomic(self):
        registry = ProductionExtensionRegistry()
        registry.register("storage.task_repository", "stable", lambda **_: {"provider":"stable"})
        with self.assertRaisesRegex(ProductionExtensionError, "disabled extension provider cannot be activated"):
            registry.register(
                "storage.task_repository",
                "invalid",
                lambda **_: {"provider":"invalid"},
                enabled=False,
                replace=True,
            )
        self.assertEqual(registry.create("storage.task_repository")["provider"], "stable")
        self.assertEqual(
            [(item.provider_id, item.active) for item in registry.list()],
            [("stable", True)],
        )

    def test_runtime_kernel_has_pluggable_infrastructure_boundaries(self):
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        for point in ("resource.scheduler", "storage.production_ledger", "storage.story_bible", "storage.task_repository", "checkpoint.langgraph", "routing.workload", "storage.task_lease", "discovery.workers"):
            self.assertIn(f'"{point}"', backend)
        self.assertIn('"extensions"', backend)
        self.assertIn('parsed.path == "/api/production/workers"', backend)
        self.assertIn("ThreadingHTTPServer((SERVICE_HOST, SERVICE_PORT), Handler)", backend)
        self.assertIn('"X-Production-Dispatched":"1"', backend)
        self.assertIn("_forward_production_request(parsed.path, body", backend)

    def test_outline_to_export_contract_has_no_stage_gap(self):
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        self.assertIn('"/api/audio/tts":"video"', backend)
        self.assertIn('"/api/videos/merge":"composition"', backend)
        self.assertIn('"/api/videos/audit":"review_export"', backend)
        self.assertIn('if (shotVideoStatus.value === "confirmed") await syncProductionLedger(project)', (root / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8"))

    def test_all_eleven_stages_advance_only_after_confirmation(self):
        with TemporaryDirectory() as temporary:
            brain = ProductionOrchestrator(Path(temporary) / "kernel.sqlite")
            identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
            for index, stage in enumerate(CANONICAL_STAGES):
                brain.register_stage(stage, lambda inputs, current=stage: {"stage":current}, provider_id=f"provider-{stage}")
                result = brain.execute(identity, stage, {})
                self.assertEqual(result["status"], "waiting_human")
                self.assertEqual(result["current_stage"], stage)
                confirmed = brain.report(identity, stage, "completed", confirmation={"confirmed_at":"test"})
                self.assertEqual(confirmed["next_stage"], CANONICAL_STAGES[index + 1] if index + 1 < len(CANONICAL_STAGES) else "")
            self.assertEqual(brain.state(identity)["status"], "completed")

    def test_completed_stage_cannot_be_forged_or_skip_predecessors(self):
        with TemporaryDirectory() as temporary:
            brain = ProductionOrchestrator(Path(temporary) / "kernel.sqlite")
            identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
            with self.assertRaisesRegex(ValueError, "previous stage"):
                brain.report(identity, "subtitle", "completed", confirmation={"confirmed_at":"fake"})
            brain.report(identity, "requirements", "completed", trusted=True)
            with self.assertRaisesRegex(ValueError, "durable confirmation"):
                brain.report(identity, "outline", "completed", evidence={})
            with self.assertRaisesRegex(ValueError, "previous stage"):
                brain.begin(identity, "composition")

    def test_image_production_routes_use_capability_registry(self):
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        handler = backend[backend.index("class Handler") :]
        for capability in (
            "image.generate",
            "image.baseline.klein9b",
            "image.variant.qwen",
            "image.variant.ipadapter",
            "image.shot.multireference",
        ):
            self.assertIn(f'"{capability}"', handler)
        self.assertIn('("image.baseline.schnell", "comfy-flux1-schnell-q8", _generate_flux1_schnell_baseline)', backend)
        for capability in ("asset.3d", "pose.extract", "audio.bgm"):
            self.assertIn(f'_invoke_production_capability("{capability}"', backend)
        self.assertIn('args=("video.shot",)', backend)
        self.assertIn('_invoke_production_capability("audio.tts", body=body)', backend)
        self.assertIn('_invoke_production_capability(capability, body=body)', backend)
        self.assertIn('("text.generate.json", "ollama-qwen3-vl-32b", _ollama_json_local)', backend)
        self.assertIn('("text.narrative.repair", "ollama-qwen25-72b", _narrative_repair)', backend)
        self.assertIn('"text.generate.json", prompt=prompt', backend)
        self.assertIn('_invoke_production_capability("audit.narrative", body=body)', backend)
        for implementation in (
            "_generate_flux1_schnell_baseline(",
            "_generate_klein9b_asset_baseline(",
            "_generate_qwen_character_variant(",
            "_generate_ipadapter_image(",
            "_generate_multireference_shot(",
        ):
            self.assertNotIn(implementation, handler)

    def test_missing_real_auditors_never_return_fake_pass(self):
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        self.assertIn('"error": "audit_provider_not_installed"', backend)
        self.assertIn('_optional_audit("audit.video.lipsync", body)', backend)
        self.assertIn('audit result lacks real evidence', backend)
        self.assertNotIn('"matched":True, "speech_start"', backend)
        self.assertNotIn('"model": "CampPlus" if parsed.path.endswith("speaker-audit")', backend)
        frontend = (root / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
        self.assertNotIn('? { ...audit, status:"pass", issues:[] }', frontend)
        self.assertNotIn('content_compliance_status:"pass"', frontend)
        self.assertIn('body.get("content_compliance_status") != "pass"', backend)

    def test_runtime_tasks_and_capabilities_have_authoritative_read_apis(self):
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        self.assertIn('parsed.path == "/api/tasks/runtime"', backend)
        self.assertIn('parsed.path == "/api/production/capabilities"', backend)
        self.assertIn('nonterminal_only=query.get("nonterminal_only"', backend)
        frontend = (root / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
        task_service = (root / "plugins/builtin/short_drama/frontend/services/task.service.ts").read_text(encoding="utf-8")
        self.assertIn("taskService.runtime(taskIdentity(project))", frontend)
        self.assertIn("任务 UUID {{ task.job_id }}", frontend)
        self.assertIn("/api/tasks/runtime?", task_service)
        self.assertIn("productionLedgerService.capabilities()", frontend)
        self.assertIn("可插拔生产能力", frontend)

    def test_formal_production_endpoints_enter_langgraph_gate(self):
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        for endpoint, stage in (("/api/outline/plan","outline"),("/api/script/episode","script"),("/api/characters/generate","assets"),("/api/shots/generate","image"),("/api/videos/generate","video"),("/api/audio/tts","video"),("/api/videos/merge","composition"),("/api/videos/audit","review_export")):
            self.assertIn(f'"{endpoint}":"{stage}"', backend)
        self.assertIn("_begin_production_request(body, production_stage)", backend)
        self.assertIn('"completed":"pending_confirmation"', backend)
        self.assertIn("_production_orchestrator().report(", backend)

    def test_durable_repository_unifies_text_image_and_video_jobs(self):
        with TemporaryDirectory() as temporary:
            repository = DurableTaskRepository(Path(temporary) / "tasks.sqlite")
            for task_class in ("text", "image", "video"):
                repository.upsert(
                    f"{task_class}-job",
                    task_class,
                    {
                        "tenant_id": "tenant",
                        "user_id": "user",
                        "project_id": "project",
                        "stage": task_class,
                        "status": "generating",
                        "heartbeat_at": "2026-08-10T00:00:00+00:00",
                    },
                )
            tasks = repository.list(
                tenant_id="tenant",
                user_id="user",
                project_id="project",
                nonterminal_only=True,
            )
            self.assertEqual({item["task_class"] for item in tasks}, {"text", "image", "video"})
            self.assertTrue(all(item["payload"]["status"] == "generating" for item in tasks))
            self.assertEqual(len(repository.list(task_class="image")), 1)

    def test_authoritative_task_store_commits_before_json_projection(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("compat_task_commit_order_test", root / "plugins/builtin/short_drama/backend/compat_server.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            module.TEXT_JOBS_FILE = directory / "text-jobs.json"
            module.TASK_REPOSITORIES = {}
            module.SERVICE_SHUTTING_DOWN.set()
            old = {"jobs":{"job":{"job_id":"job", "status":"queued", "project_id":"project"}}}
            atomic_write_json(module.TEXT_JOBS_FILE, old)
            original_writer = module.atomic_write_json
            module.atomic_write_json = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("projection failed"))
            latest = {"jobs":{"job":{"job_id":"job", "status":"completed", "project_id":"project"}}}
            with self.assertRaisesRegex(OSError, "projection failed"):
                module._save_text_jobs(latest)
            module.atomic_write_json = original_writer
            self.assertEqual(module._task_repository(module.TEXT_JOBS_FILE).get("job")["payload"]["status"], "completed")
            self.assertEqual(module._load_text_jobs()["jobs"]["job"]["status"], "completed")
            original_sync = module._sync_durable_tasks
            module._sync_durable_tasks = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("authority failed"))
            with self.assertRaisesRegex(OSError, "authority failed"):
                module._save_text_jobs({"jobs":{"job":{"job_id":"job", "status":"failed"}}})
            module._sync_durable_tasks = original_sync
            self.assertEqual(json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"]["job"]["status"], "queued")
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        for task_class, target in (("text", "TEXT_JOBS_FILE"), ("image", "IMAGE_JOBS_FILE"), ("video", "VIDEO_JOBS_FILE")):
            start = backend.index(f"def _save_{task_class}_jobs")
            end = backend.index("\ndef ", start + 5)
            section = backend[start:end]
            self.assertLess(section.index(f'_sync_durable_tasks("{task_class}", {target}, store)'), section.index("atomic_write_json("))

    def test_task_batch_is_atomic_and_graph_projection_is_replayable(self):
        with TemporaryDirectory() as temporary:
            repository = DurableTaskRepository(Path(temporary) / "tasks.sqlite")
            original_execute = repository._execute_upsert
            calls = 0
            def fail_second(connection, values):
                nonlocal calls
                calls += 1
                if calls == 2: raise OSError("second task failed")
                return original_execute(connection, values)
            repository._execute_upsert = fail_second
            with self.assertRaisesRegex(OSError, "second task failed"):
                repository.upsert_many("text", {"one":{"status":"queued"}, "two":{"status":"queued"}}, enqueue_projection=True)
            self.assertEqual(repository.list(task_class="text"), [])
            self.assertEqual(repository.pending_projections(task_class="text"), [])

        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("compat_projection_replay_test", root / "plugins/builtin/short_drama/backend/compat_server.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with TemporaryDirectory() as temporary:
            module.OUTPUT_ROOT = Path(temporary)
            cache = module.OUTPUT_ROOT / "narrative-cache"; cache.mkdir(parents=True)
            module.TEXT_JOBS_FILE = cache / "text-jobs.json"; module.TASK_REPOSITORIES = {}
            module.SERVICE_SHUTTING_DOWN.clear()
            class FailedBrain:
                def report(self, *_args, **_kwargs): raise OSError("graph unavailable")
            module.PRODUCTION_ORCHESTRATOR = FailedBrain()
            completed = {"jobs":{"done":{"job_id":"done", "tenant_id":"t", "user_id":"u", "project_id":"p", "stage":"outline", "status":"completed"}}}
            module._save_text_jobs(completed)
            self.assertEqual(module._load_text_jobs()["jobs"]["done"]["status"], "completed")
            self.assertEqual(len(module._task_repository(module.TEXT_JOBS_FILE).pending_projections(task_class="text")), 1)
            reports = []
            class HealthyBrain:
                def report(self, identity, stage, lifecycle, **evidence): reports.append((identity, stage, lifecycle, evidence))
            module.PRODUCTION_ORCHESTRATOR = HealthyBrain()
            self.assertEqual(module._replay_durable_task_projections(), 1)
            self.assertEqual(reports[0][1:3], ("outline", "pending_confirmation"))
            self.assertEqual(module._task_repository(module.TEXT_JOBS_FILE).pending_projections(task_class="text"), [])
            self.assertEqual(module._load_text_jobs()["jobs"]["done"]["status"], "completed")
            repository = module._task_repository(module.TEXT_JOBS_FILE)
            repository.upsert_many("text", {"done":completed["jobs"]["done"]}, enqueue_projection=True)
            self.assertEqual(repository.pending_projections(task_class="text"), [])

    def test_stale_projection_cannot_ack_or_overwrite_newer_event(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("compat_projection_fence_test", root / "plugins/builtin/short_drama/backend/compat_server.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with TemporaryDirectory() as temporary:
            module.OUTPUT_ROOT = Path(temporary); cache = module.OUTPUT_ROOT / "narrative-cache"; cache.mkdir(parents=True)
            module.TEXT_JOBS_FILE = cache / "text-jobs.json"; module.TASK_REPOSITORIES = {}; module.SERVICE_SHUTTING_DOWN.clear()
            real_brain = ProductionOrchestrator(cache / "graph.sqlite")
            old_started = threading.Event(); release_old = threading.Event()
            class BlockingBrain:
                def report(self, identity, stage, lifecycle, **evidence):
                    if int(evidence.get("projection_revision") or 0) == 1:
                        old_started.set(); release_old.wait(2)
                    return real_brain.report(identity, stage, lifecycle, **evidence)
            module.PRODUCTION_ORCHESTRATOR = BlockingBrain()
            repository = module._task_repository(module.TEXT_JOBS_FILE)
            base = {"job_id":"job", "tenant_id":"t", "user_id":"u", "project_id":"p", "stage":"outline", "status":"queued"}
            repository.upsert_many("text", {"job":base}, enqueue_projection=True)
            old = threading.Thread(target=module._drain_durable_task_projections, args=("text", module.TEXT_JOBS_FILE)); old.start()
            self.assertTrue(old_started.wait(1))
            repository.upsert_many("text", {"job":{**base, "status":"completed"}}, enqueue_projection=True)
            self.assertEqual(repository.pending_projections(task_class="text")[0]["event_revision"], 2)
            second_repository = DurableTaskRepository(repository.database)
            module.TASK_REPOSITORIES = {repository.database:second_repository}
            second_brain = ProductionOrchestrator(cache / "graph.sqlite")
            module.PRODUCTION_ORCHESTRATOR = second_brain
            self.assertEqual(module._drain_durable_task_projections("text", module.TEXT_JOBS_FILE), 0)
            release_old.set(); old.join(2)
            self.assertEqual(second_repository.pending_projections(task_class="text")[0]["event_revision"], 2)
            self.assertEqual(module._drain_durable_task_projections("text", module.TEXT_JOBS_FILE), 1)
            self.assertEqual(second_repository.pending_projections(task_class="text"), [])
            state = second_brain.state({"tenant_id":"t", "user_id":"u", "project_id":"p"})
            self.assertEqual(state["stages"]["outline"], "pending_confirmation")
            self.assertEqual(state["projection_revisions"]["outline"], 2)

    def test_lost_projection_lease_requeues_authoritative_state(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("compat_projection_lost_lease_test", root / "plugins/builtin/short_drama/backend/compat_server.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with TemporaryDirectory() as temporary:
            module.OUTPUT_ROOT = Path(temporary); cache = module.OUTPUT_ROOT / "narrative-cache"; cache.mkdir(parents=True)
            module.TEXT_JOBS_FILE = cache / "text-jobs.json"; module.TASK_REPOSITORIES = {}; module.SERVICE_SHUTTING_DOWN.clear()
            brain = ProductionOrchestrator(cache / "graph.sqlite")
            old_started = threading.Event(); release_old = threading.Event()
            class BlockingBrain:
                def report(self, identity, stage, lifecycle, **evidence):
                    if int(evidence.get("projection_revision") or 0) == 1:
                        old_started.set(); release_old.wait(2)
                    return brain.report(identity, stage, lifecycle, **evidence)
            module.PRODUCTION_ORCHESTRATOR = BlockingBrain()
            repository = module._task_repository(module.TEXT_JOBS_FILE)
            base = {"job_id":"job", "tenant_id":"t", "user_id":"u", "project_id":"p", "stage":"outline", "status":"queued"}
            repository.upsert_many("text", {"job":base}, enqueue_projection=True)
            old = threading.Thread(target=module._drain_durable_task_projections, args=("text", module.TEXT_JOBS_FILE)); old.start()
            self.assertTrue(old_started.wait(1))
            repository.upsert_many("text", {"job":{**base, "status":"completed"}}, enqueue_projection=True)
            # Simulate expiry/takeover while the old external graph commit is blocked.
            with repository._connection() as connection:
                connection.execute("UPDATE task_projection_locks SET owner_id=?,expires_at=?", ("new-owner", time.time() + 30))
            brain.report({"tenant_id":"t", "user_id":"u", "project_id":"p"}, "outline", "pending_confirmation", projection_revision=2)
            repository.acknowledge_projections([("job", 2)])
            release_old.set(); old.join(2)
            pending = repository.pending_projections(task_class="text")
            self.assertEqual(len(pending), 1)
            self.assertGreater(pending[0]["event_revision"], 2)
            with repository._connection() as connection:
                connection.execute("DELETE FROM task_projection_locks WHERE scope_key=?", ("t:u:p:outline",))
            self.assertEqual(module._drain_durable_task_projections("text", module.TEXT_JOBS_FILE), 1)
            state = brain.state({"tenant_id":"t", "user_id":"u", "project_id":"p"})
            self.assertEqual(state["stages"]["outline"], "pending_confirmation")
            self.assertGreater(state["projection_revisions"]["outline"], 2)

    def test_projection_lock_concurrent_acquire_has_one_owner(self):
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "tasks.sqlite"
            repositories = (DurableTaskRepository(database), DurableTaskRepository(database))
            barrier = threading.Barrier(2); release = threading.Event(); outcomes = []
            def acquire(repository):
                barrier.wait()
                with repository.projection_lock("t:u:p:outline", ttl=5) as lease:
                    outcomes.append(bool(lease))
                    if lease: release.wait(1)
            threads = [threading.Thread(target=acquire, args=(repository,)) for repository in repositories]
            for thread in threads: thread.start()
            time.sleep(.1); release.set()
            for thread in threads: thread.join(2)
            self.assertEqual(sorted(outcomes), [False, True])

    def test_projection_lock_release_busy_does_not_escape(self):
        with TemporaryDirectory() as temporary:
            repository = DurableTaskRepository(Path(temporary) / "tasks.sqlite")
            original_connection = repository._connection
            entered = False
            @contextmanager
            def busy_on_release():
                nonlocal entered
                if entered:
                    raise sqlite3.OperationalError("database is locked")
                entered = True
                with original_connection() as connection:
                    yield connection
            with repository.projection_lock("t:u:p:outline", ttl=5) as lease:
                self.assertTrue(lease.owns())
                repository._connection = busy_on_release
            self.assertTrue(entered)

    def test_projection_replay_store_failure_does_not_stop_other_stores(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("compat_projection_resilient_replay_test", root / "plugins/builtin/short_drama/backend/compat_server.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        calls = []
        module.TEXT_JOBS_FILE = Path("text.json"); module.IMAGE_JOBS_FILE = Path("image.json"); module.VIDEO_JOBS_FILE = Path("video.json")
        def drain(task_class, _job_file):
            calls.append(task_class)
            if task_class == "text":
                raise sqlite3.OperationalError("database is locked")
            return 1
        module._drain_durable_task_projections = drain
        self.assertEqual(module._replay_durable_task_projections(), 2)
        self.assertEqual(calls, ["text", "image", "video"])

    def test_waiting_memory_is_preserved_in_tasks_and_projected_as_graph_queued(self):
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        self.assertIn('"waiting_memory":"queued"', backend)
        with TemporaryDirectory() as temporary:
            repository = DurableTaskRepository(Path(temporary) / "tasks.sqlite")
            repository.upsert("video-wait", "video", {
                "tenant_id":"tenant", "user_id":"user", "project_id":"project",
                "stage":"queued", "status":"waiting_memory", "request":{"project_id":"project"},
            })
            record = repository.get("video-wait")
            self.assertEqual(record["status"], "waiting_memory")
            self.assertEqual(record["payload"]["status"], "waiting_memory")

    def test_frontend_and_pipeline_use_one_canonical_stage_contract(self):
        root = Path(__file__).resolve().parents[2]
        pipeline = (root / "plugins/builtin/short_drama/workflows/v1.pipeline.json").read_text(encoding="utf-8")
        frontend_types = (root / "plugins/builtin/short_drama/frontend/types/production.ts").read_text(encoding="utf-8")
        frontend_flow = (root / "plugins/builtin/short_drama/frontend/utils/production-flow.ts").read_text(encoding="utf-8")
        for stage in CANONICAL_STAGES:
            self.assertIn(f'"{stage}"', pipeline)
            self.assertIn(f'"{stage}"', frontend_types)
            self.assertIn(f'"{stage}"', frontend_flow)
        self.assertEqual(canonical_stage("characters"), "assets")
        self.assertEqual(canonical_stage("shots"), "image")
        self.assertEqual(canonical_stage("merge"), "composition")

    def test_reused_asset_card_is_a_shared_component(self):
        root = Path(__file__).resolve().parents[2]
        app = (root / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
        component = (root / "plugins/builtin/short_drama/frontend/components/business/UnifiedAssetCard.vue").read_text(encoding="utf-8")
        self.assertIn('<UnifiedAssetCard v-for="item in group.items"', app)
        self.assertNotIn('<article v-for="item in group.items"', app)
        for kind in ('"character"', '"prop"', '"scene"'):
            self.assertIn(kind, component)

    def test_heavy_workloads_enter_the_shared_resource_scheduler(self):
        root = Path(__file__).resolve().parents[2]
        backend = (root / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
        self.assertNotIn("with HEAVY_TASK_LOCK:", backend)
        for resource_class in ("text", "audit", "image", "audio", "video", "3d", "upscale"):
            self.assertIn(f'_claim_production_resource("{resource_class}"', backend)
        self.assertIn("TASK_LEASES.acquire", backend)
        self.assertIn("WORKLOAD_ROUTER.route", backend)
        self.assertIn('name="production-worker-heartbeat"', backend)
        self.assertIn("if SERVICE_SHUTTING_DOWN.is_set():", backend)
        self.assertIn('"resources":RESOURCE_SCHEDULER.snapshot()', backend)
        self.assertIn('PRODUCTION_POOL_CAPACITIES = {"accelerator":1, "cpu-media":2, "control":8}', backend)
        self.assertIn('PRODUCTION_POOL_QUEUE_LIMITS = {"accelerator":16, "cpu-media":64, "control":256}', backend)
        self.assertIn('PRODUCTION_TENANT_QUEUE_LIMITS = {"accelerator":8, "cpu-media":32, "control":128}', backend)
        self.assertIn('PRODUCTION_PROJECT_QUEUE_LIMITS = {"accelerator":4, "cpu-media":16, "control":64}', backend)
        self.assertIn('tenant_id=str(scope.get("tenant_id") or "")', backend)
        self.assertIn('timeout=VIDEO_QUEUE_TIMEOUT_SECONDS, identity=body', backend)
        self.assertIn('timeout=IMAGE_QUEUE_TIMEOUT_SECONDS, identity=body', backend)
        self.assertIn('kwargs={"job_id":job_id, "body":body}', backend)
        self.assertIn('serialized_pools={"accelerator"}', backend)
        self.assertIn('active=len(resources.get("active_items") or [])', backend)

    def test_narrative_actions_reused_by_all_four_text_views(self):
        root = Path(__file__).resolve().parents[2]
        app = (root / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
        self.assertEqual(app.count("<NarrativeItemActions "), 4)
        self.assertNotIn('<span class="message-actions episode-actions"', app)

    def test_three_or_more_color_presets_use_one_component(self):
        root = Path(__file__).resolve().parents[2]
        app = (root / "plugins/builtin/short_drama/frontend/App.vue").read_text(encoding="utf-8")
        component = (root / "plugins/builtin/short_drama/frontend/components/base/ColorPresetPicker.vue").read_text(encoding="utf-8")
        self.assertEqual(app.count("<ColorPresetPicker "), 4)
        self.assertNotIn('<div class="color-presets"><button v-for=', app)
        self.assertIn('v-for="color in colors"', component)
    def test_ledger_persists_confirmations_dependencies_and_invalidation(self):
        with TemporaryDirectory() as temporary:
            ledger = ProductionLedger(Path(temporary) / "ledger.sqlite")
            identity = {"tenant_id":"tenant", "user_id":"user", "project_id":"project"}
            ledger.upsert({**identity, "stage":"outline", "scope_type":"project", "scope_id":"all", "lifecycle":"pending_confirmation", "content_fingerprint":"outline-v1"})
            ledger.upsert({**identity, "stage":"script", "scope_type":"episode", "scope_id":"1", "lifecycle":"completed", "content_fingerprint":"script-v1"})
            ledger.dependency({**identity, "source":{"stage":"outline", "scope_type":"project", "scope_id":"all"}, "target":{"stage":"script", "scope_type":"episode", "scope_id":"1"}})
            confirmed = ledger.confirm({**identity, "stage":"outline", "scope_type":"project", "scope_id":"all"})
            self.assertEqual(confirmed["lifecycle"], "completed")
            self.assertIsNotNone(confirmed["confirmation"])
            impact = ledger.impact({**identity, "source":{"stage":"outline", "scope_type":"project", "scope_id":"all"}, "reason":"changed"}, mutate=True)
            self.assertEqual([(item["stage"], item["scope_id"], item["lifecycle"]) for item in impact], [("script", "1", "stale")])
            self.assertGreaterEqual(len(ledger.versions(identity)), 3)

    def test_content_change_withdraws_confirmation(self):
        with TemporaryDirectory() as temporary:
            ledger = ProductionLedger(Path(temporary) / "ledger.sqlite")
            identity = {"tenant_id":"tenant", "user_id":"user", "project_id":"project"}
            payload = {**identity, "stage":"outline", "scope_type":"project", "scope_id":"all", "lifecycle":"pending_confirmation", "content_fingerprint":"one"}
            ledger.upsert(payload); ledger.confirm(payload)
            changed = ledger.upsert({**payload, "content_fingerprint":"two"})
            self.assertIsNone(changed["confirmation"])

    def test_langgraph_checkpoint_resumes_project_state(self):
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "control.sqlite"
            identity = {"tenant_id":"tenant", "user_id":"user", "project_id":"project"}
            brain = ProductionOrchestrator(database)
            self.assertEqual(brain.report(identity, "requirement", "completed", trusted=True)["next_stage"], "outline")
            self.assertEqual(brain.report(identity, "outline", "pending_confirmation")["status"], "waiting_human")
            self.assertEqual(brain.report(identity, "outline", "completed", trusted=True)["next_stage"], "script")
            self.assertEqual(brain.state(identity)["stages"]["outline"], "completed")

    def test_failed_stage_routes_to_director_repair(self):
        with TemporaryDirectory() as temporary:
            calls = []
            brain = ProductionOrchestrator(Path(temporary) / "control.sqlite", lambda payload: calls.append(payload) or {"action":"manual", "stage":"video", "reason":"需要人工判断"})
            state = brain.report({"tenant_id":"t", "user_id":"u", "project_id":"p"}, "video", "failed", error="bad")
            self.assertEqual(state["decision"], {"action":"manual", "stage":"video", "reason":"需要人工判断"})
            self.assertEqual(len(calls), 1)

    def test_langgraph_executes_replaceable_stage_and_waits_for_human_confirmation(self):
        with TemporaryDirectory() as temporary:
            identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
            brain = ProductionOrchestrator(Path(temporary) / "control.sqlite")
            brain.register_stage("requirements", lambda inputs: {"brief": inputs["brief"]})
            result = brain.execute(identity, "requirements", {"brief":"仙侠短剧"})
            self.assertEqual(result["status"], "waiting_human")
            self.assertEqual(result["output"], {"brief":"仙侠短剧"})
            brain.register_stage("requirements", lambda inputs: {"brief":"替换"}, provider_id="replacement", replace=True)
            self.assertEqual(brain.stages()[0].provider_id, "replacement")
            brain.enable_stage("requirements", False)
            with self.assertRaisesRegex(ValueError, "disabled"):
                brain.execute(identity, "requirements", {})
            self.assertTrue(brain.unregister_stage("requirements"))

    def test_langgraph_rejects_stage_when_previous_gate_is_incomplete(self):
        with TemporaryDirectory() as temporary:
            identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
            brain = ProductionOrchestrator(Path(temporary) / "control.sqlite")
            brain.register_stage("outline", lambda inputs: {"episodes": []})
            with self.assertRaisesRegex(ValueError, "previous stage"):
                brain.execute(identity, "outline", {})

    def test_langgraph_begin_gates_legacy_production_endpoints(self):
        with TemporaryDirectory() as temporary:
            identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
            brain = ProductionOrchestrator(Path(temporary) / "control.sqlite")
            with self.assertRaisesRegex(ValueError, "requirements"):
                brain.begin(identity, "outline")
            brain.report(identity, "requirements", "completed", trusted=True)
            self.assertEqual(brain.begin(identity, "outline")["current_stage"], "outline")

    def test_resource_scheduler_prioritizes_waiting_text_over_video(self):
        scheduler = ResourceScheduler()
        order = []
        entered = threading.Event(); release = threading.Event()
        def active():
            with scheduler.claim("control", "active"):
                entered.set(); release.wait(2)
        holder = threading.Thread(target=active); holder.start(); self.assertTrue(entered.wait(1))
        video = threading.Thread(target=lambda: self._claim(scheduler, "video", "video", order))
        text = threading.Thread(target=lambda: self._claim(scheduler, "text", "text", order))
        video.start(); time.sleep(.02); text.start(); time.sleep(.02); release.set()
        holder.join(); video.join(); text.join()
        self.assertEqual(order, ["text", "video"])

    def test_resource_scheduler_can_cancel_waiter(self):
        scheduler = ResourceScheduler(); entered = threading.Event(); release = threading.Event(); result = []
        holder = threading.Thread(target=lambda: self._hold(scheduler, entered, release)); holder.start(); self.assertTrue(entered.wait(1))
        def waiter():
            try:
                with scheduler.claim("video", "cancel-me", timeout=2): pass
            except ResourceSchedulerError as error: result.append(str(error))
        thread = threading.Thread(target=waiter); thread.start()
        for _ in range(100):
            if scheduler.snapshot()["queued"]: break
            threading.Event().wait(.005)
        self.assertEqual(scheduler.cancel_job("cancel-me"), 1); release.set(); holder.join(); thread.join()
        self.assertEqual(result, ["resource request cancelled"])

    def test_resource_scheduler_pools_allow_safe_parallelism_and_keep_gpu_serial(self):
        scheduler = ResourceScheduler(
            resource_pools={"control":"control", "audio":"cpu", "text":"gpu", "image":"gpu", "video":"gpu", "audit":"gpu", "3d":"gpu", "upscale":"gpu"},
            pool_capacities={"control":4, "cpu":2, "gpu":1}, serialized_pools={"gpu"},
        )
        gpu_entered = threading.Event(); release_gpu = threading.Event()
        second_gpu_entered = threading.Event(); control_entered = threading.Event(); audio_entered = threading.Event()
        def hold_gpu():
            with scheduler.claim("video", "gpu-1"):
                gpu_entered.set(); release_gpu.wait(2)
        def wait_gpu():
            with scheduler.claim("image", "gpu-2", timeout=2): second_gpu_entered.set()
        holder = threading.Thread(target=hold_gpu); holder.start(); self.assertTrue(gpu_entered.wait(1))
        follower = threading.Thread(target=wait_gpu); follower.start()
        # Use real context managers for the independent pools and release immediately.
        def short_claim(resource, job, event):
            with scheduler.claim(resource, job, timeout=1): event.set()
        control = threading.Thread(target=short_claim, args=("control", "control-1", control_entered))
        audio = threading.Thread(target=short_claim, args=("audio", "audio-1", audio_entered))
        control.start(); audio.start()
        self.assertTrue(control_entered.wait(1)); self.assertTrue(audio_entered.wait(1))
        self.assertFalse(second_gpu_entered.is_set())
        snapshot = scheduler.snapshot()
        self.assertEqual(snapshot["pools"]["gpu"]["active"], 1)
        self.assertEqual(snapshot["pools"]["gpu"]["queued"], 1)
        release_gpu.set()
        for thread in (holder, follower, control, audio): thread.join(2)
        self.assertTrue(second_gpu_entered.is_set())

    def test_resource_scheduler_enforces_capacity_within_cpu_pool(self):
        scheduler = ResourceScheduler(
            resource_pools={resource:("cpu" if resource == "audio" else "gpu") for resource in ("control", "text", "audit", "image", "audio", "video", "3d", "upscale")},
            pool_capacities={"cpu":2, "gpu":1}, serialized_pools={"gpu"},
        )
        entered = [threading.Event() for _ in range(3)]; release = threading.Event()
        def worker(index):
            with scheduler.claim("audio", f"audio-{index}", timeout=2):
                entered[index].set(); release.wait(2)
        threads = [threading.Thread(target=worker, args=(index,)) for index in range(3)]
        for thread in threads: thread.start()
        deadline = time.time() + 1
        while time.time() < deadline and sum(event.is_set() for event in entered) < 2: time.sleep(.01)
        self.assertEqual(sum(event.is_set() for event in entered), 2)
        waiting_index = next(index for index, event in enumerate(entered) if not event.is_set())
        release.set()
        for thread in threads: thread.join(2)
        self.assertTrue(entered[waiting_index].is_set())

    def test_resource_scheduler_applies_per_pool_backpressure(self):
        scheduler = ResourceScheduler(
            resource_pools={resource:"gpu" for resource in ("control", "text", "audit", "image", "audio", "video", "3d", "upscale")},
            pool_capacities={"gpu":1}, pool_queue_limits={"gpu":1}, serialized_pools={"gpu"},
        )
        entered = threading.Event(); release = threading.Event(); waiter_done = threading.Event()
        holder = threading.Thread(target=lambda: self._hold(scheduler, entered, release)); holder.start(); self.assertTrue(entered.wait(1))
        def queued():
            with scheduler.claim("video", "queued", timeout=2): pass
            waiter_done.set()
        waiter = threading.Thread(target=queued); waiter.start()
        deadline = time.time() + 1
        while time.time() < deadline and not scheduler.snapshot()["queued"]: time.sleep(.01)
        with self.assertRaisesRegex(ResourceSchedulerError, "backpressure: gpu"):
            with scheduler.claim("image", "rejected", timeout=.1): pass
        snapshot = scheduler.snapshot()
        self.assertEqual(snapshot["pools"]["gpu"]["queue_limit"], 1)
        release.set(); holder.join(2); waiter.join(2); self.assertTrue(waiter_done.is_set())

    def test_resource_scheduler_applies_tenant_and_project_queue_backpressure(self):
        scheduler = ResourceScheduler(
            resource_pools={resource:"gpu" for resource in ("control", "text", "audit", "image", "audio", "video", "3d", "upscale")},
            pool_capacities={"gpu":1}, pool_queue_limits={"gpu":8},
            tenant_queue_limits={"gpu":2}, project_queue_limits={"gpu":1}, serialized_pools={"gpu"},
        )
        entered = threading.Event(); release = threading.Event()
        holder = threading.Thread(target=lambda: self._hold(scheduler, entered, release)); holder.start(); self.assertTrue(entered.wait(1))
        errors = []
        def wait(job, project):
            try:
                with scheduler.claim("image", job, timeout=2, tenant_id="tenant-a", user_id="user", project_id=project): pass
            except ResourceSchedulerError as error: errors.append(str(error))
        first = threading.Thread(target=wait, args=("first", "project-a")); first.start()
        deadline = time.time() + 1
        while time.time() < deadline and len(scheduler.snapshot()["queued"]) < 1: time.sleep(.01)
        with self.assertRaisesRegex(ResourceSchedulerError, "project resource backpressure: gpu"):
            with scheduler.claim("image", "same-project", timeout=.1, tenant_id="tenant-a", user_id="user", project_id="project-a"): pass
        second = threading.Thread(target=wait, args=("second", "project-b")); second.start()
        deadline = time.time() + 1
        while time.time() < deadline and len(scheduler.snapshot()["queued"]) < 2: time.sleep(.01)
        with self.assertRaisesRegex(ResourceSchedulerError, "tenant resource backpressure: gpu"):
            with scheduler.claim("image", "same-tenant", timeout=.1, tenant_id="tenant-a", user_id="user", project_id="project-c"): pass
        other_errors = []
        def other_tenant():
            try:
                with scheduler.claim("image", "other-tenant", timeout=2, tenant_id="tenant-b", user_id="user", project_id="project-a"): pass
            except ResourceSchedulerError as error: other_errors.append(str(error))
        third = threading.Thread(target=other_tenant); third.start()
        deadline = time.time() + 1
        while time.time() < deadline and len(scheduler.snapshot()["queued"]) < 3: time.sleep(.01)
        snapshot = scheduler.snapshot()
        self.assertEqual(snapshot["pools"]["gpu"]["tenant_queue_limit"], 2)
        self.assertEqual(snapshot["pools"]["gpu"]["project_queue_limit"], 1)
        self.assertEqual(len(snapshot["queued"]), 3)
        self.assertEqual({item["tenant_id"] for item in snapshot["queued"]}, {"tenant-a", "tenant-b"})
        with self.assertRaisesRegex(ResourceSchedulerError, "must be supplied together"):
            with scheduler.claim("image", "partial", tenant_id="tenant-a"): pass
        release.set(); holder.join(2); first.join(2); second.join(2); third.join(2)
        self.assertEqual(errors + other_errors, [])

    def test_workload_router_reaps_expired_worker_projections(self):
        router = WorkloadRouter(heartbeat_timeout=10)
        router.heartbeat(WorkerSnapshot("old", "scope", ("image",), 1, 0, 0, 100, 10, endpoint="http://old"))
        router.heartbeat(WorkerSnapshot("live", "scope", ("image",), 1, 0, 0, 100, 25, endpoint="http://live"))
        self.assertEqual(router.reap(now=30), 1)
        self.assertEqual([item["worker_id"] for item in router.snapshot(now=30)], ["live"])

    def test_story_bible_rejects_duplicate_titles_and_events(self):
        episodes = [
            {"episode":1, "title":"血脉觉醒", "core_event":"女主首次唤醒血脉力量"},
            {"episode":2, "title":"血脉觉醒", "core_event":"女主首次唤醒血脉力量"},
        ]
        violations = StoryBible.validate(episodes)
        self.assertTrue(any("标题重复" in item for item in violations))
        self.assertTrue(any("核心事件重复" in item for item in violations))

    def test_story_bible_persists_episode_facts(self):
        with TemporaryDirectory() as temporary:
            bible = StoryBible(Path(temporary) / "story.sqlite")
            identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
            result = bible.update(identity, "outline", {"episodes":[{"episode":1, "title":"开局", "core_event":"女主进入宗门并遭到当众质疑", "hook":"身份玉佩发光"}]})
            self.assertEqual(result["episodes"][0]["title"], "开局")
            self.assertEqual(result["violations"], [])

    def test_storyboard_many_shots_are_one_episode_fact(self):
        shots = [{"episode":1, "shot_number":number} for number in range(1, 21)]
        self.assertEqual(StoryBible._episodes("storyboard", {"shots":shots}), [{"episode":1}])
        self.assertEqual(StoryBible.validate(StoryBible._episodes("storyboard", {"shots":shots})), [])

    def test_story_bible_rejects_semantic_duplicates_and_similar_character_names(self):
        with TemporaryDirectory() as temporary:
            bible = StoryBible(Path(temporary) / "story.sqlite")
            identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
            with self.assertRaises(StoryBibleError):
                bible.update(identity, "outline", {"episodes":[
                    {"episode":1, "title":"血脉之力初现", "core_event":"血脉力量初次爆发震慑全场"},
                    {"episode":2, "title":"血脉力量初现", "core_event":"血脉力量第一次爆发并震慑众人"},
                ]})
            with self.assertRaises(StoryBibleError):
                bible.update(identity, "outline", {"plan":{"characters":[{"name":"苏璃"},{"name":"白璃"}]}, "episodes":[{"episode":1,"title":"开局","core_event":"女主进入宗门遭到质疑"}]})

    def test_script_cannot_introduce_episode_missing_from_outline(self):
        with TemporaryDirectory() as temporary:
            bible = StoryBible(Path(temporary) / "story.sqlite")
            identity = {"tenant_id":"t", "user_id":"u", "project_id":"p"}
            bible.update(identity, "outline", {"episodes":[{"episode":1,"title":"开局","core_event":"女主进入宗门遭到质疑"}]})
            with self.assertRaises(StoryBibleError):
                bible.update(identity, "script", {"scripts":[{"episode":2,"title":"越界","content":"未登记内容"}]})

    @staticmethod
    def _claim(scheduler, kind, job, order):
        with scheduler.claim(kind, job): order.append(job)

    @staticmethod
    def _hold(scheduler, entered, release):
        with scheduler.claim("control", "holder"):
            entered.set(); release.wait(2)


if __name__ == "__main__":
    unittest.main()
