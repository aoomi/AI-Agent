import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"


def load_backend():
    spec = importlib.util.spec_from_file_location("compat_server_runtime_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(module, root: Path) -> None:
    module.IMAGE_JOBS_FILE = root / "image-jobs.json"
    module.OUTPUT_ROOT = root / "output"
    module.ACTIVE_IMAGE_JOBS.clear()
    module.ACTIVE_IMAGE_SUBJECTS.clear()
    module.ACTIVE_IMAGE_PROCESSES.clear()
    module.ACTIVE_IMAGE_WORKERS.clear()
    module.IMAGE_SHUTTING_DOWN.clear()


def test_shutdown_gate_rejects_new_process_without_spawning() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        target = root / "forbidden.png"
        module._update_image_job("job-shutdown", status="queued", started_at=module._iso_now())
        module.IMAGE_SHUTTING_DOWN.set()
        try:
            module._run_image_process(
                "job-shutdown",
                [str(Path(sys.executable).resolve()), "-c", f"from pathlib import Path; Path({str(target)!r}).write_bytes(b'bad')"],
                cwd=root,
                target=target,
                timeout=10,
            )
        except RuntimeError as error:
            assert "关闭" in str(error)
        else:
            raise AssertionError("shutdown gate accepted a new image process")
        job = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]["job-shutdown"]
        assert job["status"] == "failed"
        assert not target.exists()
        assert not module.ACTIVE_IMAGE_PROCESSES


def test_registration_failure_terminates_spawned_process_and_does_not_retry() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        target = root / "never.png"
        module._update_image_job("job-register-fail", status="queued", started_at=module._iso_now())
        original_save = module._save_image_jobs
        calls = 0

        def fail_first_registration(store):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("simulated persistence failure")
            return original_save(store)

        module._save_image_jobs = fail_first_registration
        try:
            try:
                module._run_image_process(
                    "job-register-fail",
                    [str(Path(sys.executable).resolve()), "-c", "import time; time.sleep(30)"],
                    cwd=root,
                    target=target,
                    timeout=10,
                )
            except RuntimeError as error:
                assert "登记失败" in str(error)
            else:
                raise AssertionError("registration failure was accepted")
        finally:
            module._save_image_jobs = original_save
        assert calls == 2
        assert not module.ACTIVE_IMAGE_PROCESSES
        assert not module.ACTIVE_IMAGE_JOBS
        job = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]["job-register-fail"]
        assert job["status"] == "failed"


def test_image_process_records_pid_heartbeat_and_completion_transition() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        target = root / "done.png"
        module._update_image_job("job-1", status="queued", started_at=module._iso_now())
        command = [str(Path(sys.executable).resolve()), "-c", f"from pathlib import Path; Path({str(target)!r}).write_bytes(b'ok')"]
        module._run_image_process("job-1", command, cwd=root, target=target, timeout=10)
        job = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]["job-1"]
        assert target.read_bytes() == b"ok"
        assert job["status"] == "processing"
        assert job["heartbeat_at"]
        assert job["pid"] is None and job["process_group"] is None


def test_image_process_retries_only_once() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        target = root / "done.png"; marker = root / "attempts.txt"
        module._update_image_job("job-2", status="queued", started_at=module._iso_now())
        script = (
            "from pathlib import Path; import sys; "
            f"m=Path({str(marker)!r}); n=int(m.read_text())+1 if m.exists() else 1; m.write_text(str(n)); "
            f"Path({str(target)!r}).write_bytes(b'ok') if n==2 else sys.exit(7)"
        )
        module._run_image_process("job-2", [str(Path(sys.executable).resolve()), "-c", script], cwd=root, target=target, timeout=10)
        job = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]["job-2"]
        assert marker.read_text() == "2"
        assert job["retry_count"] == 1


def test_service_restart_recovers_persisted_running_state() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._save_image_jobs({"jobs":{"job-3":{"status":"generating", "pid":None, "process_group":None}}})
        module._recover_image_jobs()
        job = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]["job-3"]
        assert job["status"] == "failed"
        assert "服务重启" in job["error"]


