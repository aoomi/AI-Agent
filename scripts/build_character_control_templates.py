"""Build deterministic, versioned OpenPose templates and a neutral side-depth source."""

from pathlib import Path
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "plugins/builtin/short_drama/backend/assets/character_controls"
AUX_SRC = Path("/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/custom_nodes/comfyui_controlnet_aux/src")
sys.path.insert(0, str(AUX_SRC))

from custom_controlnet_aux.open_pose.body import Keypoint  # noqa: E402
from custom_controlnet_aux.open_pose.util import draw_bodypose  # noqa: E402


def point(x: float, y: float) -> Keypoint:
    return Keypoint(x, y, 1.0, -1)


def template(view: str) -> np.ndarray:
    cx = 0.50
    if view == "side_90_full":
        xs = {"near": cx + 0.006, "far": cx - 0.006}
    else:
        xs = {"near": cx + 0.11, "far": cx - 0.11}
    points = [
        point(cx + (0.035 if view == "side_90_full" else 0), 0.105),
        point(cx, 0.205),
        point(xs["near"], 0.235), point(xs["near"] + 0.025, 0.355), point(xs["near"] + 0.020, 0.485),
        point(xs["far"], 0.235), point(xs["far"] - 0.025, 0.355), point(xs["far"] - 0.020, 0.485),
        point(cx + (0.018 if view != "side_90_full" else 0.006), 0.505),
        point(cx + (0.025 if view != "side_90_full" else 0.008), 0.700),
        point(cx + (0.030 if view != "side_90_full" else 0.010), 0.910),
        point(cx - (0.018 if view != "side_90_full" else 0.006), 0.505),
        point(cx - (0.025 if view != "side_90_full" else 0.008), 0.700),
        point(cx - (0.030 if view != "side_90_full" else 0.010), 0.910),
        point(cx + (0.018 if view == "side_90_full" else 0.030), 0.095),
        point(cx - (0.008 if view == "side_90_full" else 0.030), 0.095),
        point(cx + (0.005 if view == "side_90_full" else 0.050), 0.105),
        point(cx - (0.015 if view == "side_90_full" else 0.050), 0.105),
    ]
    canvas = np.zeros((1664, 928, 3), dtype=np.uint8)
    return draw_bodypose(canvas, points, xinsr_stick_scaling=True)


def build_depth_source() -> np.ndarray:
    image = np.full((1664, 928, 3), 128, dtype=np.uint8)
    center = 464
    cv2.ellipse(image, (center, 176), (70, 98), 0, 0, 360, (185, 185, 185), -1)
    cv2.ellipse(image, (center + 48, 180), (38, 26), 0, 0, 360, (190, 190, 190), -1)
    cv2.rectangle(image, (center - 25, 260), (center + 28, 325), (178, 178, 178), -1)
    torso = np.array([[center - 58, 320], [center + 70, 320], [center + 52, 820], [center - 42, 820]], np.int32)
    cv2.fillConvexPoly(image, torso, (172, 172, 172))
    cv2.line(image, (center + 40, 350), (center + 42, 820), (184, 184, 184), 42)
    cv2.line(image, (center - 8, 805), (center - 4, 1475), (176, 176, 176), 50)
    cv2.line(image, (center + 18, 805), (center + 20, 1475), (166, 166, 166), 48)
    cv2.ellipse(image, (center + 44, 1515), (76, 28), 8, 0, 360, (182, 182, 182), -1)
    return cv2.GaussianBlur(image, (0, 0), 7)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for view in ("front_full", "side_90_full", "back_full"):
        cv2.imwrite(str(ASSETS / f"openpose_{view}_7_5.png"), template(view))
    cv2.imwrite(str(ASSETS / "side_depth_source_7_5.png"), build_depth_source())


if __name__ == "__main__":
    main()
