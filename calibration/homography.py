"""Homography wrapper used by the calibration manager.

The actual DLT solver lives in ``utils.geometry``; this module provides a
small stateful helper that owns the current homography and applies it to
detections.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from utils.geometry import compute_homography, transform_points


class HomographyMapper:
    """Camera-pixel -> board-coordinate mapper."""

    def __init__(self):
        self.H: Optional[np.ndarray] = None
        self.board_size: Optional[tuple[int, int]] = None

    @property
    def is_calibrated(self) -> bool:
        return self.H is not None

    def calibrate(self, camera_points, board_size) -> np.ndarray:
        """Compute and store the homography.

        ``camera_points``: 4 clicked points in camera pixels ordered
        TL, TR, BR, BL.  ``board_size``: (width, height) of the board in
        board coordinates.  Returns the homography matrix.
        """
        w, h = board_size
        dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float64)
        self.H = compute_homography(np.asarray(camera_points, dtype=np.float64), dst)
        self.board_size = (int(w), int(h))
        return self.H

    def load(self, homography, board_size) -> None:
        self.H = np.asarray(homography, dtype=np.float64)
        self.board_size = (int(board_size[0]), int(board_size[1]))

    def camera_to_board(self, point):
        """Map one camera point to board coordinates, or None."""
        if self.H is None:
            return None
        xy = transform_points(self.H, np.asarray(point, dtype=np.float64))
        return float(xy[0]), float(xy[1])

    def board_corners(self):
        """The four board corners in board coordinates (TL,TR,BR,BL)."""
        if self.board_size is None:
            return None
        w, h = self.board_size
        return [(0, 0), (w, 0), (w, h), (0, h)]
