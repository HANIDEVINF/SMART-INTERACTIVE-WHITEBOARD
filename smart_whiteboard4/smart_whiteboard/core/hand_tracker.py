"""Hand tracking with MediaPipe (optional backend) - index fingertip pointer + pinch clicks.

The colour-marker detector (core/detector.py) stays the default and the fallback. This module adds a second
pointer source that needs no marker: your bare hand.

    pointer        index fingertip (landmark 8)
    Next click     thumb tip (4) touches middle fingertip (12)   -> left click  (same as the Right arrow)
    Previous click thumb tip (4) touches ring fingertip (16)     -> right click (same as the Left arrow)

The index finger is deliberately NOT part of the pinch, so the pointer does not jump when you click.

Pinch test (scale invariant):  ratio = |thumb_tip - finger_tip| / |wrist - middle_mcp|
A pinch starts when ratio < PINCH_ON and ends when ratio > PINCH_OFF (hysteresis avoids flicker).
GestureClicker then requires the pinch to be seen on CONFIRM_FRAMES consecutive frames and enforces a cooldown,
so noisy landmarks cannot create repeated clicks.

MediaPipe needs a model file (hand_landmarker.task, ~7 MB, free). It is downloaded once with download_model()
to data/models/. Nothing here uses a cloud service at run time: inference is local.
"""
from __future__ import annotations

import math
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from core.detector import Detection, DetectionResult
from core.settings import DATA_DIR

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/"
             "hand_landmarker.task")
MODEL_FILENAME = "hand_landmarker.task"
MIN_MODEL_BYTES = 1_000_000

WRIST, THUMB_TIP, INDEX_TIP, MIDDLE_MCP, MIDDLE_TIP, RING_TIP = 0, 4, 8, 9, 12, 16
PINCH_ON, PINCH_OFF = 0.30, 0.48
CONFIRM_FRAMES = 2
COOLDOWN_MS = 600
HAND_CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11),
                    (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18), (18, 19), (19, 20),
                    (0, 17)]


def model_path() -> Path:
    return DATA_DIR / "models" / MODEL_FILENAME


# ---------------------------------------------------------------------------------------------------- status
def mediapipe_importable() -> tuple[bool, str]:
    try:
        import mediapipe  # noqa: F401
        from mediapipe.tasks.python import vision  # noqa: F401
    except Exception as exc:                          # ImportError, or a broken native library
        return False, f"MediaPipe cannot be imported ({exc.__class__.__name__}: {exc})"
    return True, "MediaPipe is installed"


def hand_backend_status(path: Path | None = None) -> tuple[bool, str]:
    ok, msg = mediapipe_importable()
    if not ok:
        return False, msg
    p = path or model_path()
    if not p.is_file() or p.stat().st_size < MIN_MODEL_BYTES:
        return False, "Hand model not downloaded yet"
    return True, "MediaPipe hand tracking ready"


