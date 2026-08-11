#!/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/.venv/bin/python3
"""Real local image -> TripoSR/Blender -> storyboard frames -> H3 video E2E."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import cv2
import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "plugins/builtin/short_drama/backend/asset_3d_worker.py"
TRIPOSR_PYTHON = Path("/Users/aoo/AI/Tools/TripoSR/.venv/bin/python")
FFMPEG = Path("/opt/homebrew/bin/ffmpeg")
FFPROBE = Path("/opt/homebrew/bin/ffprobe")
API = "http://127.0.0.1:8787"
TARGET_SIZE = (928, 1664)
FACE_CASCADE = ROOT / "models/vision/opencv/haarcascade_frontalface_default.xml"
CAMERAS = [
    ("front_0", 0, 0), ("left_45", -45, 0), ("side_90", -90, 0),
    ("rear_135", -135, 0), ("top_45", 0, -45), ("bottom_15", 0, 15),
]


def digest(path: Path) -> str:
    value = hashlib.md5()  # noqa: S324 - user-requested artifact checksum, not security.
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def stage_log(stage: int, paths: list[Path]) -> None:
    print(f"[阶段{stage}] 完成 ✓ " + " ".join(f"{item.name}={digest(item)}" for item in paths), flush=True)


def detect_face(image: np.ndarray) -> tuple[int, int, int, int] | None:
    classifier = cv2.CascadeClassifier(str(FACE_CASCADE))
    if classifier.empty():
        raise RuntimeError("OpenCV人脸检测资源不存在或损坏")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = classifier.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(48, 48))
    if not len(faces):
        return None
    x, y, width, height = max(faces, key=lambda value: int(value[2]) * int(value[3]))
    return int(x), int(y), int(width), int(height)


def extract_features(source: Path, target: Path) -> dict:
    image = cv2.imread(str(source))
    if image is None:
        raise RuntimeError("输入图片无法解码")
    height, width = image.shape[:2]
    face = detect_face(image)
    pixels = image.reshape(-1, 3)
    dominant = np.median(pixels, axis=0).astype(int).tolist()[::-1]
    payload = {
        "source": str(source), "subject_type": "character" if face else "object_or_scene",
        "image_size": {"width": width, "height": height}, "dominant_rgb": dominant,
        "body": {"estimated_height_ratio": 0.88, "shoulder_width_ratio": 0.32},
        "face": None if face is None else {
            "bbox_xywh": list(face), "center_ratio": [(face[0] + face[2] / 2) / width, (face[1] + face[3] / 2) / height],
            "eye_distance_ratio_estimate": 0.32, "nose_bridge_ratio_estimate": 0.24,
            "mouth_width_ratio_estimate": 0.38, "jaw_width_ratio_estimate": 0.78,
        },
        "method": "OpenCV Haar face localization + deterministic proportion estimates",
    }
    write_json(target, payload)
    return payload


def camera_parameters(features: dict, target: Path) -> dict:
    radius, height = 3.2, 1.45
    cameras = []
    for index, (name, yaw, pitch) in enumerate(CAMERAS, 1):
        radians = math.radians(yaw)
        cameras.append({
            "id": index, "name": name, "position_xyz": [round(radius * math.sin(radians), 4), round(-radius * math.cos(radians), 4), height],
            "rotation_yaw_pitch_roll": [yaw, pitch, 0], "focal_length_mm": 50,
        })
    payload = {
        "source_features": str(features.get("source")), "mesh_size_cm": {"length": 45, "width": 60, "height": 170},
        "material": {"diffuse_rgb": features["dominant_rgb"], "roughness": 0.55, "metallic": 0.0}, "cameras": cameras,
    }
    write_json(target, payload)
    return payload


def run_3d(source: Path, output: Path) -> dict:
    report = output / "report.json"
    if report.is_file():
        return json.loads(report.read_text(encoding="utf-8"))
    command = [str(TRIPOSR_PYTHON), str(WORKER), "--source", str(source), "--output", str(output), "--kind", "character", "--resolution", "256"]
    subprocess.run(command, cwd=ROOT, check=True, timeout=3600)
    return json.loads(report.read_text(encoding="utf-8"))


def fit_frame(source: Path, target: Path) -> None:
    with Image.open(source).convert("RGB") as image:
        fitted = ImageOps.contain(image, TARGET_SIZE, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", TARGET_SIZE, (32, 32, 32))
        canvas.paste(fitted, ((TARGET_SIZE[0] - fitted.width) // 2, (TARGET_SIZE[1] - fitted.height) // 2))
        canvas.save(target, "PNG")


def make_storyboard_frames(source: Path, report: dict, directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    render_order = ["front_0", "left_45", "right_45", "side_90", "back_180", "top", "bottom"]
    render_paths = {str(item["label"]): Path(item["path"]) for item in report["renders"]}
    inputs = [source, *(render_paths[name] for name in render_order)]
    outputs = []
    for index, item in enumerate(inputs, 1):
        target = directory / f"frame_{index:02d}.png"
        fit_frame(item, target)
        outputs.append(target)
    return outputs


def api_json(method: str, path: str, payload: dict | None = None, *, headers: dict[str, str] | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(API + path, data=data, headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(error.read().decode("utf-8")) from error


def generate_h3_video(source: Path, source_video: Path, output: Path, *, duration: int) -> tuple[Path, dict]:
    payload = {
        "tenant_id": "local-default", "user_id": "aoo", "project_id": "visual-e2e",
        "episode": 1, "shot_number": int(time.time()) % 1000000, "business_duration": duration,
        "image_url": f"/api/result-media?filename={source.name}&subfolder=images", "source_video_url": str(source_video),
        "identity_reference_url": str(source), "orientation": "portrait",
        "prompt": "Smooth slow cinematic orbit, preserve the exact face, costume and body; stable vertical composition.",
        "motion_strategy": {"camera_movement_ratio": 0.3, "subject_action_ratio": 0.15, "instruction": "slow stable orbit, no abrupt movement"},
    }
    started = api_json("POST", "/api/videos/generate", payload, headers={"X-Production-Dispatched": "1"})
    job_id = str(started["job_id"])
    query = urlencode({"job_id": job_id})
    deadline = time.time() + 1800
    while time.time() < deadline:
        result = api_json("GET", f"/api/videos/result?{query}")
        if result.get("status") == "completed":
            media = API + str(result["video"]["url"])
            with urlopen(media, timeout=120) as response, output.open("wb") as stream:
                shutil.copyfileobj(response, stream)
            return output, result
        if result.get("status") in {"failed", "cancelled", "stopped"}:
            raise RuntimeError(str(result.get("error") or "H3视频生成失败"))
        time.sleep(3)
    api_json("POST", "/api/videos/stop", {"job_id": job_id})
    raise TimeoutError("H3 E2E超过30分钟硬截止")


def probe_video(path: Path) -> dict:
    command = [str(FFPROBE), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,duration", "-of", "json", str(path)]
    return json.loads(subprocess.check_output(command, text=True))["streams"][0]


def upscale_2k(source: Path, target: Path) -> Path:
    subprocess.run([str(FFMPEG), "-y", "-i", str(source), "-vf", "scale=1440:2560:flags=lanczos", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)], check=True, capture_output=True, timeout=1800)
    return target


def validate_video(video: Path, frames: list[Path], target: Path, started_at: float) -> dict:
    capture = cv2.VideoCapture(str(video)); fps = capture.get(cv2.CAP_PROP_FPS) or 24; count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    samples, previous = [], None
    for frame_index in range(0, count, max(1, round(fps * 0.5))):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index); ok, frame = capture.read()
        if not ok: continue
        face = detect_face(frame); residual = 0.0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if previous is not None:
            flow = cv2.calcOpticalFlowFarneback(previous, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            median = np.median(flow.reshape(-1, 2), axis=0)
            residual = float(np.percentile(np.linalg.norm(flow - median, axis=2), 95) / frame.shape[1])
        samples.append({"frame": frame_index, "face_detected": face is not None, "residual_flow_ratio_p95": round(residual, 5)})
        previous = gray
    capture.release()
    source_embeddings = []
    for path in frames:
        image = cv2.imread(str(path)); face = detect_face(image) if image is not None else None
        if face:
            x, y, w, h = face; crop = cv2.resize(cv2.cvtColor(image[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY), (64, 64)).astype(np.float32) / 255
            source_embeddings.append(crop.flatten())
    similarity = 0.0
    if len(source_embeddings) >= 2:
        normalized = [item / max(np.linalg.norm(item), 1e-6) for item in source_embeddings]
        similarity = float(np.mean([np.dot(normalized[0], item) for item in normalized[1:]]))
    probe = probe_video(video); duration = float(probe.get("duration") or 0)
    face_rate = sum(1 for item in samples if item["face_detected"]) / max(1, len(samples))
    max_residual = max((item["residual_flow_ratio_p95"] for item in samples), default=1.0)
    checks = {
        "playable": video.stat().st_size > 1024, "portrait_9_16": int(probe["height"]) > int(probe["width"]),
        "duration_at_least_8s": duration >= 8, "face_detection_rate_ge_80pct": face_rate >= 0.8,
        "residual_optical_flow_le_3pct": max_residual <= 0.03, "storyboard_face_similarity_ge_85pct": similarity >= 0.85,
        "total_time_le_25min": time.time() - started_at <= 1500,
    }
    report = {
        "status": "passed" if all(checks.values()) else "failed", "checks": checks, "video": probe,
        "face_score": round(face_rate, 4), "storyboard_identity_similarity": round(similarity, 4),
        "stability_score": round(max(0.0, 1 - max_residual), 4), "samples": samples,
        "limitations": ["Face validation uses Haar detection and normalized face-crop similarity; production ArcFace landmark thresholds remain a separate pending capability."],
    }
    write_json(target, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "output/e2e/visual-3d-h3")
    parser.add_argument("--duration", type=int, default=8)
    args = parser.parse_args(); started_at = time.time()
    source = args.input.resolve(); output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    if not source.is_file(): raise SystemExit("输入图片不存在")
    if not 8 <= args.duration <= 15: raise SystemExit("H3时长必须为8—15秒")
    features_path = output / "feature_extraction.json"; features = extract_features(source, features_path); stage_log(1, [features_path])
    params_path = output / "3d_params.json"; camera_parameters(features, params_path); stage_log(2, [params_path])
    report = run_3d(source, output / "asset3d"); frames = make_storyboard_frames(source, report, output / "storyboard_frames"); stage_log(3, frames)
    raw_video, h3_job = generate_h3_video(source, Path(report["source_video"]), output / "storyboard_video_768P.mp4", duration=args.duration)
    final_video = upscale_2k(raw_video, output / "storyboard_video_2K.mp4"); stage_log(4, [raw_video, final_video])
    validation_path = output / "validation_report.json"; validation = validate_video(final_video, frames, validation_path, started_at); stage_log(5, [validation_path])
    write_json(output / "run_manifest.json", {"input": str(source), "h3_job": h3_job, "outputs": {"3d_params": str(params_path), "frames": [str(path) for path in frames], "video": str(final_video), "validation": str(validation_path)}, "status": validation["status"]})
    if validation["status"] != "passed": raise SystemExit(2)


if __name__ == "__main__":
    main()
