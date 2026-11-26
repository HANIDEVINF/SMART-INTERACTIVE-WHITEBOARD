"""Coordinate systems and the conversions between them.

Three different coordinate systems are involved and must never be mixed up:

    CAMERA   pixels of the webcam frame (e.g. 1280 x 720), origin top-left. Produced by the detector.
    BOARD    the logical whiteboard (e.g. 1600 x 900), origin top-left. The drawing engine works here.
    CANVAS   pixels of the on-screen widget that shows the board (changes whenever the window is resized).

    camera --(homography H, perspective correction)--> board --(scale + offset)--> canvas

The pointer is stored in BOARD coordinates. Only the very last step (board -> canvas) depends on the
window size, which is why the pointer stays correct when the window is resized or fullscreen is toggled.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from core.calibration import Calibration
from core.homography import apply_homography


# ----------------------------------------------------------------- board <-> canvas
def fit_board_in_canvas(board_size: tuple[float, float], canvas_size: tuple[float, float],
                        margin: float = 0.0) -> tuple[float, float, float, float]:
    """Largest rectangle with the board's aspect ratio, centred in the canvas: (x, y, w, h).
    scale = min(avail_w / board_w, avail_h / board_h)  -> aspect ratio is preserved (letterboxing)."""
    bw, bh = board_size
    cw, ch = canvas_size
    avail_w, avail_h = max(cw - 2 * margin, 10.0), max(ch - 2 * margin, 10.0)
    scale = min(avail_w / bw, avail_h / bh)
    w, h = bw * scale, bh * scale
    return (cw - w) / 2.0, (ch - h) / 2.0, w, h


def board_to_canvas(bx: float, by: float, board_size, rect) -> tuple[float, float]:
    """Board point -> canvas point, where `rect` is the board's rectangle in the canvas."""
    x, y, w, h = rect
    return x + bx * w / board_size[0], y + by * h / board_size[1]


def canvas_to_board(px: float, py: float, board_size, rect) -> tuple[float, float]:
    x, y, w, h = rect
    return (px - x) * board_size[0] / w, (py - y) * board_size[1] / h


# ----------------------------------------------------------------- camera -> board
@dataclass(frozen=True)
class BoardPoint:
    x: float
    y: float
    clamped: bool = False        # True when the point was within the edge margin and pushed onto the board


class CoordinateMapper:
    """Maps camera pixels to board coordinates with a calibration.

    * Different camera resolution: if frames now have another size but the same aspect ratio,
      the point is first rescaled to the calibration resolution (H' = H . S, S = diag(cw/fw, ch/fh, 1)).
    * Out-of-board rejection: points outside the board by more than `edge_margin` board pixels
      return None. Points inside the margin are clamped onto the border (a pointer on the very
      edge of the board must still work).
    * Invalid input (NaN/inf, a point on the horizon line) returns None.
    """

    def __init__(self, calibration: Calibration, edge_margin: float = 12.0) -> None:
        self.calibration = calibration
        self.edge_margin = float(edge_margin)
        self._cache: dict[tuple[int, int], np.ndarray] = {}

    @property
    def board_size(self) -> tuple[int, int]:
        return self.calibration.board_size

    def homography_for(self, frame_size: tuple[int, int] | None) -> np.ndarray:
        cal = self.calibration
        if frame_size is None or tuple(frame_size) == cal.camera_size:
            return cal.H
        key = (int(frame_size[0]), int(frame_size[1]))
        if key not in self._cache:
            scale = np.diag([cal.camera_size[0] / key[0], cal.camera_size[1] / key[1], 1.0])
            self._cache[key] = cal.H @ scale
        return self._cache[key]

    def camera_to_board(self, x: float, y: float,
                        frame_size: tuple[int, int] | None = None) -> BoardPoint | None:
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        bx, by = apply_homography(self.homography_for(frame_size), (x, y))
        if not (math.isfinite(bx) and math.isfinite(by)):
            return None
        w, h = self.board_size
        m = self.edge_margin
        if not (-m <= bx <= w + m and -m <= by <= h + m):
            return None
        cx, cy = min(max(bx, 0.0), float(w)), min(max(by, 0.0), float(h))
        return BoardPoint(cx, cy, clamped=(cx != bx or cy != by))

    def board_to_camera(self, bx: float, by: float, frame_size: tuple[int, int] | None = None):
        """Inverse mapping (used to draw the calibration grid on the camera image)."""
        H = self.homography_for(frame_size)
        out = apply_homography(np.linalg.inv(H), (bx, by))
        return None if not np.isfinite(out).all() else (float(out[0]), float(out[1]))
