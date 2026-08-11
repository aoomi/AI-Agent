import importlib.util
import json
import tempfile
import threading
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
FRONTEND = ROOT / "plugins/builtin/short_drama/frontend/App.vue"


def load_backend():
    spec = importlib.util.spec_from_file_location("compat_server_text_runtime_test", BACKEND)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(module, root: Path) -> None:
    module.OUTPUT_ROOT = root
    module.PROJECTS_FILE = root / "projects.json"
    module.PROJECT_SNAPSHOTS_DIR = root / "snapshots"
    module.TEXT_JOBS_FILE = root / "text-jobs.json"
    module.PRODUCTION_LEDGER = module.ProductionLedger(root / "production-ledger.sqlite")
    module.PRODUCTION_ORCHESTRATOR_FILE = root / "production-orchestrator.sqlite"
    module.PRODUCTION_ORCHESTRATOR = None
    module.WORKER_SCOPE = f"test-{root.name}"
    module.WORKER_ID = f"worker-{root.name}"
    module.WORKLOAD_ROUTER = module.WorkloadRouter(heartbeat_timeout=30)
    module.TASK_LEASES = module.TaskLeaseRepository(root / "task-leases.sqlite")
    module.WORKER_REGISTRY = module.WorkerRegistry(root / "worker-registry.sqlite")
    projects = [{"id":project_id, "tenant_id":"local-default", "user_id":"aoo", "stage_state":{}} for project_id in ("project-1", "p", "p1")]
    module.PROJECTS_FILE.write_text(json.dumps({"projects":projects}), encoding="utf-8")
    for project in projects:
        identity = {key:project[key] for key in ("tenant_id", "user_id", "id")}
        identity["project_id"] = identity.pop("id")
        module._production_orchestrator().report(identity, "requirements", "completed", trusted=True)
        module._production_orchestrator().report(identity, "outline", "completed", trusted=True)
    module.ACTIVE_TEXT_JOBS.clear()
    module.FORMAL_MODEL_OWNER_JOB_ID = ""


def test_restart_recovers_text_job_and_script_stage() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._save_text_jobs({"jobs":{"task-1":{"status":"generating"}}})
        module.PROJECTS_FILE.write_text(json.dumps({"projects":[{
            "id":"project-1", "stage_state":{"script":{"revision":1, "data":{
                "status":"generating", "phase":"generating", "generation_id":"task-1",
                "scripts":[{"episode":1, "title":"", "content":""}],
            }}}
        }]}), encoding="utf-8")
        module._recover_text_jobs()
        job = json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"]["task-1"]
        stage = json.loads(module.PROJECTS_FILE.read_text())["projects"][0]["stage_state"]["script"]
        assert job["status"] == "failed"
        assert stage["data"]["status"] == "failed"
        assert stage["data"]["generation_id"] == ""
        assert stage["data"]["heartbeat_at"] == 0
        assert stage["revision"] == 2


def test_failed_text_job_cannot_be_overwritten_completed() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._update_text_job("task-2", status="generating")
        module.ACTIVE_TEXT_JOBS["task-2"] = {"heartbeat_epoch":0}
        module._finish_text_job("task-2", "failed", "stopped")
        module._finish_text_job("task-2", "completed")
        job = json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"]["task-2"]
        assert job["status"] == "failed"
        assert job["error"] == "stopped"
        assert "task-2" not in module.ACTIVE_TEXT_JOBS


def test_frontend_persists_identity_heartbeat_and_retries_empty_episode() -> None:
    source = FRONTEND.read_text(encoding="utf-8")
    assert "generation_id:scriptGenerationId.value" in source
    assert "heartbeat_at:scriptHeartbeatAt.value" in source
    assert "scriptGenerationId.value = crypto.randomUUID()" in source
    script_function = source[source.index("async function generateScripts"):source.index("async function runScriptPrimaryAction")]
    assert 'productionLedgerService.runStage<{ scripts:ScriptItem[]; audits:OutlineAudit[] }>' in script_function
    assert 'stage:"script"' in script_function
    assert "for (let attempt" not in script_function
    assert "if (interrupted) await persistScriptState(project)" in source
    assert 'persistScriptState(interruptedProject)' in source
    assert 'client_generation_id:interruptedGenerationId' in source
    assert 'project_id:project?.id || ""' in source


