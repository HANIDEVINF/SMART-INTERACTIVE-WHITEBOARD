"""Calibration manager: owns the HomographyMapper, loads/saves the
calibration file, and validates clicked points."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from calibration.homography import HomographyMapper
from config.settings import load_calibration, save_calibration
from utils.geometry import is_clockwise_convex, is_valid_quad

logger = logging.getLogger(__name__)


class CalibrationManager:
    def __init__(self, board_size: tuple[int, int]):
        self.mapper = HomographyMapper()
        self.board_size = board_size
        self._clicked: list[tuple[float, float]] = []
        self.last_error: str = ""

    # -- state -------------------------------------------------------------

    @property
    def clicked_points(self):
        return list(self._clicked)

    def reset_clicks(self) -> None:
        self._clicked = []

    def undo_click(self) -> int:
        """Remove the most recent click.  Returns the new count."""
        if self._clicked:
            self._clicked.pop()
        return len(self._clicked)

    def add_click(self, point) -> int:
        """Record one calibration click.  Returns the new count (0..4)."""
        if len(self._clicked) < 4:
            self._clicked.append((float(point[0]), float(point[1])))
        return len(self._clicked)

    # -- computation -------------------------------------------------------

    def compute(self) -> Optional[np.ndarray]:
        """Compute the homography from the 4 clicked points.

        Returns the homography matrix, or None if the points are invalid.
        """
        if len(self._clicked) != 4:
            return None
        pts = np.asarray(self._clicked, dtype=np.float64)
        if not is_valid_quad(pts):
            self.last_error = "points too close together or collinear"
            logger.warning("Calibration points rejected as degenerate")
            return None
        if not is_clockwise_convex(pts):
            self.last_error = ("corners must be clicked in the order "
                               "top-left, top-right, bottom-right, bottom-left")
            logger.warning("Calibration points rejected: wrong order")
            return None
        try:
            H = self.mapper.calibrate(pts, self.board_size)
        except ValueError as exc:
            self.last_error = str(exc)
            logger.warning("Homography computation failed: %s", exc)
            return None
        self.last_error = ""
        return H

    def save(self) -> bool:
        """Persist the current calibration to config/calibration.json."""
        if not self.mapper.is_calibrated or len(self._clicked) != 4:
            return False
        return save_calibration(self._clicked, self.board_size, self.mapper.H)

    def load_saved(self) -> bool:
        "(Load a previously saved calibration, if present and valid.)"""
        data = load_calibration()
        if data is None:
            return False
        try:
            H = np.asarray(data["homography"], dtype=np.float64)
            if H.shape != (3, 3):
                return False
            saved_w, saved_h = (int(v) for v in data["board_size"])
            cur_w, cur_h = self.board_size
            if (saved_w, saved_h) != (int(cur_w), int(cur_h)) and saved_w > 0 \
                    and saved_h > 0:
                # The window size changed since calibration (e.g. moving to
                # the projector's resolution).  Board coordinates scale
                # linearly, so left-multiplying by a diagonal scale matrix
                # re-targets the same camera->board mapping exactly.
                S = np.diag([cur_w / saved_w, cur_h / saved_h, 1.0])
                H = S @ H
                logger.info("Calibration rescaled %dx%d -> %dx%d",
                            saved_w, saved_h, cur_w, cur_h)
                self.mapper.load(H, (cur_w, cur_h))
            else:
                self.mapper.load(H, data["board_size"])
            self._clicked = [tuple(p) for p in data["camera_points"]]
            logger.info("Calibration loaded from file")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load calibration: %s", exc)
            return False