def download_model(dest: Path | None = None, progress: Callable[[float], None] | None = None,
                   url: str = MODEL_URL, timeout: float = 30.0) -> Path:
    """Download the hand model (atomic: written to .part, checked, then renamed). Raises OSError on failure."""
    dest = dest or model_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp, open(part, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(min(done / total, 1.0))
        if part.stat().st_size < MIN_MODEL_BYTES:
            raise OSError("the downloaded file is too small to be the model")
        part.replace(dest)
    except Exception as exc:
        try:
            part.unlink()
        except OSError:
            pass
        raise OSError(f"Could not download the hand model: {exc}") from exc
    if progress:
        progress(1.0)
    return dest


# ---------------------------------------------------------------------------------------------------- geometry
def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def pinch_ratios(pts: list[tuple[float, float]]) -> tuple[float, float]:
    """(thumb-middle, thumb-ring) distances divided by the hand size (wrist to middle-finger knuckle)."""
    scale = max(_dist(pts[WRIST], pts[MIDDLE_MCP]), 1e-6)
    return _dist(pts[THUMB_TIP], pts[MIDDLE_TIP]) / scale, _dist(pts[THUMB_TIP], pts[RING_TIP]) / scale


class PinchClassifier:
    """Frame -> "next" | "previous" | "" with hysteresis."""

    def __init__(self) -> None:
        self.state = ""

    def update(self, pts: list[tuple[float, float]] | None) -> str:
        if pts is None:
            self.state = ""
            return ""
        r_mid, r_ring = pinch_ratios(pts)
        ratios = {"next": r_mid, "previous": r_ring}
        if self.state:
            if ratios[self.state] > PINCH_OFF:
                self.state = ""
        if not self.state:
            name, value = min(ratios.items(), key=lambda kv: kv[1])
            if value < PINCH_ON:
                self.state = name
        return self.state


class GestureClicker:
    """Turns the pinch state into single click events (confirm frames + cooldown + must release first)."""

    def __init__(self, confirm_frames: int = CONFIRM_FRAMES, cooldown_ms: int = COOLDOWN_MS) -> None:
        self.confirm_frames, self.cooldown_ms = confirm_frames, cooldown_ms
        self.reset()

    def reset(self) -> None:
        self._candidate, self._count = "", 0
        self._armed = True
        self._last_fire = -1e9

    def update(self, state: str, t: float) -> str | None:
        if not state:
            self._candidate, self._count, self._armed = "", 0, True
            return None
        if state != self._candidate:
            self._candidate, self._count = state, 0
        self._count += 1
        if self._armed and self._count >= self.confirm_frames and (t - self._last_fire) * 1000.0 >= self.cooldown_ms:
            self._armed = False                      # one event per pinch: release before the next one
            self._last_fire = t
            return state
        return None


# ---------------------------------------------------------------------------------------------------- tracker
class HandTracker:
    """Runs the MediaPipe hand landmarker. Create and use it from ONE thread (the vision worker)."""

    MAX_WIDTH = 640

    def __init__(self, path: Path | None = None, landmarker_factory: Callable[[], object] | None = None) -> None:
        self.path = path or model_path()
        self._factory = landmarker_factory
        self._landmarker = None
        self._last_ms = -1
        self.classifier = PinchClassifier()

    def _create(self):
        if self._factory is not None:
            return self._factory()
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self.path)),
            running_mode=vision.RunningMode.VIDEO, num_hands=1,
            min_hand_detection_confidence=0.5, min_hand_presence_confidence=0.5, min_tracking_confidence=0.5)
        self._mp = mp
        return vision.HandLandmarker.create_from_options(options)

    def close(self) -> None:
        if self._landmarker is not None and hasattr(self._landmarker, "close"):
            try:
                self._landmarker.close()
            except Exception:
                pass
        self._landmarker = None

    def _run(self, frame_bgr: np.ndarray, ts_ms: int):
        if self._factory is not None:
            return self._landmarker.detect_for_video(frame_bgr, ts_ms)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        return self._landmarker.detect_for_video(image, ts_ms)

    def detect(self, frame_bgr: np.ndarray, t: float) -> DetectionResult:
        """-> DetectionResult (same type as the colour detector) with .landmarks and .gesture_state filled."""
        t0 = time.perf_counter()
        if self._landmarker is None:
            self._landmarker = self._create()
        h, w = frame_bgr.shape[:2]
        small = frame_bgr
        if w > self.MAX_WIDTH:
            small = cv2.resize(frame_bgr, (self.MAX_WIDTH, max(1, round(h * self.MAX_WIDTH / w))),
                               interpolation=cv2.INTER_AREA)
        ts_ms = max(int(t * 1000.0), self._last_ms + 1)           # MediaPipe needs strictly increasing stamps
        self._last_ms = ts_ms
        res = self._run(small, ts_ms)
        mask = np.zeros((max(1, h * 320 // w), 320), np.uint8)

        def done(det, status, msg, pts=None, gesture=""):
            r = DetectionResult(det, status, msg, mask, 1 if det else 0, (time.perf_counter() - t0) * 1000.0)
            r.landmarks, r.gesture_state = pts, gesture
            return r

        hands = getattr(res, "hand_landmarks", None) or []
        if not hands:
            self.classifier.update(None)
            return done(None, "no_hand", "No hand in view")
        norm = [(float(lm.x), float(lm.y)) for lm in hands[0]]
        pts = [(x * w - 0.5, y * h - 0.5) for x, y in norm]             # camera pixels
        gesture = self.classifier.update(pts)               # pixel units, so distances are not aspect-distorted
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        poly = np.array([(x * 320 / w, y * mask.shape[0] / h) for x, y in pts], np.int32)
        cv2.fillConvexPoly(mask, cv2.convexHull(poly), 255)
        score = 1.0
        handed = getattr(res, "handedness", None)
        try:
            score = float(handed[0][0].score)
        except (TypeError, IndexError, AttributeError):
            pass
        tip = pts[INDEX_TIP]
        det = Detection(x=tip[0], y=tip[1], area=float((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])),
                        confidence=score, bbox=bbox)
        label = {"next": "  |  pinch: NEXT (left click)", "previous": "  |  pinch: PREVIOUS (right click)"}.get(gesture, "")
        return done(det, "ok", f"Hand found - fingertip at {tip[0]:.0f}, {tip[1]:.0f}{label}", pts, gesture)
