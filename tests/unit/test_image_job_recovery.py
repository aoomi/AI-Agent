import ast
import importlib.util
import json
import math
import re
import sys
import tempfile
import threading
import types
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "plugins/builtin/short_drama/backend/compat_server.py"
FRONTEND = ROOT / "plugins/builtin/short_drama/frontend/App.vue"


def test_no_text_prop_prompt_removes_positive_glyph_cues_but_keeps_material_details() -> None:
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_sanitize_no_text_asset_prompt"
    )
    namespace: dict[str, object] = {"re": re}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(BACKEND), "exec"), namespace)
    sanitize = namespace["_sanitize_no_text_asset_prompt"]

    result = sanitize("一张泛黄信纸，表面有娟秀笔迹或手指按出的指纹压痕，边缘微卷，无文字干扰")

    assert "娟秀笔迹" not in result
    assert "指纹压痕" in result
    assert "边缘微卷" in result
    assert "无文字干扰" in result
    assert result.endswith("道具表面必须完全无字、无字形、无标签、无标志、无水印。")
    assert "铭文" not in sanitize("古铜器表面带铭文且无人持握，金属氧化纹理")
    assert "金属氧化纹理" in sanitize("古铜器表面带铭文且无人持握，金属氧化纹理")
    assert "禁止出现任何文字" in sanitize("纯灰背景，禁止出现任何文字")
    assert "文字不得出现" in sanitize("纯灰背景，文字不得出现")


def load_backend_for_character_http():
    spec = importlib.util.spec_from_file_location("compat_server_character_http_test", BACKEND)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_post_generation_validation_keeps_durable_job_alive(monkeypatch) -> None:
    module = load_backend_for_character_http()
    release = threading.Event()
    updates: list[dict] = []
    checks: list[str] = []

    def validator(_image):
        assert release.wait(1)
        return True, "accepted"

    monkeypatch.setattr(module, "_assert_image_job_runnable", lambda job_id: checks.append(job_id))
    monkeypatch.setattr(module, "_update_image_job", lambda job_id, **values: updates.append({"job_id":job_id, **values}))
    timer = threading.Timer(0.04, release.set)
    timer.start()
    try:
        result = module._run_image_validation(
            "job-scene", "scene_validation", validator, {"url":"unused"},
            timeout_seconds=1, heartbeat_seconds=0.01,
        )
    finally:
        timer.cancel()

    assert result == (True, "accepted")
    assert checks.count("job-scene") >= 2
    assert sum(item.get("phase") == "scene_validation" for item in updates) >= 2
    assert all(item.get("pid") is None for item in updates)


