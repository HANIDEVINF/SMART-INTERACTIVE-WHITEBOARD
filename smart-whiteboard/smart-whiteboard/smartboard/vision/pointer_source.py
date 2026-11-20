"""Pointer sources: where does the pointer come from?

Both classes expose the same interface so the rest of the application does
not care whether the pointer is a red dot seen by the camera or the mouse
(handy to develop the UI at home without the hardware):

    update()  -> PointerSample
    pop_clicks() -> list[ClickEvent]   (only the mouse source produces any)
"""
from __future__ import annotations

import time
from typing import List, Optional

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
        self.track_cam = PointerTracker(cfg.tracking)     # smoothing in camera space
        self.track_board = PointerTracker(cfg.tracking)   # smoothing in board space
        self.last_frame: Optional[np.ndarray] = None
        self.last_detection: Optional[Detection] = None
        self.sample = PointerSample()
        self.refresh_roi()

    def refresh_roi(self):
        """Call after (re)calibration: only look for the dot inside the board."""
        self.detector.set_roi(self.calib.board_quad_in_camera())

    def update(self) -> PointerSample:
        frame = self.camera.read()
        if frame is None:               # no new frame yet: keep the previous sample
            return self.sample
        t = time.perf_counter()
        self.last_frame = frame
        prior = self.track_cam.last
        det = self.detector.detect(frame, prior)
        self.last_detection = det

        cam_raw = (det.x, det.y) if det else None
        cam_s, tracked, lost = self.track_cam.update(cam_raw, t)

        board_s = None
        if self.calib.calibrated:
            board_raw = self.calib.cam_to_board(*cam_raw) if cam_raw else None
            if board_raw:  # clamp to the board so the pointer never leaves the screen
                board_raw = (min(max(board_raw[0], 0), self.calib.board_w - 1),
                             min(max(board_raw[1], 0), self.calib.board_h - 1))
            board_s, _, _ = self.track_board.update(board_raw, t)
        self.sample = PointerSample(board_s, cam_s, tracked, lost)
        return self.sample

    def pop_clicks(self) -> List[ClickEvent]:
        return []

    def release(self):
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

    def attach(self, window_name: str):
        import cv2

        def cb(event, x, y, flags, param):
            self.pos = (float(x), float(y))
            if event == cv2.EVENT_LBUTTONDOWN:
                self._clicks.append(ClickEvent(LEFT, self.pos, "mouse"))
            elif event == cv2.EVENT_RBUTTONDOWN:
                self._clicks.append(ClickEvent(RIGHT, self.pos, "mouse"))
        cv2.setMouseCallback(window_name, cb)

    def refresh_roi(self):
        pass

    def update(self) -> PointerSample:
        if self.pos is not None:
            self.sample = PointerSample(self.pos, self.pos, True, 0)
        return self.sample

    def pop_clicks(self) -> List[ClickEvent]:
        out, self._clicks = self._clicks, []
        return out

    def release(self):
        pass