def test_service_restart_downgrades_completed_job_with_missing_media() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        missing = root / "images" / "missing.png"
        module._save_image_jobs({"jobs":{"job-missing":{"status":"completed", "output_path":str(missing),
            "image":{"url":"/api/result-media?filename=missing.png&subfolder=images"}}}})
        module._recover_image_jobs()
        job = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]["job-missing"]
        assert job["status"] == "failed"
        assert job["error"] == "已完成图片文件缺失，请重新生成"


def test_service_restart_keeps_completed_job_when_media_exists() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        image = root / "images" / "kept.png"; image.parent.mkdir(exist_ok=True); image.write_bytes(b"png")
        module._save_image_jobs({"jobs":{"job-kept":{"status":"completed", "output_path":str(image),
            "image":{"url":"/api/result-media?filename=kept.png&subfolder=images"}}}})
        module._recover_image_jobs()
        job = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]["job-kept"]
        assert job["status"] == "completed"


def test_timeout_terminates_process_and_retries_once() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        target = root / "never.png"
        module._update_image_job("job-timeout", status="queued", started_at=module._iso_now())
        try:
            module._run_image_process("job-timeout", [str(Path(sys.executable).resolve()), "-c", "import time; time.sleep(30)"], cwd=root, target=target, timeout=1)
        except RuntimeError as error:
            assert "超时" in str(error)
        else:
            raise AssertionError("timeout was accepted")
        job = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]["job-timeout"]
        assert job["status"] == "failed"
        assert job["retry_count"] == 1
        assert not module.ACTIVE_IMAGE_PROCESSES


def test_watchdog_reconciles_job_without_process() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module.IMAGE_WATCHDOG_SECONDS = 1
        module._save_image_jobs({"jobs":{
            f"job-{status}":{"status":status, "heartbeat_at":"2000-01-01T00:00:00+00:00"}
            for status in ("generating", "retrying", "processing")
        }})
        module.IMAGE_WATCHDOG_STOP.clear()
        original_wait = module.IMAGE_WATCHDOG_STOP.wait
        calls = 0
        def wait_once(_seconds):
            nonlocal calls
            calls += 1
            return calls > 1
        module.IMAGE_WATCHDOG_STOP.wait = wait_once
        try: module._monitor_image_jobs()
        finally: module.IMAGE_WATCHDOG_STOP.wait = original_wait
        jobs = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]
        assert all(job["status"] == "failed" for job in jobs.values())
        assert all("无实际进程" in job["error"] for job in jobs.values())


def test_watchdog_preserves_processing_job_while_request_worker_is_alive() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module.IMAGE_WATCHDOG_SECONDS = 1
        module._save_image_jobs({"jobs":{"job-audit":{
            "status":"processing", "started_at":module._iso_now(),
            "heartbeat_at":"2000-01-01T00:00:00+00:00", "timeout_seconds":1800,
        }}})
        module.ACTIVE_IMAGE_WORKERS["job-audit"] = threading.current_thread()
        original_wait = module.IMAGE_WATCHDOG_STOP.wait
        calls = 0
        def wait_once(_seconds):
            nonlocal calls
            calls += 1
            return calls > 1
        module.IMAGE_WATCHDOG_STOP.wait = wait_once
        try: module._monitor_image_jobs()
        finally: module.IMAGE_WATCHDOG_STOP.wait = original_wait
        job = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]["job-audit"]
        assert job["status"] == "processing"


def test_new_task_cleanup_reclaims_all_stale_nonterminal_states() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._save_image_jobs({"jobs":{
            f"job-{status}":{"status":status, "heartbeat_at":"2000-01-01T00:00:00+00:00"}
            for status in ("queued", "generating", "retrying", "processing")
        }})
        module._cleanup_invalid_image_tasks()
        jobs = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]
        assert all(job["status"] == "failed" for job in jobs.values())
        assert all("新任务启动前" in job["error"] for job in jobs.values())