def test_post_generation_validation_observes_stop_and_has_bounded_timeout(monkeypatch) -> None:
    module = load_backend_for_character_http()
    release = threading.Event()
    checks = 0
    terminated: list[str] = []
    cancelled: list[str] = []

    def assert_runnable(_job_id):
        nonlocal checks
        checks += 1
        if checks >= 2:
            raise RuntimeError("图片任务已停止")

    monkeypatch.setattr(module, "_assert_image_job_runnable", assert_runnable)
    monkeypatch.setattr(module, "_update_image_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module.RESOURCE_SCHEDULER, "cancel_job", lambda job_id: cancelled.append(job_id) or 1)
    monkeypatch.setattr(
        module, "_terminate_ollama_model",
        lambda model: terminated.append(model) or release.set() or True,
    )
    with pytest.raises(RuntimeError, match="图片任务已停止"):
        module._run_image_validation(
            "job-stop", "prop_validation", lambda _image: release.wait(1), {},
            timeout_seconds=1, heartbeat_seconds=0.01,
        )
    release.set()
    assert terminated == ["llava:latest"]
    assert cancelled == ["job-stop"]

    monkeypatch.setattr(module, "_assert_image_job_runnable", lambda _job_id: None)
    release = threading.Event()
    with pytest.raises(RuntimeError, match="图片后验收超时.*scene_validation"):
        module._run_image_validation(
            "job-timeout", "scene_validation", lambda _image: release.wait(1), {},
            timeout_seconds=0.03, heartbeat_seconds=0.01,
        )
    release.set()
    assert terminated == ["llava:latest", "llava:latest"]
    assert cancelled == ["job-stop", "job-timeout"]


def test_scene_and_prop_validation_resource_tickets_are_owned_by_image_job() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    helper = backend[backend.index("def _run_image_validation"):backend.index("def _validate_prop_asset")]
    prop = backend[backend.index("def _validate_prop_asset"):backend.index("def _validate_scene_asset")]
    scene = backend[backend.index("def _validate_scene_asset"):backend.index("def _face_pose_angles")]
    route = backend[backend.index('if parsed.path == "/api/characters/generate" and asset_kind == "prop"'):]

    assert "RESOURCE_SCHEDULER.cancel_job(job_id)" in helper
    assert '"audit", job_id or f"prop-audit-' in prop
    assert '"audit", job_id or f"scene-audit-' in scene
    assert "timeout=IMAGE_VALIDATION_TIMEOUT_SECONDS" in prop
    assert "timeout=IMAGE_VALIDATION_TIMEOUT_SECONDS" in scene
    assert "_validate_prop_asset(candidate, job_id=job_id)" in route
    assert "_validate_scene_asset(candidate, job_id=job_id)" in route


def test_post_comfy_memory_wait_is_bounded_and_keeps_job_cancellable(monkeypatch) -> None:
    module = load_backend_for_character_http()
    samples = iter([(False, {"available_gb":60.0,"required_gb":42.0,"reserve_gb":35.0}), (True, {"available_gb":80.0,"required_gb":42.0,"reserve_gb":35.0})])
    updates: list[dict] = []
    module.LAST_COMFY_FREE_AT = 100.0
    clock = iter([101.0, 101.0, 102.0])
    monkeypatch.setattr(module, "_memory_ready", lambda _estimated: next(samples))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(module, "_assert_image_job_runnable", lambda job_id: updates.append({"checked":job_id}))
    monkeypatch.setattr(module, "_update_image_job", lambda job_id, **values: updates.append({"job_id":job_id, **values}))

    module._wait_for_post_comfy_memory(42 * module.GIB, job_id="job-1", timeout_seconds=10)

    assert any(item.get("status") == "waiting_memory" for item in updates)
    assert any(item.get("checked") == "job-1" for item in updates)
    assert any(item.get("status") == "processing" and item.get("phase") == "memory_ready" for item in updates)


def test_memory_wait_only_applies_to_recent_comfy_release_and_times_out(monkeypatch) -> None:
    module = load_backend_for_character_http()
    blocked = (False, {"available_gb":60.0,"required_gb":42.0,"reserve_gb":35.0})
    immediate: list[int] = []
    monkeypatch.setattr(module, "_memory_ready", lambda _estimated: blocked)
    monkeypatch.setattr(module, "_require_memory", lambda estimated: immediate.append(estimated))
    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("unavailable")))
    module.LAST_COMFY_FREE_AT = 0.0
    module._wait_for_post_comfy_memory(42 * module.GIB)
    assert immediate == [42 * module.GIB]

    module.LAST_COMFY_FREE_AT = 100.0
    clock = iter([101.0, 101.0, 103.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    with pytest.raises(RuntimeError, match="等待Comfy释放超时"):
        module._wait_for_post_comfy_memory(42 * module.GIB, timeout_seconds=1)


def test_memory_wait_recovers_idle_comfy_cache_after_service_restart(monkeypatch) -> None:
    module = load_backend_for_character_http()
    samples = iter([(False, {"available_gb":60.0,"required_gb":42.0,"reserve_gb":35.0}), (True, {"available_gb":80.0,"required_gb":42.0,"reserve_gb":35.0})])
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return b'{"queue_running":[],"queue_pending":[]}'
    module.LAST_COMFY_FREE_AT = 0.0
    clock = iter([100.0, 100.0, 101.0])
    monkeypatch.setattr(module, "_memory_ready", lambda _estimated: next(samples))
    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(module, "_free_comfy_memory", lambda: setattr(module, "LAST_COMFY_FREE_AT", 100.0))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module._wait_for_post_comfy_memory(42 * module.GIB, timeout_seconds=10)


def test_qwen_character_paths_use_bounded_post_comfy_memory_handshake() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    repair = backend.split("def _repair_schnell_output_with_qwen", 1)[1].split("def _reference_path", 1)[0]
    variant = backend.split("def _generate_qwen_character_variant", 1)[1].split("def _latest_completed_asset_image_url", 1)[0]

    assert "_wait_for_post_comfy_memory(60 * GIB, job_id=job_id)" in repair
    assert "_require_memory(60 * GIB)" not in repair
    assert "_wait_for_post_comfy_memory(60 * GIB, job_id=job_id)" in variant
    assert "_require_memory(60 * GIB)" not in variant


def test_character_frame_gate_requires_numeric_margin_evidence() -> None:
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_verified_character_frame_margins"
    )
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(BACKEND), "exec"), namespace)
    verify = namespace["_verified_character_frame_margins"]

    assert verify({"normalized_variant_margins": True})[:2] == (False, False)
    assert verify({
        "normalized_variant_margins": True,
        "deterministic_frame_metrics": {
            "source": "yolo_person_box_fallback",
            "top_margin_ratio": 0.09,
            "bottom_margin_ratio": 0.05,
            "top_margin_at_least_8_percent": True,
            "bottom_margin_at_least_3_percent": True,
        },
    })[:2] == (False, False)
    assert verify({
        "normalized_variant_margins": True,
        "deterministic_frame_metrics": {
            "source": "grabcut_person_silhouette",
            "top_margin_ratio": 0.079999,
            "bottom_margin_ratio": 0.03,
            "top_margin_at_least_8_percent": True,
            "bottom_margin_at_least_3_percent": True,
        },
    })[:2] == (False, True)
    assert verify({
        "normalized_variant_margins": True,
        "deterministic_frame_metrics": {
            "source": "grabcut_person_silhouette",
            "top_margin_ratio": 0.09,
            "bottom_margin_ratio": 0.05,
            "top_margin_at_least_8_percent": True,
            "bottom_margin_at_least_3_percent": True,
        },
    })[:2] == (True, True)


def test_front_full_orientation_uses_deterministic_pose_instead_of_vlm_false_negative() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    assert 'deterministic_orientation\n        if target_pose == "front_full"' in backend
    branch = backend.rsplit('baseline_required_checks = (', 1)[1].split(')', 1)[0]
    assert '"correct_orientation"' in branch
    assert '"required_928x1664"' in branch
    assert '"deterministic_full_frame"' in branch
    assert "*CHARACTER_FULL_BODY_ANATOMY_CHECKS" in branch
    anatomy_contract = backend[backend.index("CHARACTER_FULL_BODY_ANATOMY_CHECKS = ("):backend.index("def _character_variant_required_checks")]
    assert '"hands_anatomically_valid"' in anatomy_contract
    assert '"feet_anatomically_valid"' in anatomy_contract
    assert '"no_fused_missing_or_extra_limbs_or_digits"' in anatomy_contract
    assert '"plain_background"' not in branch
    assert '"exactly_one_person"' not in branch


def test_character_normalizer_measures_silhouette_instead_of_trusting_detector_box() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    normalizer = backend[backend.index("def _normalize_character_variant_margins"):backend.index("def _flux_identity_prompt")]
    assert "cv2.grabCut" in normalizer
    assert '"top_margin_ratio"' in normalizer
    assert '"bottom_margin_ratio"' in normalizer
    assert 'target_h=1664*0.86' in normalizer
    assert 'top=int(round(ry-1664*0.09))' in normalizer
    assert 'normalized_margin_contract_failed' in normalizer
    assert 'foreground_segmentation_failed' in normalizer
    assert 'yolo_person_box_fallback' not in normalizer