def test_ollama_generation_always_runs_explicit_unload() -> None:
    module = load_backend()
    calls = []
    module._require_memory = lambda _value: None
    module._unload_ollama_model = lambda *_args: calls.append("unload")
    class BrokenResponse:
        def __enter__(self): raise OSError("network failed")
        def __exit__(self, *_args): return False
    original = module.urlopen
    module.urlopen = lambda *_args, **_kwargs: BrokenResponse()
    try:
        try: module._ollama_json("test")
        except OSError: pass
        else: raise AssertionError("network failure was accepted")
    finally:
        module.urlopen = original
    assert calls == ["unload"]


def test_shutdown_recovers_persisted_nonterminal_jobs_without_active_thread() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._save_text_jobs({"jobs":{
            "queued":{"status":"queued"}, "generating":{"status":"generating"},
            "retrying":{"status":"retrying"}, "processing":{"status":"processing"},
            "completed":{"status":"completed"},
        }})
        module.PROJECTS_FILE.write_text(json.dumps({"projects":[]}), encoding="utf-8")
        unloads = []
        module._unload_ollama_model = lambda: unloads.append(True)
        module._shutdown_text_jobs()
        jobs = json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"]
        assert all(jobs[name]["status"] == "failed" for name in ("queued", "generating", "retrying", "processing"))
        assert jobs["completed"]["status"] == "completed"
        assert not module.ACTIVE_TEXT_JOBS
        assert unloads == [True]


def test_script_episode_http_registers_unique_job_and_completes() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._ollama_json = lambda _prompt, *_args, **_kwargs: {"script":{"title":"测试集", "content":[
            {"画面":f"画面{i}", "动作":f"动作{i}", "台词":"无", "旁白":"无", "情绪":"紧张"} for i in range(12)
        ]}}
        server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        task_id = "12345678-1234-1234-1234-123456789abc"
        body = json.dumps({"generation_id":task_id, "project_id":"project-1", "episode":1, "duration":60}).encode()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/api/script/episode", data=body, headers={"Content-Type":"application/json"}, method="POST")
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read())
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        assert payload["job_id"] != task_id
        assert payload["script"]["title"] == "测试集"
        job = json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"][payload["job_id"]]
        assert job["job_id"] == payload["job_id"]
        assert job["client_generation_id"] == task_id
        assert job["status"] == "completed"
        assert payload["job_id"] not in module.ACTIVE_TEXT_JOBS


def test_same_client_generation_creates_unique_job_per_episode() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._ollama_json = lambda _prompt, *_args, **_kwargs: {"script":{"title":"测试集", "content":[
            {"画面":f"画面{i}", "动作":f"动作{i}", "台词":"无", "旁白":"无", "情绪":"紧张"} for i in range(12)
        ]}}
        server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        client_id = "11111111-1111-4111-8111-111111111111"; ids = []
        try:
            for episode in (1, 2):
                body = json.dumps({"generation_id":client_id, "project_id":"project-1", "episode":episode, "duration":60}).encode()
                request = Request(f"http://127.0.0.1:{server.server_port}/api/script/episode", data=body, headers={"Content-Type":"application/json", "X-Production-Dispatched":"1"}, method="POST")
                with urlopen(request, timeout=10) as response: ids.append(json.loads(response.read())["job_id"])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        jobs = json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"]
        assert ids[0] != ids[1]
        assert len(jobs) == 2
        assert {jobs[job_id]["episode"] for job_id in ids} == {1, 2}
        assert all(jobs[job_id]["client_generation_id"] == client_id for job_id in ids)


def test_watchdog_checks_actual_worker_and_hard_deadline() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    assert '"worker_thread":threading.current_thread()' in source
    assert 'worker.is_alive() and worker.ident == active.get("thread_id")' in source
    assert 'now - started > timeout_seconds' in source
    assert 'timeout_seconds = float(job.get("timeout_seconds") or TEXT_JOB_TIMEOUT_SECONDS)' in source
    assert 'active.get("project_id") == project_id' in source
    assert 'stored.get("client_generation_id") == client_generation_id' in source


