import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"


def load_backend(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_waiting_video_admission_requires_empty_comfy_queue(monkeypatch):
    module = load_backend("waiting_video_admission")
    monkeypatch.setattr(module, "ACTIVE_VIDEO_JOBS", set())
    monkeypatch.setattr(module, "_heavy_task_busy", lambda: False)
    for queue in (
        {"queue_running":[[0, "running"]], "queue_pending":[]},
        {"queue_running":[], "queue_pending":[[1, "pending"]]},
    ):
        monkeypatch.setattr(module, "_comfy_json", lambda _path, value=queue: value)
        assert module._waiting_video_release_window_open() is False
    monkeypatch.setattr(module, "_comfy_json", lambda _path: {"queue_running":[], "queue_pending":[]})
    assert module._waiting_video_release_window_open() is True


def test_waiting_video_admission_fails_closed_on_unknown_or_local_busy(monkeypatch):
    module = load_backend("waiting_video_admission_closed")
    monkeypatch.setattr(module, "ACTIVE_VIDEO_JOBS", {"job"})
    monkeypatch.setattr(module, "_heavy_task_busy", lambda: False)
    monkeypatch.setattr(module, "_comfy_json", lambda _path: (_ for _ in ()).throw(AssertionError("queue must not be queried")))
    assert module._waiting_video_release_window_open() is False
    monkeypatch.setattr(module, "ACTIVE_VIDEO_JOBS", set())
    monkeypatch.setattr(module, "_comfy_json", lambda _path: (_ for _ in ()).throw(OSError("offline")))
    assert module._waiting_video_release_window_open() is False


def test_waiting_memory_remains_task_state_and_projects_to_graph_queue():
    source = BACKEND.read_text(encoding="utf-8")
    assert '"waiting_memory":"queued"' in source
    assert 'status = "generating" if ready and _waiting_video_release_window_open() else "waiting_memory"' in source