def test_character_normalizer_fails_closed_when_segmentation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_normalize_character_variant_margins"
    )
    script = next(
        node.value for node in ast.walk(function)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "from ultralytics import YOLO" in node.value
    )

    class FakeBoxes:
        cls = [0]
        conf = [0.9]
        xyxy = [[100.0, 100.0, 800.0, 1500.0]]

    class FakeYOLO:
        def __init__(self, _model: str) -> None:
            pass

        def __call__(self, _source: str, *, verbose: bool):
            return [types.SimpleNamespace(boxes=FakeBoxes())]

    def fail_grabcut(*_args, **_kwargs):
        raise RuntimeError("forced-grabcut-failure")

    fake_cv2 = types.SimpleNamespace(
        imread=lambda _source: types.SimpleNamespace(shape=(1664, 928, 3)),
        grabCut=fail_grabcut,
        GC_INIT_WITH_RECT=0,
    )
    fake_numpy = types.SimpleNamespace(
        zeros=lambda _shape, _dtype: object(),
        uint8=object(),
        float64=object(),
        floor=math.floor,
        ceil=math.ceil,
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)
    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=FakeYOLO))
    monkeypatch.setattr(sys, "argv", ["normalizer", "/tmp/not-written.png"])

    with pytest.raises(RuntimeError, match="foreground_segmentation_failed:RuntimeError:forced-grabcut-failure"):
        exec(compile(script, "<forced-segmentation-failure>", "exec"), {})


def test_character_full_frame_candidate_removes_failed_output(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_prepare_character_full_frame_candidate"
    )
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(BACKEND), "exec"), namespace)
    prepare = namespace["_prepare_character_full_frame_candidate"]
    with tempfile.TemporaryDirectory() as directory:
        candidate = Path(directory) / "candidate.png"
        candidate.write_bytes(b"failed-candidate")
        monkeypatch.setitem(prepare.__globals__, "_local_media_path", lambda _url: candidate)
        monkeypatch.setitem(
            prepare.__globals__, "_normalize_character_variant_margins",
            lambda _path: (_ for _ in ()).throw(RuntimeError("foreground_segmentation_failed")),
        )
        normalized, evidence = prepare({"url": "/candidate.png"})
        assert normalized is False
        assert evidence["normalization_failed"] is True
        assert evidence["source_removed"] is True
        assert not candidate.exists()


def test_character_baseline_normalization_failure_retries_in_formal_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name in {"_prepare_character_full_frame_candidate", "_run_character_full_frame_candidate_loop"}
    ]
    namespace: dict[str, object] = {"json": __import__("json")}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(BACKEND), "exec"), namespace)
    run_loop = namespace["_run_character_full_frame_candidate_loop"]
    attempts = []
    removed = []

    def prepare(candidate: dict):
        if candidate["id"] < 3:
            removed.append(candidate["id"])
            return False, {"normalization_failed": True, "source_removed": True}
        candidate["normalized_variant_margins"] = True
        return True, {"source": "grabcut_person_silhouette"}

    monkeypatch.setitem(run_loop.__globals__, "_prepare_character_full_frame_candidate", prepare)
    monkeypatch.setitem(run_loop.__globals__, "_local_media_path", lambda _url: types.SimpleNamespace(unlink=lambda **_kwargs: None))

    def retry(retry_number: int, _evidence: str):
        attempts.append(retry_number)
        return {"id": retry_number, "url": f"/{retry_number}.png"}

    image, _evidence, count = run_loop(
        {"id": 1, "url": "/1.png"}, generate_retry=retry,
        validate_candidate=lambda _candidate: (True, '{"valid":true}'), max_attempts=3,
    )
    assert image["id"] == 3
    assert count == 3
    assert attempts == [2, 3]
    assert removed == [1, 2]


def test_character_baseline_last_normalization_failure_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_run_character_full_frame_candidate_loop")
    namespace: dict[str, object] = {"json": __import__("json")}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(BACKEND), "exec"), namespace)
    run_loop = namespace["_run_character_full_frame_candidate_loop"]
    monkeypatch.setitem(
        run_loop.__globals__, "_prepare_character_full_frame_candidate",
        lambda _candidate: (False, {"normalization_failed": True, "source_removed": True}),
    )
    retries = []
    with pytest.raises(RuntimeError, match="character_full_frame_candidates_exhausted"):
        run_loop(
            {"url": "/1.png"}, generate_retry=lambda number, _evidence: retries.append(number) or {"url": f"/{number}.png"},
            validate_candidate=lambda _candidate: (True, ""), max_attempts=3,
        )
    assert retries == [2, 3]