def test_unified_task_resume_replays_persisted_image_request() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        module._save_image_jobs({"jobs":{"old":{"status":"failed", "subject_key":"project::shot_1_2", "endpoint":"/api/shots/generate", "request":{"project_id":"project", "episode":1, "shot_number":2}, "finished_at":module._iso_now()}}})
        captured = []
        class Thread:
            def __init__(self, *, target, args, **_kwargs): captured.append((target, args))
            def start(self): return None
        original = module.threading.Thread; module.threading.Thread = Thread
        try: resumed, endpoint = module._resume_persisted_task({"project_id":"project"}, "project:project:shot_images:1:2")
        finally: module.threading.Thread = original
        assert resumed is True and endpoint == "/api/shots/generate"
        assert captured and captured[0][1][0] == "/api/shots/generate"
        assert captured[0][1][1]["generation_id"]


def test_recovery_refuses_unverified_reused_pid() -> None:
    module = load_backend()
    job = {"pid":123, "process_group":123, "owner_token":"token"}
    class Result:
        stdout = "123 /usr/bin/python unrelated.py"
    original = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: Result()
    try: assert module._persisted_image_process("job-safe", job) is None
    finally: module.subprocess.run = original


def test_recovery_refuses_verified_process_from_other_scope() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        job = {"pid":123, "process_group":123, "owner_token":"token", "service_scope":"foreign"}
        class Result:
            stdout = f"123 {module.IMAGE_TASK_SUPERVISOR} --job-id job-safe --owner-token token --service-scope foreign"
        original = module.subprocess.run
        module.subprocess.run = lambda *args, **kwargs: Result()
        try: assert module._persisted_image_process("job-safe", job) is None
        finally: module.subprocess.run = original


def test_manual_raw_model_process_is_not_classified_as_owned_orphan() -> None:
    module = load_backend()
    class Result:
        stdout = f"123 123 {module.MFLUX_FLUX2} --output {module.OUTPUT_ROOT / 'images/manual.png'}"
    original = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: Result()
    try: assert module._orphan_image_processes() == []
    finally: module.subprocess.run = original


def test_supervisor_from_another_service_scope_is_not_orphaned() -> None:
    module = load_backend()
    class Result:
        stdout = f"123 123 {module.IMAGE_TASK_SUPERVISOR} --job-id foreign --owner-token token --service-scope foreign-scope -- /bin/sleep 30"
    original = module.subprocess.run
    module.subprocess.run = lambda *args, **kwargs: Result()
    try: assert module._orphan_image_processes() == []
    finally: module.subprocess.run = original


def test_shutdown_terminates_and_persists_failed_state() -> None:
    module = load_backend()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); prepare(module, root)
        process = subprocess.Popen([str(Path(sys.executable).resolve()), "-c", "import time; time.sleep(30)"], start_new_session=True)
        module.ACTIVE_IMAGE_PROCESSES["job-shutdown"] = process
        module.ACTIVE_IMAGE_JOBS.add("job-shutdown")
        module.ACTIVE_IMAGE_SUBJECTS["subject"] = "job-shutdown"
        module._save_image_jobs({"jobs":{
            "job-shutdown":{"status":"generating", "pid":process.pid, "process_group":process.pid},
            "job-queued":{"status":"queued"}, "job-retrying":{"status":"retrying"}, "job-processing":{"status":"processing"},
            "job-completed":{"status":"completed"},
        }})
        module._shutdown_image_jobs()
        jobs = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]
        assert process.poll() is not None
        assert all(jobs[name]["status"] == "failed" and "服务关闭" in jobs[name]["error"] for name in ("job-shutdown", "job-queued", "job-retrying", "job-processing"))
        assert jobs["job-completed"]["status"] == "completed"
        assert not module.ACTIVE_IMAGE_PROCESSES and not module.ACTIVE_IMAGE_JOBS and not module.ACTIVE_IMAGE_SUBJECTS
