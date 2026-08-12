import importlib.util
from pathlib import Path


def test_restart_requeues_only_never_started_agent_jobs(monkeypatch, tmp_path) -> None:
    path = Path("plugins/builtin/short_drama/backend/compat_server.py")
    spec = importlib.util.spec_from_file_location("agent_recovery_backend", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    store = {"jobs": {"queued":{"status":"queued"}, "running":{"status":"running"}, "done":{"status":"completed"}}}
    started = []; saved = []
    monkeypatch.setattr(module, "_load_agent_jobs", lambda: store)
    monkeypatch.setattr(module, "_save_agent_jobs", lambda value: saved.append(value))
    monkeypatch.setattr(module, "_start_agent_job", lambda job_id: started.append(job_id))

    module._recover_agent_jobs()

    assert started == ["queued"]
    assert store["jobs"]["running"]["status"] == "failed"
    assert "显式重试" in store["jobs"]["running"]["error"]
    assert store["jobs"]["done"]["status"] == "completed"
    assert len(saved) == 1