@pytest.mark.parametrize("successful_attempt,expected_status", [
    (1, 200), (2, 200), (3, 200), (None, 502), ("validation_failure", 502),
    ("hands_failure", 502), ("feet_failure", 502), ("no_fused_failure", 502),
])
@pytest.mark.parametrize("project_id", ["bug038-http-p1", "bug038-http-p2"])
def test_character_baseline_http_retries_cleanup_and_terminal_state(
    monkeypatch: pytest.MonkeyPatch, successful_attempt: int | str | None, expected_status: int, project_id: str,
) -> None:
    module = load_backend_for_character_http()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        module.OUTPUT_ROOT = root
        module.IMAGE_JOBS_FILE = root / "image-jobs.json"
        module.PROJECTS_FILE = root / "projects.json"
        module.PROJECT_SNAPSHOTS_DIR = root / "snapshots"
        module.ACTIVE_IMAGE_JOBS.clear(); module.ACTIVE_IMAGE_SUBJECTS.clear(); module.ACTIVE_IMAGE_WORKERS.clear()
        module.PROJECTS_FILE.write_text(json.dumps({"projects": []}), encoding="utf-8")
        generated: list[Path] = []

        def generate(_capability: str, **_kwargs):
            number = len(generated) + 1
            target = root / "images" / f"candidate-{number}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f"candidate-{number}".encode())
            generated.append(target)
            return {"url": f"/api/result-media?filename={target.name}&subfolder=images", "filename": target.name, "subfolder": "images"}

        def normalize(path: Path):
            number = int(path.stem.rsplit("-", 1)[-1])
            if successful_attempt not in {"validation_failure", "hands_failure", "feet_failure", "no_fused_failure"} and number != successful_attempt:
                raise RuntimeError("foreground_segmentation_failed:forced-http-test")
            return {
                "source": "grabcut_person_silhouette", "top_margin_ratio": 0.09, "bottom_margin_ratio": 0.05,
                "top_margin_at_least_8_percent": True, "bottom_margin_at_least_3_percent": True,
                "output_width": 928, "output_height": 1664,
            }

        valid_evidence = json.dumps({
            "exactly_one_person": True, "correct_orientation": True, "top_margin_at_least_8_percent": True,
            "bottom_margin_at_least_3_percent": True, "plain_background": True, "required_928x1664": True,
            "deterministic_full_frame": True,
            "hands_anatomically_valid": True, "feet_anatomically_valid": True,
            "no_fused_missing_or_extra_limbs_or_digits": True,
        })
        anatomy_failure_field = {
            "hands_failure":"hands_anatomically_valid",
            "feet_failure":"feet_anatomically_valid",
            "no_fused_failure":"no_fused_missing_or_extra_limbs_or_digits",
        }.get(successful_attempt)
        anatomy_failure_verdict = json.loads(valid_evidence)
        if anatomy_failure_field:
            anatomy_failure_verdict[anatomy_failure_field] = False
        anatomy_failure_evidence = json.dumps(anatomy_failure_verdict)
        monkeypatch.setattr(module, "_invoke_production_capability", generate)
        monkeypatch.setattr(module, "_normalize_character_variant_margins", normalize)
        monkeypatch.setattr(
            module, "_validate_character_variant",
            lambda *_args, **_kwargs: (
                (False, '{"correct_orientation":false,"plain_background":false}')
                if successful_attempt == "validation_failure"
                else (False, anatomy_failure_evidence)
                if anatomy_failure_field
                else (True, valid_evidence)
            ),
        )
        monkeypatch.setattr(
            module, "_local_media_path",
            lambda url: root / "images" / str(url).split("filename=", 1)[1].split("&", 1)[0],
        )
        server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        body = json.dumps({
            "project_id": project_id, "name": "苏璃", "asset_subject": "苏璃", "asset_kind": "character",
            "asset_phase": "baseline", "width": 928, "height": 1664, "prompt": "女性，中国人，0度正面全身",
        }).encode()
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/characters/generate", data=body,
            headers={"Content-Type": "application/json", "X-Production-Dispatched": "1"}, method="POST",
        )
        try:
            if expected_status == 200:
                with urlopen(request, timeout=10) as response:
                    payload = json.loads(response.read())
                    assert response.status == 200
                assert payload["validation_attempts"] == successful_attempt
                assert payload["image"]["validation_attempts"] == successful_attempt
            else:
                with pytest.raises(HTTPError) as captured:
                    urlopen(request, timeout=10)
                assert captured.value.code == 502
                payload = json.loads(captured.value.read())
                assert "自动生成3次仍未通过" in payload["error"]
                assert "{" not in payload["error"]
                assert payload["validation_attempts"] == 3
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        actual_attempts = successful_attempt if isinstance(successful_attempt, int) else 3
        assert len(generated) == actual_attempts
        assert [path.exists() for path in generated] == ([False] * (actual_attempts - 1) + [True] if isinstance(successful_attempt, int) else [False] * 3)
        jobs = json.loads(module.IMAGE_JOBS_FILE.read_text())["jobs"]
        terminal = next(iter(jobs.values()))
        assert terminal["validation_attempts"] == actual_attempts
        assert terminal["project_id"] == project_id
        assert terminal["subject_key"].startswith(f"{project_id}:")
        assert terminal["status"] == ("completed" if expected_status == 200 else "failed")


