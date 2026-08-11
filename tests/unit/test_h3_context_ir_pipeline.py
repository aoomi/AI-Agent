from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "compat_h3_context_ir_pipeline_test",
    ROOT / "plugins/builtin/short_drama/backend/compat_server.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_local_media_path_accepts_nested_controlled_result_directory(monkeypatch, tmp_path):
    target = tmp_path / "assets3d" / "project-1" / "scene" / "空房间" / "blender_source.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"video")
    monkeypatch.setattr(MODULE, "OUTPUT_ROOT", tmp_path)
    subfolder = quote("assets3d/project-1/scene/空房间")
    assert MODULE._local_media_path(
        f"/api/result-media?filename=blender_source.mp4&subfolder={subfolder}"
    ) == target


@pytest.mark.parametrize(
    "url",
    [
        "/api/result-media?filename=blender_source.mp4&subfolder=../outside",
        "/api/result-media?filename=blender_source.mp4&subfolder=/tmp",
        "/api/result-media?filename=../secret&subfolder=assets3d",
    ],
)
def test_local_media_path_rejects_absolute_and_traversal_inputs(monkeypatch, tmp_path, url):
    monkeypatch.setattr(MODULE, "OUTPUT_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError, match="分镜图片不存在"):
        MODULE._local_media_path(url)


def _runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, history):
    identity = tmp_path / "identity.png"
    identity.write_bytes(b"test-image")
    comfy_input = tmp_path / "comfy-input"
    comfy_output = tmp_path / "comfy-output"
    state = {"jobs": {"job": {"status": "generating"}}}
    submitted: list[dict] = []
    cancelled: list[str] = []
    freed: list[bool] = []
    unloads: list[str] = []

    def update(job_id: str, **changes):
        state["jobs"][job_id].update(changes)
        return dict(state["jobs"][job_id])

    def comfy(path: str, payload=None, timeout=0):
        if path == "/prompt":
            submitted.append(payload)
            return {"prompt_id": f"context-{len(submitted)}"}
        return history(path, len(submitted))

    monkeypatch.setattr(MODULE, "COMFY_INPUT", comfy_input)
    monkeypatch.setattr(MODULE, "COMFY_OUTPUT", comfy_output)
    monkeypatch.setattr(MODULE, "H3_CONTEXT_IR_OUTPUT_ROOT", tmp_path / "persisted")
    monkeypatch.setattr(MODULE, "_resolve_media_input", lambda value: identity)
    monkeypatch.setattr(MODULE, "_start_comfy", lambda: None)
    monkeypatch.setattr(MODULE, "_comfy_json", comfy)
    monkeypatch.setattr(MODULE, "_update_video_job", update)
    monkeypatch.setattr(MODULE, "_load_video_jobs", lambda: state)
    monkeypatch.setattr(MODULE, "_cancel_comfy_prompt", lambda prompt_id, **kwargs: cancelled.append(str(prompt_id)) or True)
    monkeypatch.setattr(MODULE, "_terminate_ollama_model", lambda model: unloads.append(model) or True)
    monkeypatch.setattr(MODULE, "_ollama_model_loaded", lambda model: False)
    monkeypatch.setattr(MODULE, "_free_comfy_memory", lambda: freed.append(True))
    monkeypatch.setattr(MODULE.time, "sleep", lambda seconds: None)
    return state, submitted, cancelled, freed, unloads


def _success(prompt_id: str) -> dict:
    return {
        prompt_id: {
            "status": {"status_str": "success"},
            "outputs": {
                "3": {"text": ["optimized H3 prompt"]},
                "4": {"text": ['["h3-prompt-writing"]']},
                "5": {"text": ['{"optimized_prompt":"optimized H3 prompt"}']},
            },
        }
    }