def test_outline_jobs_recover_and_frontend_stops_exact_project() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._save_text_jobs({"jobs":{"outline-1":{"status":"generating", "stage":"outline"}}})
        module.PROJECTS_FILE.write_text(json.dumps({"projects":[{
            "id":"project-1", "stage_state":{"outline":{"revision":1, "data":{
                "status":"generating", "phase":"generating", "generation_id":"batch-1",
            }}}
        }]}), encoding="utf-8")
        module._recover_text_jobs()
        jobs = json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"]
        stage = json.loads(module.PROJECTS_FILE.read_text())["projects"][0]["stage_state"]["outline"]
        assert jobs["outline-1"]["status"] == "failed"
        assert stage["data"]["status"] == "failed"
        assert stage["data"]["generation_id"] == ""
    frontend = FRONTEND.read_text(encoding="utf-8")
    assert 'narrativeService.stop("outline", { ...productionTaskContext(interruptedProject), client_generation_id:interruptedOutlineGenerationId })' in frontend
    assert 'narrativeService.stop("outline", { ...productionTaskContext(project), client_generation_id:clientGenerationId })' in frontend
    assert 'for (const character of Array.from(text))' not in frontend
    assert 'audit_mode:"both", range:`第${start}' not in frontend
    outline_function = frontend[frontend.index("async function generateOutline"):frontend.index("async function confirmOutline")]
    assert 'productionLedgerService.runStage<{ plan:OutlinePlan; episodes:EpisodeOutline[]; audit:OutlineAudit | null }>' in outline_function
    assert 'stage:"outline"' in outline_function
    assert "for (let attempt" not in outline_function