def test_character_variant_http_rejects_each_anatomy_gate_for_every_full_body_pose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_backend_for_character_http()
    poses = ("left_45_full", "right_45_full", "side_90_full", "back_full")
    anatomy_checks = (
        "hands_anatomically_valid",
        "feet_anatomically_valid",
        "no_fused_missing_or_extra_limbs_or_digits",
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        baseline = root / "images" / "baseline.png"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_bytes(b"baseline")
        module.OUTPUT_ROOT = root
        module.IMAGE_JOBS_FILE = root / "image-jobs.json"
        module.PROJECTS_FILE = root / "projects.json"
        module.PROJECT_SNAPSHOTS_DIR = root / "snapshots"
        module.ACTIVE_IMAGE_JOBS.clear(); module.ACTIVE_IMAGE_SUBJECTS.clear(); module.ACTIVE_IMAGE_WORKERS.clear()
        module.PROJECTS_FILE.write_text(json.dumps({"projects": []}), encoding="utf-8")
        case = {"pose": poses[0], "failed_check": None, "generated": []}

        def generate(_capability: str, **_kwargs):
            target = root / "images" / f"{case['pose']}-{case['failed_check'] or 'valid'}-{len(case['generated']) + 1}.png"
            target.write_bytes(b"candidate")
            case["generated"].append(target)
            return {"url": f"/api/result-media?filename={target.name}&subfolder=images", "filename": target.name, "subfolder": "images"}

        def validate(_reference_url: str, _image: dict, target_pose: str, _clothing_url: str):
            required = module._character_variant_required_checks(target_pose, True)
            verdict = {key: True for key in required}
            failed_check = case["failed_check"]
            if failed_check:
                verdict[failed_check] = False
            return module._character_variant_verdict_passes(verdict, target_pose, True), json.dumps(verdict)

        monkeypatch.setattr(module, "_invoke_production_capability", generate)
        monkeypatch.setattr(module, "_reference_path", lambda _url: baseline)
        monkeypatch.setattr(module, "_prepare_character_full_frame_candidate", lambda _image: (True, {"source":"grabcut_person_silhouette"}))
        monkeypatch.setattr(module, "_validate_character_variant", validate)
        monkeypatch.setattr(
            module, "_local_media_path",
            lambda url: root / "images" / str(url).split("filename=", 1)[1].split("&", 1)[0],
        )
        server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            for pose in poses:
                for failed_check in (*anatomy_checks, None):
                    case.update({"pose": pose, "failed_check": failed_check, "generated": []})
                    body = json.dumps({
                        "project_id": f"bug038-{pose}-{failed_check or 'valid'}",
                        "name": "苏璃", "asset_subject": f"苏璃-{pose}-{failed_check or 'valid'}",
                        "asset_kind": "character", "asset_phase": "variant", "target_pose": pose,
                        "width": 928, "height": 1664, "prompt": "中国女性，固定角度全身",
                        "references": [{"url":"/api/result-media?filename=baseline.png&subfolder=images"}],
                        "clothing_reference_url":"/api/result-media?filename=baseline.png&subfolder=images",
                    }).encode()
                    request = Request(
                        f"http://127.0.0.1:{server.server_port}/api/characters/generate", data=body,
                        headers={"Content-Type":"application/json", "X-Production-Dispatched":"1"}, method="POST",
                    )
                    if failed_check:
                        with pytest.raises(HTTPError) as captured:
                            urlopen(request, timeout=10)
                        assert captured.value.code == 502
                        assert len(case["generated"]) == 2
                        assert all(not path.exists() for path in case["generated"])
                    else:
                        with urlopen(request, timeout=10) as response:
                            payload = json.loads(response.read())
                            assert response.status == 200
                        assert payload["image"]["validation_passed"] is True
                        assert len(case["generated"]) == 1
                        assert case["generated"][0].exists()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_flux_scene_prop_variants_force_klein9b_cfg_1_5_and_20_steps() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    branch = backend.split('if references and asset_phase == "variant" and asset_kind in {"scene", "prop"}:', 1)[1].split("else:", 1)[0]
    assert 'guidance=1.5, steps=20' in branch
    assert '"cfg":1.5, "steps":20' in branch
    assert 'model=ASSET_3D_KLEIN9B_MODEL, base_model="flux2-klein-9b", quantize=8' in branch
    assert '"generation_workflow":"FLUX.2 Klein 9B MLX 8-bit"' in branch
    prop_retry = backend.split('name=f"{name}_no_person_retry"', 1)[1].split('if asset_phase == "baseline"', 1)[0]
    scene_retry = backend.split('name=f"{name}_empty_scene_retry_{validation_attempt + 2}"', 1)[1].split('if asset_phase == "baseline"', 1)[0]
    for retry in (prop_retry, scene_retry):
        assert 'guidance=1.5, steps=20' in retry
        assert 'model=ASSET_3D_KLEIN9B_MODEL, base_model="flux2-klein-9b", quantize=8' in retry
        assert 'if references and asset_phase == "variant"' in retry
    final_metadata = backend.split('if references and asset_phase == "variant" and asset_kind in {"scene", "prop"}:', 2)[2].split("if required_text:", 1)[0]
    for token in ('"generation_workflow":"FLUX.2 Klein 9B MLX 8-bit"', '"workflow_mode":"direct_fixed_angle_no_qwen"', '"base_model":"flux2-klein-9b"', '"quantization":"8-bit"', '"cfg":1.5', '"steps":20'):
        assert token in final_metadata


def test_qwen_character_dossier_supports_left_right_45_and_command_stable_retry_seed() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    frontend = FRONTEND.read_text(encoding="utf-8")
    qwen = backend.split("def _generate_qwen_character_variant(", 1)[1].split("def _generate_ipadapter_image", 1)[0]
    for pose in ("left_45_full", "right_45_full"):
        assert f'"{pose}"' in qwen
    assert 'character_sheet_urls: list[str] | None = None' in qwen
    assert 'graph["14"]["inputs"]["image3"]' in qwen
    assert 'seed_material = identity_source.read_bytes() + target_pose.encode("utf-8") + str(prompt).encode("utf-8")' in qwen
    assert 'fixed_seed = int(hashlib.sha256(seed_material).hexdigest()[:8], 16)' in qwen
    assert 'graph["19"]["inputs"]["seed"] = fixed_seed' in qwen
    assert 'sheet_input.unlink(missing_ok=True)' in qwen
    assert 'except Exception:\n        identity_input.unlink(missing_ok=True)' in qwen
    assert qwen.index('except Exception:\n        identity_input.unlink(missing_ok=True)') < qwen.index('angle_prompt = (')
    assert 'character_sheet_reference_count' in qwen
    assert 'character_sheet_urls=[str(item.get("url") or "") for item in references[1:]' in backend
    assert 'label:"左45°全身"' in frontend and 'label:"右45°全身"' in frontend
    assert 'Maintain consistent character identity and costume details across all angles' in frontend
    assert 'slide.variant?.status === "waiting_confirmation"' in frontend
    assert 'variant.status = "waiting_confirmation"' in frontend
    assert 'asset.status === "confirmed" && asset !== variant' in frontend
    assert 'if (variant.status === "waiting_confirmation") return' in frontend
    assert 'if (item.status !== "confirmed") await generateAssetVariantsFromConfirmedBaseline(kind, item)' in frontend
    generator = backend.split("def _generate_image(", 1)[1].split("def _klein9b_houtu_loras", 1)[0]
    assert 'command.extend(["--guidance", str(float(guidance))])' in generator
    assert '"--steps", str(effective_steps)' in generator


def test_stale_image_jobs_are_failed_and_resumable() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    frontend = FRONTEND.read_text(encoding="utf-8")

    assert "ACTIVE_IMAGE_JOBS: set[str] = set()" in backend
    assert "ACTIVE_IMAGE_PROCESSES" in backend
    assert "def _recover_image_jobs()" in backend
    assert "def _monitor_image_jobs()" in backend
    assert "看门狗已回收无实际进程的图片任务" in backend
    assert "_terminate_process_tree" in backend
    assert "applyInterruptedStageRecovery(resumeStages)" in frontend
    resume = frontend[frontend.index("function applyInterruptedStageRecovery"):frontend.index("type OutlineStageData")]
    assert "generateAllAssetImages()" not in resume
    assert "上次资产任务已中断，请点击生成图片继续" in resume
    for call in ("generateOutline(", "generateScripts(", "generateStoryboards(", "generateShotImages(", "generateShotVideos(", "mergeEpisodes(", "auditFinalEpisodes(", "runUpscale(", "createExports("):
        assert call not in resume
    assert '"active_job" in payload' in frontend
    assert 'item.generation_nonce = activeJob.slice' in frontend
    assert 'includes("图片任务已中断")' in frontend
    assert 'APPLICATION_ROOT / "output"' in backend
    assert "Drama_Pipeline_ceshi/output" not in backend


def test_image_jobs_have_process_heartbeat_timeout_and_single_retry() -> None:
    backend = BACKEND.read_text(encoding="utf-8")

    assert '"job_id":job_id' in backend
    assert '"heartbeat_at":_iso_now()' in backend
    assert "IMAGE_TASK_TIMEOUT_SECONDS" in backend
    assert "IMAGE_QUEUE_TIMEOUT_SECONDS" in backend
    assert "max_attempts: int = 2" in backend
    assert "for attempt in range(max(1, max_attempts))" in backend
    assert "start_new_session=True" in backend
    assert "os.killpg" in backend
    assert "_cleanup_invalid_image_tasks()" in backend
    assert "_recover_image_jobs()" in backend
    assert 'status="retrying" if attempt < max_attempts - 1 else "failed"' in backend
    assert 'if attempt < max_attempts - 1: continue' in backend
    assert "job_id = str(uuid4())" in backend
    assert '"request_name":request_name' in backend
    assert "_save_image_jobs(jobs)\n                ACTIVE_IMAGE_JOBS.add(job_id)" in backend
    assert "def _persisted_image_process" in backend
    assert "IMAGE_TASK_SUPERVISOR" in backend
    assert 'if job.get("status") == "failed"' in backend
    assert "def _shutdown_image_jobs" in backend
    assert "HEAVY_TASK_LOCK = threading.RLock()" in backend


def test_live_image_job_keeps_asset_timer_running() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert 'profiles.some(item => item.status === "generating") ? "generating"' in source
    assert 'if (/道具资产验收失败/.test(message))' in source
    assert '道具图未通过：${failed.join("、")}，请继续生成' in source


def test_uploaded_asset_views_drive_multireference_storyboards() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    frontend = FRONTEND.read_text(encoding="utf-8")

    assert "def _generate_multireference_shot" in backend
    assert 'item.get("usage") != "audit_only"' in backend
    assert 'usage=face_primary as the sole face, makeup, hairline, close-up expression and lip-shape identity source' in backend
    assert 'usage=angle_continuity only to preserve side/back body silhouette' in backend
    assert 'usage=clothing_body only for body build' in backend
    assert '"identity_face_audit"' in backend
    assert 'identity_missing_or_duplicated' in backend
    assert 'visible_face_asymmetry' in backend
    assert "def _apply_storyboard_face_lock" in backend
    assert '"identity_lock":"single_front_face_primary"' in backend
    assert 'stage="storyboard_face_lock"' in backend
    assert 'hands_anatomically_valid' in backend
    assert 'body_anatomically_valid' in backend
    assert 'faces_anatomically_valid' in backend
    assert "def _audit_shot_consistency" in backend
    assert 'parsed.path in {"/api/shots/generate", "/api/shots/repair"} and references' in backend
    assert 'angle:"0°正面全身", usage:"clothing_body"' in frontend
    assert 'asset.label === "0°正面半身" ? "face_primary" : "angle_continuity"' in frontend
    assert 'single-face-v2-anatomy-gate' in frontend
    assert '旧版分镜未经过人脸与人体结构专项验收' in frontend
    assert "assetUploadComplete" in frontend
    assert "missingAssetsForShotImages" in frontend


def test_asset_baselines_use_style_specific_local_models() -> None:
    backend = BACKEND.read_text(encoding="utf-8")

    assert "def _generate_flux1_schnell_baseline" in backend
    assert '"class_type":"UnetLoaderGGUF"' in backend
    assert '"unet_name":"flux1-schnell-Q8_0.gguf"' in backend
    assert 'asset_phase == "baseline"' in backend
    assert '"base_model":"flux1-schnell-Q8_0.gguf"' in backend
    assert '"steps":4' in backend
    assert 'image["validation_evidence"] = validation_evidence' in backend
    assert 'image["validation_passed"] = True' in backend
    assert "for validation_attempt in range(5):" not in backend
    assert "def _schnell_test_loras(body: dict)" in backend
    assert 'if str(body.get("asset_phase", "")) == "variant":\n        return []' in backend
    assert 'if kind == "prop":\n        return []' in backend
    assert '"国风浅涂":"风格_国风仙韵_FLUX1_仅测试.safetensors"' in backend
    assert '"国风厚涂":"风格_油画仙韵_FLUX1_仅测试.safetensors"' not in backend
    assert "def _klein9b_houtu_loras(body: dict)" in backend
    assert 'if parsed.path == "/api/characters/generate" and asset_phase == "baseline"' in backend
    assert 'image.baseline.klein9b' in backend
    assert '"--lora-paths"' in backend
    assert 'project_style = str(project.get("style", "")' in backend
    assert "if not style_paths:\n        return []" in backend
    assert '"style":"项目提示词锁定"' in backend
    assert 'schnell_baseline = parsed.path == "/api/characters/generate" and asset_phase == "baseline"' in backend
    assert 'selected_lora = None if schnell_baseline or references else _automatic_lora' in backend
    assert 'if "LoRA 索引未登记" in str(error)' in backend
    assert "def _generate_ipadapter_image" in backend
    route_start = backend.index('if parsed.path in {"/api/characters/generate", "/api/shots/generate", "/api/shots/repair", "/api/assistant/images/generate"}')
    route_end = backend.index('if parsed.path == "/api/videos/generate"', route_start)
    route = backend[route_start:route_end]
    fixed_branch = route[route.index('"image.variant.qwen"'):route.index('if asset_phase != "variant" or not target_pose:')]
    assert '"image.variant.ipadapter"' in fixed_branch
    assert 'target_pose=target_pose' in fixed_branch
    assert 'clothing_reference_url' in fixed_branch
    assert 'job_id=job_id' in fixed_branch
    assert '"num_predict":640' in backend
    assert '"deterministic_full_frame"' in backend
    assert '_generate_qwen_character_variant' in backend
    assert 'if asset_phase == "variant" and target_pose:' in route
    assert 'stage="ipadapter_openpose"' in backend
    assert 'required = ("exactly_one_person", "correct_orientation"' in backend
    assert 'required += ("full_head_visible", "feet_visible"' in backend
    assert '"ckpt_name":"RealVisXL_V5.0_fp16.safetensors"' in backend
    fixed_start = backend.index("def _generate_ipadapter_image")
    fixed_end = backend.index("def _extract_openpose", fixed_start)
    fixed_workflow = backend[fixed_start:fixed_end]
    assert '"class_type":"LoraLoader"' not in fixed_workflow
    assert '"style_lora":"none"' in fixed_workflow
    assert '"character_lora":"none"' in fixed_workflow
    assert '"kind":"style"' in backend
    assert '"kind":"character"' in backend
    assert "not os.path.samefile(path, style_path)" in backend
    assert 'gender in {"女", "女性", "female", "woman", "girl", "f"}' in backend
    assert 'verdict.get("plain_gray_background") is True' not in backend
    assert 'def _validate_prop_asset' in backend
    assert '"exactly_one_isolated_prop"' in backend
    assert '"no_scene_or_environment"' in backend
    assert 'STRICT STUDIO PRODUCT PHOTOGRAPH' in backend
    assert 'one pale cyan carved jade pendant' in backend
    assert 'image["validation_passed"] = prop_valid' in backend
    assert 'if prop_valid: break' in backend
    assert "def _normalize_character_baseline_crop" in backend
    assert 'scale=(1664.0*0.45)/face_h' in backend
    assert 'hair_top*scale-1664*0.05' in backend
    assert '(928.0*0.96)/hair_width' in backend
    assert 'verdict.get("required_928x1664") is True' in backend
    assert 'and verdict.get("front_facing") is True' in backend
    assert 'and verdict.get("direct_gaze") is True' in backend
    assert 'abs(pose[1]) <= 3.0 and abs(pose[2]) <= 3.0' in backend


def test_schnell_baseline_finishes_without_implicit_qwen_repair() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    schnell_start = backend.index("def _generate_flux1_schnell_baseline")
    repair_start = backend.index("def _repair_schnell_output_with_qwen")
    variant_start = backend.index("def _reference_path")
    schnell = backend[schnell_start:repair_start]
    repair = backend[repair_start:variant_start]

    assert 'shutil.copy2(generated, schnell_target)' in schnell
    assert '_free_comfy_memory()' in schnell
    assert '_repair_schnell_output_with_qwen(' not in schnell
    assert '"workflow_mode":"single_model_baseline"' in schnell
    assert 'os.replace(temporary_target, target)' in schnell
    assert '"class_type":"UnetLoaderGGUF"' in schnell
    assert 'qwen_image_edit_2511_fp8mixed.safetensors' not in schnell
    assert 'if not source.is_file()' in repair
    assert 'shutil.copy2(source, input_path)' in repair
    assert '"unet_name":"qwen_image_edit_2511_bf16.safetensors"' in repair
    assert 'qwen_image_edit_2511_fp8mixed.safetensors' not in repair
    assert 'flux1-schnell-Q8_0.gguf' not in repair
    assert '"workflow_mode":"sequential_independent"' in repair
    assert '"class_type":"LoadImageMask"' in repair
    assert '"class_type":"SetLatentNoiseMask"' in repair
    assert '"denoise":0.45' in repair
    assert 'repair_mode":"masked_local_inpaint"' in repair
    assert 'qwen_prompt_id' in repair


def test_fixed_angles_use_qwen_2511_official_multiple_angles_workflow() -> None:
    backend = BACKEND.read_text(encoding="utf-8")
    frontend = FRONTEND.read_text(encoding="utf-8")

    assert 'stage="ipadapter_openpose"' in backend
    assert '"ckpt_name":"RealVisXL_V5.0_fp16.safetensors"' in backend
    fixed_start = backend.index("def _generate_ipadapter_image")
    fixed_end = backend.index("def _extract_openpose", fixed_start)
    fixed_workflow = backend[fixed_start:fixed_end]
    assert '"class_type":"LoraLoader"' not in fixed_workflow
    assert '"class_type":"IPAdapterUnifiedLoaderFaceID"' in fixed_workflow
    assert '"preset":"FACEID PLUS V2"' in fixed_workflow
    assert '"class_type":"IPAdapterFaceID"' in fixed_workflow
    assert '"attn_mask":["24",0]' in fixed_workflow
    assert '"clip":["1",1]' in fixed_workflow
    assert '"steps":24' in fixed_workflow
    assert '"steps":12' in fixed_workflow
    assert '"denoise":profile["refine_denoise"]' in fixed_workflow
    assert '"refine_denoise":0.18' in fixed_workflow
    assert '"class_type":"VAEEncode"' in fixed_workflow
    assert '"control_net_name":"openpose-sdxl-1.0.safetensors"' in backend
    assert '"ipadapter_file":"ip-adapter-plus_sdxl_vit-h.safetensors"' in backend
    assert '"weight":profile["clothing_weight"],"weight_type":profile["clothing_weight_type"]' in backend
    assert '"end_at":profile["clothing_end"]' in backend
    assert '"model":["18",0]' in backend
    assert 'abs(pose[1]) <= 7.0' in backend
    assert '88.0 <= face_angle <= 92.0' in backend
    assert 'torso_rotation <= 3.0' in backend
    assert '"side_angle_tier"' in backend
    assert 'openpose_{target_pose}_7_5.png' in fixed_workflow
    assert 'side_depth_source_7_5.png' in fixed_workflow
    assert '"class_type":"DepthAnythingV2Preprocessor"' in fixed_workflow
    assert '"control_net_name":"xinsir-controlnet-depth-sdxl-1.0.safetensors"' in fixed_workflow
    assert '"workflow_mode":"two_stage_pose_then_identity_clothing"' in fixed_workflow
    assert "def _prepare_ipadapter_reference_crops" in backend
    assert "def _face_embedding_similarity" in backend
    assert "def _pose_proportion_metrics" in backend
    assert 'face_similarity >= 0.35' in backend
    assert 'clothing_similarity >= 0.82' in backend
    assert 'dimensions == (928, 1664)' in backend
    assert '"top_margin_at_least_8_percent"' in backend
    assert '"bottom_margin_at_least_3_percent"' in backend
    assert '"face_height_40_to_50_percent"' in backend
    assert '"head_to_body_ratio_7_to_7_8"' in backend
    assert 'deterministic_orientation' in backend
    assert '"exact_clothing_consistent"' in backend
    assert '"body_shape_consistent"' in backend
    assert 'for path in [reference, candidate]' in backend
    assert 'for path in [strict_clothing_reference, candidate]' in backend
    assert '_validate_character_variant(candidate.get("url", ""), candidate, "front_full")' in backend
    assert '"gender_and_age_match"' in backend
    assert '"face_hair_match"' in backend
    assert '"clothing_match"' in backend
    assert 'asset_phase == "repair"' in backend
    assert 'stage="qwen_repairing"' in backend
    route_start = backend.index('if parsed.path in {"/api/characters/generate", "/api/shots/generate", "/api/shots/repair", "/api/assistant/images/generate"}')
    route_end = backend.index('if parsed.path == "/api/videos/generate"', route_start)
    fixed_route = backend[route_start:route_end]
    assert '"image.variant.qwen"' in fixed_route
    assert '_invoke_production_capability(' in fixed_route
    qwen_start = backend.index('def _generate_qwen_character_variant')
    qwen_end = backend.index('def _latest_completed_asset_image_url', qwen_start)
    qwen_angle = backend[qwen_start:qwen_end]
    assert '"unet_name":"qwen_image_edit_2511_bf16.safetensors"' in qwen_angle
    assert 'angle_lora_weight = 0.35 if target_pose in {"left_45_full", "right_45_full"} else 1.0' in qwen_angle
    assert '"lora_name":"qwen-image-edit-2511-multiple-angles-lora.safetensors","strength_model":angle_lora_weight' in qwen_angle
    assert '"lora_name":"Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors","strength_model":1.0' in qwen_angle
    assert '"steps":4,"cfg":1.0' in qwen_angle
    asset_spec = (ROOT / "docs/specs/短剧3D资产生产规范.md").read_text(encoding="utf-8")
    assert "提示目标为从正面向对应方向转动35°" in asset_spec
    assert "左`+30°—+60°`、右`-60°—-30°`" in asset_spec
    assert "角度LoRA文件/权重、采样步数和CFG必须作为同一版本化配置整体锁定" in asset_spec
    assert "粘连、缺失、多余、重复、断裂、融化或不自然连接" in asset_spec
    assert '"image1":["3",0],"image2":["6",0]' in qwen_angle
    assert '"reference_latents_method":"index_timestep_zero"' in qwen_angle
    assert 'stage="qwen_variant"' in qwen_angle
    assert '_cancel_comfy_prompt(prompt_id)' in qwen_angle
    assert 'image = _generate_visual_persona_front_full(' not in fixed_route
    assert 'image = _generate_pshuman_view(' not in fixed_route
    assert '"control":1.05, "depth_control":0.55' in backend
    assert '"ip_weight":0.12' in backend
    assert 'assetError.value = `${item.name}：${userFacingGenerationError(item.error)}`' in frontend
    assert 'const firstFailedVariant = variants.find(variant => variant.status === "failed")' in frontend
    assert 'if (item.error) assetError.value = `${item.name}：${item.error}`' in frontend
    assert '"workflow_mode":"qwen_2511_multiple_angles"' in backend
    prop_scene_variant = backend[backend.index('if references and asset_phase == "variant" and asset_kind in {"scene", "prop"}'):]
    prop_scene_variant = prop_scene_variant[:prop_scene_variant.index("else:", 200)]
    assert '_repair_schnell_output_with_qwen(' not in prop_scene_variant
    assert '"image.generate"' in prop_scene_variant
    assert 'const identityReferenceUrl = item.image_url;' in frontend
    assert 'clothing_reference_url:clothingReferenceUrl' in frontend
    assert 'asset_phase:"repair"' in frontend
    unified_asset_card = (ROOT / "plugins/builtin/short_drama/frontend/components/business/UnifiedAssetCard.vue").read_text(encoding="utf-8")
    assert ':show-repair="Boolean(slide.imageUrl)"' in unified_asset_card
    assert "def _latest_completed_asset_image_url" in backend
    assert 'body["references"] = references' in backend
    assert 'body["clothing_reference_url"] = recovered_url' in backend


def test_in_world_text_is_blank_during_diffusion_and_rendered_deterministically() -> None:
    backend = BACKEND.read_text(encoding="utf-8")

    assert "def _required_image_text" in backend
    assert "def _blank_requested_text" in backend
    assert "def _apply_required_text_overlay" in backend
    assert "当前生图阶段禁止生成任何汉字、字母、数字、符号、书法、标志或水印" in backend
    assert 'required_text = _required_image_text(body, base_image_prompt)' in backend
    assert 'base_image_prompt = _blank_requested_text(base_image_prompt, required_text)' in backend
    assert '_apply_required_text_overlay(_local_media_path(image.get("url")), required_text, body)' in backend
    assert '"text_audit":"exact_source_render"' in backend
    assert 'hashlib.sha256(text.encode()).hexdigest()' in backend
    assert '/System/Library/Fonts/Supplemental/Songti.ttc' in backend
    assert "def _validate_scene_asset" in backend
    assert "no_text_letters_numbers_or_signage" in backend
    assert 'for validation_attempt in range(3)' in backend