def test_context_ir_success_persists_independent_stage_and_outputs(monkeypatch, tmp_path):
    state, submitted, cancelled, freed, unloads = _runtime(
        monkeypatch, tmp_path, lambda path, attempt: _success(f"context-{attempt}")
    )
    result = MODULE._optimize_h3_ref2va_prompt(
        "job", {"identity_reference_url": "ignored"}, duration=5, prompt="source prompt"
    )
    assert result == "optimized H3 prompt"
    assert len(submitted) == 1
    assert state["jobs"]["job"]["context_ir_stage"] == "completed"
    assert state["jobs"]["job"]["context_ir_prompt_id"] == "context-1"
    assert state["jobs"]["job"]["optimized_prompt"] == result
    assert all(Path(path).is_file() for path in state["jobs"]["job"]["context_ir_outputs"].values())
    assert "context-1" in cancelled
    assert unloads == [MODULE.H3_CONTEXT_IR_MODEL]
    assert freed


def test_context_ir_success_removes_owned_comfy_text_intermediates(monkeypatch, tmp_path):
    def history(path, attempt):
        output = tmp_path / "comfy-output" / "h3_context_ir"
        output.mkdir(parents=True, exist_ok=True)
        for kind, suffix in (("optimized", ".txt"), ("skills", ".json"), ("raw", ".json")):
            (output / f"job_owned_{kind}_a{attempt}_00001{suffix}").write_text("intermediate", encoding="utf-8")
        return _success(f"context-{attempt}")

    _runtime(monkeypatch, tmp_path, history)
    monkeypatch.setattr(MODULE, "uuid4", lambda: type("FixedUUID", (), {"hex":"owned"})())
    MODULE._optimize_h3_ref2va_prompt(
        "job", {"identity_reference_url":"ignored"}, duration=5, prompt="source prompt"
    )
    assert not list((tmp_path / "comfy-output").glob("h3_context_ir/job_owned_*"))


def test_context_ir_failed_prompt_retries_only_once(monkeypatch, tmp_path):
    state, submitted, cancelled, _, _ = _runtime(
        monkeypatch,
        tmp_path,
        lambda path, attempt: {f"context-{attempt}": {"status": {"status_str": "error"}}},
    )
    with pytest.raises(RuntimeError, match="Context IR执行失败"):
        MODULE._optimize_h3_ref2va_prompt(
            "job", {"identity_reference_url": "ignored"}, duration=5, prompt="source prompt"
        )
    assert len(submitted) == 2
    assert {"context-1", "context-2"}.issubset(cancelled)
    assert state["jobs"]["job"]["context_ir_attempt"] == 2


def test_context_ir_one_history_error_recovers(monkeypatch, tmp_path):
    calls = 0

    def history(path, attempt):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("transient history failure")
        return _success(f"context-{attempt}")

    _, submitted, _, _, _ = _runtime(monkeypatch, tmp_path, history)
    result = MODULE._optimize_h3_ref2va_prompt(
        "job", {"identity_reference_url": "ignored"}, duration=5, prompt="source prompt"
    )
    assert result == "optimized H3 prompt"
    assert len(submitted) == 1


def test_context_ir_timeout_does_not_submit_h3(monkeypatch, tmp_path):
    _, submitted, cancelled, _, _ = _runtime(monkeypatch, tmp_path, lambda path, attempt: {})
    monkeypatch.setattr(MODULE, "H3_CONTEXT_IR_TIMEOUT_SECONDS", 0)
    h3_calls: list[object] = []
    monkeypatch.setattr(MODULE, "_invoke_production_capability", lambda *args, **kwargs: h3_calls.append((args, kwargs)))
    target = tmp_path / "result.mp4"
    with pytest.raises(TimeoutError, match="Context IR超过硬截止时间"):
        MODULE._run_h3_context_then_ref2va(
            "job", {"identity_reference_url": "ignored"}, target, duration=5, instruction="shot"
        )
    assert len(submitted) == 1
    assert "context-1" in cancelled
    assert h3_calls == []