def test_outline_post_validation_failure_unloads_retained_formal_model() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        unloaded = []
        module._ollama_json = lambda *_args, **_kwargs: {"episodes":[{"episode":1}]}
        module._validate_outline_episode_batch = lambda *_args: (_ for _ in ()).throw(ValueError("invalid batch"))
        module._unload_ollama_model = lambda model=None: unloaded.append(model)
        server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        body = json.dumps({"project_id":"p", "generation_id":"g", "start_episode":1, "count":1, "total_episodes":20}).encode()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/api/outline/episodes", data=body, headers={"Content-Type":"application/json"}, method="POST")
            try: urlopen(request, timeout=10)
            except Exception: pass
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        assert unloaded == [module.TEXT_FORMAL_MODEL]
        job = next(iter(json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"].values()))
        assert job["status"] == "failed"


def test_watchdog_uses_hard_ollama_runner_termination() -> None:
    source = BACKEND.read_text(encoding="utf-8")
    assert '_terminate_ollama_model(TEXT_FORMAL_MODEL)' in source
    assert '["/usr/local/bin/ollama", "stop", model]' in source


def test_ollama_stop_nonzero_falls_back_and_verifies_runner_absent() -> None:
    module = load_backend(); unloaded = []
    class Result: returncode = 1
    module.subprocess.run = lambda *_args, **_kwargs: Result()
    module._unload_ollama_model = lambda model=None: unloaded.append(model)
    module._ollama_model_loaded = lambda _model: False
    assert module._terminate_ollama_model(module.TEXT_FORMAL_MODEL) is True
    assert unloaded == [module.TEXT_FORMAL_MODEL]


def test_ollama_stop_does_not_report_success_while_runner_remains() -> None:
    module = load_backend(); unloads = []
    class Result: returncode = 0
    module.subprocess.run = lambda *_args, **_kwargs: Result()
    module._unload_ollama_model = lambda model=None: unloads.append(model)
    module._ollama_model_loaded = lambda _model: True
    module.time.sleep = lambda _seconds: None
    assert module._terminate_ollama_model(module.TEXT_FORMAL_MODEL) is False
    assert unloads == [module.TEXT_FORMAL_MODEL]


def test_stopping_waiting_outline_does_not_kill_other_project_owner() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        now = __import__("time").time(); worker = threading.current_thread()
        for job_id, project_id in (("waiting-p1", "p1"), ("owner-p2", "p2")):
            module.ACTIVE_TEXT_JOBS[job_id] = {"project_id":project_id, "stage":"outline", "started_epoch":now, "heartbeat_epoch":now, "worker_thread":worker, "thread_id":worker.ident}
            module._update_text_job(job_id, status="generating", project_id=project_id, stage="outline", client_generation_id=f"g-{project_id}", request={"tenant_id":"local-default", "user_id":"aoo", "project_id":project_id})
        module.FORMAL_MODEL_OWNER_JOB_ID = "owner-p2"
        terminations = []
        module._terminate_ollama_model = lambda _model: (terminations.append(True) or True)
        server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        body = json.dumps({"kind":"outline", "tenant_id":"local-default", "user_id":"aoo", "project_id":"p1", "client_generation_id":"g-p1"}).encode()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/api/generation/stop", data=body, headers={"Content-Type":"application/json"}, method="POST")
            with urlopen(request, timeout=10) as response: payload = json.loads(response.read())
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        assert payload["stopped"] == ["waiting-p1"]
        assert terminations == []
        assert "owner-p2" in module.ACTIVE_TEXT_JOBS
        jobs = json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"]
        assert jobs["waiting-p1"]["status"] == "failed" and jobs["owner-p2"]["status"] == "generating"


def test_cancelled_waiter_cannot_start_after_heavy_lock_releases() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._update_text_job("waiter", status="failed")
        calls = []
        module.urlopen = lambda *_args, **_kwargs: calls.append(True)
        try: module._ollama_json("x", module.TEXT_FORMAL_MODEL, 1, owner_job_id="waiter")
        except RuntimeError as error: assert "已停止" in str(error)
        else: raise AssertionError("cancelled waiter started inference")
        assert calls == [] and module.FORMAL_MODEL_OWNER_JOB_ID == ""


def test_stopping_script_owner_terminates_runner_before_failed_terminal() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        now = __import__("time").time(); worker = threading.current_thread(); job_id = "script-owner"
        module.ACTIVE_TEXT_JOBS[job_id] = {"project_id":"p1", "stage":"script", "started_epoch":now, "heartbeat_epoch":now, "worker_thread":worker, "thread_id":worker.ident}
        module._update_text_job(job_id, status="generating", project_id="p1", stage="script", client_generation_id="g1", request={"tenant_id":"local-default", "user_id":"aoo", "project_id":"p1"})
        module.FORMAL_MODEL_OWNER_JOB_ID = job_id
        terminations = []
        module._terminate_ollama_model = lambda _model: (terminations.append(True) or True)
        server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        body = json.dumps({"kind":"script", "tenant_id":"local-default", "user_id":"aoo", "project_id":"p1", "client_generation_id":"g1"}).encode()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/api/generation/stop", data=body, headers={"Content-Type":"application/json"}, method="POST")
            with urlopen(request, timeout=10) as response: payload = json.loads(response.read())
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        assert payload["stopped"] == [job_id] and terminations == [True]
        assert job_id not in module.ACTIVE_TEXT_JOBS
        assert json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"][job_id]["status"] == "failed"


def test_outline_http_tracks_jobs_and_reuses_formal_model_until_last_batch() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        calls = []
        def fake_ollama(_prompt, model, memory, **options):
            calls.append((model, memory, options))
            if len(calls) == 1:
                return {"title":"测试", "general_outline":"总纲", "characters":[], "arcs":[]}
            start = 1 if len(calls) == 2 else 11
            return {"episodes":[{
                "episode":episode, "title":f"唯一标题{episode}", "story_stage":f"第{episode}集·推进",
                "core_event":f"事件{episode}", "protagonist_action":f"主动行动{episode}",
                "ability_progression":f"第{episode}阶能力，冷却一刻钟", "villain_action":f"手段{episode}并受罚",
                "supporting_motivation":f"盟友目标{episode}", "protection_set_piece":"本集不设置",
                "irreversible_change":f"状态改变{episode}", "new_information":f"线索{episode}",
                "resolved_setup":"无", "cliffhanger":f"信物{episode}出现", "synopsis":f"完整梗概{episode}",
            } for episode in range(start, start + 10)]}
        module._ollama_json = fake_ollama
        module._validate_outline_episode_batch = lambda episodes, *_args: episodes
        server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def post(path, body):
            request = Request(f"http://127.0.0.1:{server.server_port}{path}", data=json.dumps(body).encode(), headers={"Content-Type":"application/json", "X-Production-Dispatched":"1"}, method="POST")
            with urlopen(request, timeout=10) as response: return json.loads(response.read())
        common = {"project_id":"project-1", "generation_id":"batch-1", "total_episodes":20}
        try:
            plan = post("/api/outline/plan", common)
            first = post("/api/outline/episodes", {**common, "start_episode":1, "count":10, "previous_episodes":[]})
            last = post("/api/outline/episodes", {**common, "start_episode":11, "count":10, "previous_episodes":first["episodes"]})
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        assert len({plan["job_id"], first["job_id"], last["job_id"]}) == 3
        jobs = json.loads(module.TEXT_JOBS_FILE.read_text())["jobs"]
        assert len(jobs) == 3 and all(job["status"] == "completed" for job in jobs.values())
        assert calls[0][2]["release_model"] is False
        assert calls[1][2]["release_model"] is False
        assert calls[2][2]["release_model"] is True
        assert not module.ACTIVE_TEXT_JOBS
