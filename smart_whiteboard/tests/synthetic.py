"""Synthetic camera scenes with known geometry, so computer-vision code can be tested without a webcam.

Scene model: a rectangular board (BOARD_W x BOARD_H, board coordinates) is seen through a known
perspective transform H_true (board -> camera). A coloured marker sits at a known board position.
We render the camera frame, then tests check that detection + calibration + mapping recover the
known board position.
"""
from __future__ import annotations

import time

import cv2
import numpy as np

CAM_W, CAM_H = 640, 360
BOARD_W, BOARD_H = 1600, 900
GREEN = (60, 200, 40)      # BGR, HSV ~ (60, 200, 200): inside the default green range
RED = (30, 30, 230)        # BGR, hue ~ 0 (wraps)
BLUE = (230, 80, 20)

# board corners in the camera image (TL, TR, BR, BL): a mild perspective trapezium
CAM_QUAD = [(110.0, 60.0), (540.0, 80.0), (590.0, 320.0), (60.0, 300.0)]


def board_to_cam_matrix(quad=CAM_QUAD, board=(BOARD_W, BOARD_H)) -> np.ndarray:
    src = np.float32([(0, 0), (board[0], 0), (board[0], board[1]), (0, board[1])])
    return cv2.getPerspectiveTransform(src, np.float32(quad))


def project(H: np.ndarray, x: float, y: float) -> tuple[float, float]:
    v = H @ np.array([x, y, 1.0])
    return float(v[0] / v[2]), float(v[1] / v[2])


def render_scene(marker_board=None, marker_color=GREEN, radius=9, size=(CAM_W, CAM_H), quad=CAM_QUAD,
                 noise=0, seed=0, extra=None) -> np.ndarray:
    w, h = size
    img = np.full((h, w, 3), (70, 70, 74), np.uint8)                       # grey room
    cv2.fillConvexPoly(img, np.int32(np.round(quad)), (238, 238, 232))      # white board
    if noise:
        rng = np.random.default_rng(seed)
        img = np.clip(img.astype(np.int16) + rng.integers(-noise, noise + 1, img.shape), 0, 255).astype(np.uint8)
    if marker_board is not None:
        H = board_to_cam_matrix(quad)
        cx, cy = project(H, *marker_board)
        cv2.circle(img, (int(round(cx)), int(round(cy))), radius, marker_color, -1, cv2.LINE_AA)
    for fn in extra or []:
        fn(img)
    return img


def blob_frame(w=320, h=180, blobs=(), color=GREEN, bg=(40, 40, 40)) -> np.ndarray:
    """Plain frame with filled circles: blobs = [(cx, cy, r), ...]."""
    img = np.full((h, w, 3), bg, np.uint8)
    for cx, cy, r in blobs:
        cv2.circle(img, (int(cx), int(cy)), int(r), color, -1)
    return img


class FakeCapture:
    """Minimal cv2.VideoCapture look-alike playing a scripted scene (used by engine/GUI tests only).

    `frames` is a callable(index) -> frame or None (None = a failed read). Frames are paced at `fps`.
    """

    def __init__(self, frames, fps=60, opened=True, size=(CAM_W, CAM_H)):
        self._frames, self._fps, self._opened, self._size = frames, fps, opened, size
        self._i = 0
        self.released = False
        self._next = time.perf_counter()

    def isOpened(self):
        return self._opened and not self.released

    def set(self, *_):
        return True

    def get(self, prop):
        return {cv2.CAP_PROP_FRAME_WIDTH: self._size[0], cv2.CAP_PROP_FRAME_HEIGHT: self._size[1]}.get(prop, 0)

    def read(self):
        delay = self._next - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        self._next = max(self._next, time.perf_counter()) + 1.0 / self._fps
        frame = self._frames(self._i)
        self._i += 1
        return (frame is not None), frame

    def release(self):
        self.released = True