def test_context_ir_persistence_failure_blocks_h3(monkeypatch, tmp_path):
    _, submitted, _, _, _ = _runtime(
        monkeypatch, tmp_path, lambda path, attempt: _success(f"context-{attempt}")
    )
    monkeypatch.setattr(MODULE, "_persist_h3_context_ir_outputs", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    h3_calls: list[object] = []
    monkeypatch.setattr(MODULE, "_invoke_production_capability", lambda *args, **kwargs: h3_calls.append((args, kwargs)))
    with pytest.raises(OSError, match="disk full"):
        MODULE._run_h3_context_then_ref2va(
            "job", {"identity_reference_url": "ignored"}, tmp_path / "result.mp4", duration=5, instruction="shot"
        )
    assert len(submitted) == 1
    assert h3_calls == []


def test_context_ir_requires_readable_persisted_outputs_before_h3(monkeypatch, tmp_path):
    _, submitted, _, _, _ = _runtime(
        monkeypatch, tmp_path, lambda path, attempt: _success(f"context-{attempt}")
    )
    monkeypatch.setattr(MODULE, "_persist_h3_context_ir_outputs", lambda *args: {
        "optimized_prompt": str(tmp_path / "missing-prompt.txt"),
        "selected_skills": str(tmp_path / "missing-skills.json"),
        "raw_json": str(tmp_path / "missing-raw.json"),
    })
    h3_calls: list[object] = []
    monkeypatch.setattr(MODULE, "_invoke_production_capability", lambda *args, **kwargs: h3_calls.append((args, kwargs)))
    with pytest.raises(RuntimeError, match="Context IR持久输出不可用"):
        MODULE._run_h3_context_then_ref2va(
            "job", {"identity_reference_url":"ignored"}, tmp_path / "result.mp4", duration=5, instruction="shot"
        )
    assert len(submitted) == 1
    assert h3_calls == []


def test_context_ir_rejects_symlinked_persisted_output(monkeypatch, tmp_path):
    _, _, _, _, _ = _runtime(
        monkeypatch, tmp_path, lambda path, attempt: _success(f"context-{attempt}")
    )
    publication = tmp_path / "persisted" / "job" / "publication"
    publication.mkdir(parents=True)
    real_prompt = publication / "real-prompt.txt"
    real_prompt.write_text("disk optimized", encoding="utf-8")
    prompt_link = publication / "optimized_prompt.txt"
    prompt_link.symlink_to(real_prompt.name)
    skills = publication / "selected_skills.json"
    skills.write_text('["skill"]', encoding="utf-8")
    raw = publication / "raw_json.json"
    raw.write_text('{"optimized_prompt":"disk optimized"}', encoding="utf-8")
    monkeypatch.setattr(MODULE, "_persist_h3_context_ir_outputs", lambda *args: {
        "optimized_prompt": str(prompt_link), "selected_skills": str(skills), "raw_json": str(raw),
    })
    h3_calls: list[object] = []
    monkeypatch.setattr(MODULE, "_invoke_production_capability", lambda *args, **kwargs: h3_calls.append((args, kwargs)))
    with pytest.raises(RuntimeError, match="Context IR持久输出不可用"):
        MODULE._run_h3_context_then_ref2va(
            "job", {"identity_reference_url":"ignored"}, tmp_path / "result.mp4", duration=5, instruction="shot"
        )
    assert h3_calls == []


def test_context_ir_rejects_symlinked_publication_directory(monkeypatch, tmp_path):
    _, _, _, _, _ = _runtime(
        monkeypatch, tmp_path, lambda path, attempt: _success(f"context-{attempt}")
    )
    job_root = tmp_path / "persisted" / "job"
    real_publication = job_root / "real"
    real_publication.mkdir(parents=True)
    (real_publication / "optimized_prompt.txt").write_text("disk optimized", encoding="utf-8")
    (real_publication / "selected_skills.json").write_text('["skill"]', encoding="utf-8")
    (real_publication / "raw_json.json").write_text('{"optimized_prompt":"disk optimized"}', encoding="utf-8")
    linked_publication = job_root / "publication"
    linked_publication.symlink_to(real_publication.name, target_is_directory=True)
    monkeypatch.setattr(MODULE, "_persist_h3_context_ir_outputs", lambda *args: {
        "optimized_prompt": str(linked_publication / "optimized_prompt.txt"),
        "selected_skills": str(linked_publication / "selected_skills.json"),
        "raw_json": str(linked_publication / "raw_json.json"),
    })
    h3_calls: list[object] = []
    monkeypatch.setattr(MODULE, "_invoke_production_capability", lambda *args, **kwargs: h3_calls.append((args, kwargs)))
    with pytest.raises(RuntimeError, match="Context IR持久输出不可用"):
        MODULE._run_h3_context_then_ref2va(
            "job", {"identity_reference_url":"ignored"}, tmp_path / "result.mp4", duration=5, instruction="shot"
        )
    assert h3_calls == []


def test_context_ir_identity_copy_failure_runs_full_cleanup(monkeypatch, tmp_path):
    _, _, cancelled, freed, unloads = _runtime(monkeypatch, tmp_path, lambda path, attempt: {})
    monkeypatch.setattr(MODULE.shutil, "copy2", lambda *args: (_ for _ in ()).throw(OSError("copy failed")))
    h3_calls: list[object] = []
    monkeypatch.setattr(MODULE, "_invoke_production_capability", lambda *args, **kwargs: h3_calls.append((args, kwargs)))
    with pytest.raises(OSError, match="copy failed"):
        MODULE._run_h3_context_then_ref2va(
            "job", {"identity_reference_url":"ignored"}, tmp_path / "result.mp4", duration=5, instruction="shot"
        )
    assert cancelled == []
    assert unloads == [MODULE.H3_CONTEXT_IR_MODEL]
    assert freed == [True]
    assert h3_calls == []
    assert not (tmp_path / "comfy-input" / "short_drama_h3_context_ir").exists()


def test_context_ir_outputs_publish_as_one_complete_set(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "H3_CONTEXT_IR_OUTPUT_ROOT", tmp_path / "context-output")
    original_write = MODULE.Path.write_text
    writes = 0

    def fail_second_write(path, value, *args, **kwargs):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("second artifact failed")
        return original_write(path, value, *args, **kwargs)

    monkeypatch.setattr(MODULE.Path, "write_text", fail_second_write)
    with pytest.raises(OSError, match="second artifact failed"):
        MODULE._persist_h3_context_ir_outputs("job", "optimized", "skills", "raw")
    job_root = tmp_path / "context-output" / "job"
    assert not [path for path in job_root.iterdir() if not path.name.startswith(".")]
    assert not list(job_root.glob("*.staging"))


def test_context_ir_cancel_cancels_owned_prompt_and_blocks_h3(monkeypatch, tmp_path):
    state, submitted, cancelled, _, _ = _runtime(monkeypatch, tmp_path, lambda path, attempt: {})
    load_calls = 0

    def load_jobs():
        nonlocal load_calls
        load_calls += 1
        if load_calls >= 2:
            state["jobs"]["job"].update({"status": "cancelled", "error": "视频任务已停止"})
        return state

    monkeypatch.setattr(MODULE, "_load_video_jobs", load_jobs)
    h3_calls: list[object] = []
    monkeypatch.setattr(MODULE, "_invoke_production_capability", lambda *args, **kwargs: h3_calls.append((args, kwargs)))
    with pytest.raises(RuntimeError, match="视频任务已停止"):
        MODULE._run_h3_context_then_ref2va(
            "job", {"identity_reference_url": "ignored"}, tmp_path / "result.mp4", duration=5, instruction="shot"
        )
    assert len(submitted) == 1
    assert "context-1" in cancelled
    assert h3_calls == []


def test_context_model_must_be_unloaded_before_h3(monkeypatch, tmp_path):
    _, _, _, _, _ = _runtime(monkeypatch, tmp_path, lambda path, attempt: _success(f"context-{attempt}"))
    monkeypatch.setattr(MODULE, "_terminate_ollama_model", lambda model: False)
    monkeypatch.setattr(MODULE, "_ollama_model_loaded", lambda model: True)
    h3_calls: list[object] = []
    monkeypatch.setattr(MODULE, "_invoke_production_capability", lambda *args, **kwargs: h3_calls.append((args, kwargs)))
    with pytest.raises(RuntimeError, match="模型未卸载"):
        MODULE._run_h3_context_then_ref2va(
            "job", {"identity_reference_url": "ignored"}, tmp_path / "result.mp4", duration=5, instruction="shot"
        )
    assert h3_calls == []


def test_successful_context_output_is_the_only_prompt_submitted_to_h3(monkeypatch, tmp_path):
    state = {"jobs": {"job": {"status": "generating"}}}
    h3_calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(MODULE, "_optimize_h3_ref2va_prompt", lambda *args, **kwargs: "persisted optimized prompt")
    monkeypatch.setattr(MODULE, "_load_video_jobs", lambda: state)
    monkeypatch.setattr(MODULE, "_ollama_model_loaded", lambda model: False)
    monkeypatch.setattr(MODULE, "_require_memory", lambda amount: None)
    monkeypatch.setattr(MODULE, "_invoke_production_capability", lambda *args, **kwargs: h3_calls.append((args, kwargs)))
    result = MODULE._run_h3_context_then_ref2va(
        "job", {"identity_reference_url": "ignored"}, tmp_path / "result.mp4", duration=5, instruction="raw shot"
    )
    assert result == "persisted optimized prompt"
    assert len(h3_calls) == 1
    assert h3_calls[0][0] == ("video.shot.h3_ref2va",)
    assert h3_calls[0][1]["optimized_prompt"] == "persisted optimized prompt"
    assert "instruction" not in h3_calls[0][1]


def test_video_lifecycle_cancels_context_prompt_key():
    backend = (ROOT / "plugins/builtin/short_drama/backend/compat_server.py").read_text(encoding="utf-8")
    assert '"context_ir_prompt_id"' in backend[backend.index("def _cancel_job_comfy_prompts"):backend.index("def _cleanup_comfy_temp_inputs")]
    watchdog = backend[backend.index("def _monitor_waiting_video_jobs"):backend.index("def _recover_video_jobs")]
    recover = backend[backend.index("def _recover_video_jobs"):backend.index("def _load_resources")]
    assert "_cancel_job_comfy_prompts(job)" in watchdog
    assert recover.count("_cancel_job_comfy_prompts(job)") >= 2
    assert 'optimized_prompt=optimized_prompt' in backend
    assert 'H3 Ref2VA禁止使用未优化的原始提示词' in backend


def test_owned_comfy_prompt_cancel_requires_confirmed_queue_disappearance(monkeypatch):
    states = iter([("running", False), ("absent", False)])
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(MODULE, "_comfy_prompt_queue_details", lambda prompt_id: next(states))
    monkeypatch.setattr(MODULE, "_comfy_json", lambda path, payload=None, timeout=0: calls.append((path, payload)) or {})
    monkeypatch.setattr(MODULE.time, "sleep", lambda seconds: None)
    assert MODULE._cancel_comfy_prompt("owned", confirm_seconds=10) is True
    assert calls == [("/interrupt", {})]


def test_owned_comfy_prompt_cancel_times_out_while_still_queued(monkeypatch):
    ticks = iter([0.0, 11.0])
    monkeypatch.setattr(MODULE, "_comfy_prompt_queue_details", lambda prompt_id: ("running", False))
    monkeypatch.setattr(MODULE, "_comfy_json", lambda path, payload=None, timeout=0: {})
    monkeypatch.setattr(MODULE.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(MODULE.time, "sleep", lambda seconds: None)
    assert MODULE._cancel_comfy_prompt("owned", confirm_seconds=10) is False


def test_owned_running_prompt_does_not_interrupt_foreign_running_prompt(monkeypatch):
    ticks = iter([0.0, 11.0])
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(MODULE, "_comfy_prompt_queue_details", lambda prompt_id: ("running", True))
    monkeypatch.setattr(MODULE, "_comfy_json", lambda path, payload=None, timeout=0: calls.append((path, payload)) or {})
    monkeypatch.setattr(MODULE.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(MODULE.time, "sleep", lambda seconds: None)
    assert MODULE._cancel_comfy_prompt("owned", confirm_seconds=10) is False
    assert calls == []


def test_owned_comfy_prompt_cancel_failure_is_not_reported_as_stopped(monkeypatch):
    store = {
        "jobs": {
            "job": {
                "job_id": "job", "status": "generating", "stage": "h3_rv2v",
                "subject_key": "tenant:user:project:1:1", "queued_at": MODULE._iso_now(),
                "comfy_prompt_id": "owned",
            }
        }
    }
    cancelled_tickets: list[str] = []
    monkeypatch.setattr(MODULE, "_load_video_jobs", lambda: store)
    monkeypatch.setattr(MODULE, "_save_video_jobs", lambda value: None)
    monkeypatch.setattr(MODULE, "_cancel_job_comfy_prompts", lambda job, **kwargs: False)
    monkeypatch.setattr(MODULE.RESOURCE_SCHEDULER, "cancel_job", lambda job_id: cancelled_tickets.append(job_id))
    MODULE.ACTIVE_VIDEO_JOBS.add("job")
    stopped = MODULE._stop_video_generation(requested_job_id="job")
    assert stopped == []
    assert cancelled_tickets == []
    assert store["jobs"]["job"]["status"] == "generating"
    assert store["jobs"]["job"]["stage"] == "cancel_pending"
    assert store["jobs"]["job"]["cancel_requested_at"]
    assert "job" in MODULE.ACTIVE_VIDEO_JOBS
    MODULE.ACTIVE_VIDEO_JOBS.discard("job")


def test_terminal_orphan_recovery_waits_before_restoring_terminal(monkeypatch):
    body = {"tenant_id": "tenant", "user_id": "user", "project_id": "project", "episode": 1, "shot_number": 1}
    store = {"jobs": {"job": {"status": "generating", "stage": "cancel_pending", "request": body, "comfy_prompt_id": "owned"}}}
    events: list[str] = []

    @contextmanager
    def claim(*args, **kwargs):
        events.append("ticket_acquired")
        yield
        events.append("ticket_released")

    def update(job_id, **changes):
        events.append(f"commit:{changes.get('status')}")
        store["jobs"][job_id].update(changes)
        return dict(store["jobs"][job_id])

    monkeypatch.setattr(MODULE, "_claim_production_resource", claim)
    monkeypatch.setattr(MODULE, "_load_video_jobs", lambda: store)
    monkeypatch.setattr(MODULE, "_wait_for_video_comfy_prompts", lambda job_id, prompts: events.append("queue_absent"))
    monkeypatch.setattr(MODULE, "_update_video_job", update)
    MODULE.ACTIVE_VIDEO_JOBS.add("job")
    MODULE.ACTIVE_VIDEO_SUBJECTS[MODULE._video_key(body)] = "job"
    MODULE._recover_terminal_video_prompt("job", body, "cancelled", "cancelled", "视频任务已停止")
    assert events == ["ticket_acquired", "queue_absent", "commit:cancelled", "ticket_released"]
    assert store["jobs"]["job"]["status"] == "cancelled"
    assert "job" not in MODULE.ACTIVE_VIDEO_JOBS
