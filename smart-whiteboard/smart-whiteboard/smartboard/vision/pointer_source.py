"""Pointer sources: where does the pointer come from?

Both classes expose the same interface so the rest of the application does
not care whether the pointer is a red dot seen by the camera or the mouse
(handy to develop the UI at home without the hardware):

    update()                -> PointerSample         (latest sample, never blocks)
    pop_clicks()            -> list[ClickEvent]      (only the mouse source produces any)
    click_position(lookback) -> board position to use for a click

VisionPointerSource can run in its own thread (start()): camera capture,
detection, smoothing and mapping then keep their frame rate whatever the
interface is doing (drawing a 1080p screen takes longer than a camera frame).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, List, Optional, Tuple

import numpy as np

from ..config import Config
from ..events import ClickEvent, LEFT, RIGHT, PointerSample
from .calibration import Calibration
from .detector import Detection, RedDotDetector
from .tracker import PointerTracker


class VisionPointerSource:
    """camera frame -> red dot detection -> smoothing -> homography -> board px."""

    def __init__(self, cfg: Config, camera, calibration: Calibration):
        self.cfg = cfg
        self.camera = camera
        self.calib = calibration
        self.detector = RedDotDetector(cfg.detection)
        self.track_cam = PointerTracker(cfg.tracking)     # smoothing in camera space (prior, calibration)
        self.track_board = PointerTracker(cfg.tracking)   # smoothing in board space (what the UI sees)
        self.last_frame: Optional[np.ndarray] = None
        self.last_detection: Optional[Detection] = None
        self.sample = PointerSample()
        self.history: Deque[Tuple[float, Tuple[float, float]]] = deque(maxlen=120)   # (time, board) tracked
        self.fps = 0.0
        self.latency_ms = 0.0
        self.frames = 0                # processed camera frames
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._run = False
        self.refresh_roi()

    # ---- calibration hook --------------------------------------------------------------------
    def refresh_roi(self):
        """Call after (re)calibration: only look for the dot inside the board."""
        with self._lock:
            self.detector.set_roi(self.calib.board_quad_in_camera())

    # ---- one pipeline step -------------------------------------------------------------------
    def step(self) -> bool:
        """Process the newest camera frame (if any).  Returns True if a frame was processed."""
        frame = self.camera.read()
        if frame is None:
            return False
        t0 = time.perf_counter()
        with self._lock:
            self.calib.set_camera_size(frame.shape[1], frame.shape[0])
            self.last_frame = frame
            det = self.detector.detect(frame, self.track_cam.last)
            self.last_detection = det

            cam_raw = (det.x, det.y) if det else None
            cam_s, tracked, lost = self.track_cam.update(cam_raw, t0)

            board_s = None
            if self.calib.calibrated:
                board_raw = self.calib.cam_to_board(*cam_raw) if cam_raw else None
                if board_raw:  # clamp to the board so the pointer never leaves the screen
                    board_raw = (min(max(board_raw[0], 0), self.calib.board_w - 1),
                                 min(max(board_raw[1], 0), self.calib.board_h - 1))
                board_s, _, _ = self.track_board.update(board_raw, t0)
                if board_raw and board_s:
                    self.history.append((t0, board_s))
            self.sample = PointerSample(board_s, cam_s, tracked, lost)
        self.frames += 1
        t1 = time.perf_counter()
        self.latency_ms = 0.9 * self.latency_ms + 0.1 * (t1 - t0) * 1000
        dt = max(t1 - getattr(self, "_t_prev", t1 - 0.033), 1e-3)
        self._t_prev = t1
        self.fps = 0.9 * self.fps + 0.1 / dt if self.fps else 1.0 / dt
        return True

    # ---- threading ---------------------------------------------------------------------------
    def start(self):
        if self._thread is not None:
            return
        self._run = True

        def loop():
            while self._run:
                if not self.step():
                    time.sleep(0.002)
        self._thread = threading.Thread(target=loop, daemon=True, name="vision")
        self._thread.start()

    def update(self) -> PointerSample:
        if self._thread is None:                 # not threaded: do the work here
            self.step()
        return self.sample

    # ---- clicks ------------------------------------------------------------------------------
    def click_position(self, lookback_s: float = 0.0, max_move_px: float = 120.0):
        """Board position for a click made NOW.

        Pressing a remote button makes the hand (and the dot) jump a few pixels
        just before the key event arrives.  So the click uses where the dot was
        ``lookback_s`` earlier - unless the pointer has travelled far since then
        (a deliberate fast move), in which case the current position is right."""
        cur = self.sample.board
        if cur is None or lookback_s <= 0:
            return cur
        with self._lock:
            hist = list(self.history)
        if not hist:
            return cur
        t_ref = time.perf_counter() - lookback_s
        past = min(hist, key=lambda e: abs(e[0] - t_ref))
        if abs(past[0] - t_ref) > 0.15:
            return cur
        if np.hypot(cur[0] - past[1][0], cur[1] - past[1][1]) > max_move_px:
            return cur
        return past[1]

    def pop_clicks(self) -> List[ClickEvent]:
        return []

    def release(self):
        self._run = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self.camera.release()


class MousePointerSource:
    """Simulation: the mouse over the application window is the pointer and
    its buttons act as the two remote buttons.  Used with  --mouse."""

    def __init__(self):
        self.pos = None
        self._clicks: List[ClickEvent] = []
        self.sample = PointerSample()
        self.last_frame = None
        self.last_detection = None
        self.fps = 0.0
        self.latency_ms = 0.0

    def attach(self, window_name: str):
        import cv2

        def cb(event, x, y, flags, param):
            self.pos = (float(x), float(y))
            if event == cv2.EVENT_LBUTTONDOWN:
                self._clicks.append(ClickEvent(LEFT, self.pos, "mouse"))
            elif event == cv2.EVENT_RBUTTONDOWN:
                self._clicks.append(ClickEvent(RIGHT, self.pos, "mouse"))
        cv2.setMouseCallback(window_name, cb)

    def start(self):
        pass

    def refresh_roi(self):
        pass

    def update(self) -> PointerSample:
        if self.pos is not None:
            self.sample = PointerSample(self.pos, self.pos, True, 0)
        return self.sample

    def click_position(self, lookback_s: float = 0.0, max_move_px: float = 120.0):
        return self.sample.board

    def pop_clicks(self) -> List[ClickEvent]:
        out, self._clicks = self._clicks, []
        return out

    def release(self):
        pass
