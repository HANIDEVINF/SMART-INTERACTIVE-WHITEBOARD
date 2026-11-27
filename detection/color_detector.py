"""Colour-marker detector.

Pipeline (each step is a separate, testable function):

    BGR frame
      -> HSV conversion            (manual, NumPy)
      -> HSV range threshold       (manual, NumPy, hue wrap-around aware)
      -> morphological opening     (manual, NumPy)  -- despeckle
      -> connected-component labelling (OpenCV, justified in components.py)
      -> area filtering            (manual)
      -> centroid / bbox           (manual, NumPy moments)
      -> best-blob selection       (largest valid blob, with temporal
                                    consistency handled by the tracker)

The detector returns the centroid of the best blob in *camera pixel*
coordinates, or None when no valid marker is present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from detection.components import analyse_components
from detection.morphology import morphological_open
from detection.segmentation import color_mask, frame_to_hsv


@dataclass
class Detection:
    """A single marker detection in camera-image coordinates."""
    x: float
    y: float
    area: int
    bbox: tuple[int, int, int, int]


class ColorDetector:
    """HSV-based coloured-marker detector with configurable thresholds."""

    def __init__(self, hsv_ranges: dict, min_area: int = 400,
                 max_area_ratio: float = 0.25, downscale: Optional[int] = None,
                 target_width: int = 640):
        self.hsv_ranges = dict(hsv_ranges)
        self.min_area = int(min_area)
        self.max_area_ratio = float(max_area_ratio)
        # Detection runs on a sub-sampled image: the manual NumPy HSV
        # conversion costs ~100 ms at 1280x720 but ~20 ms at 640x360, and a
        # marker is still hundreds of pixels wide after halving.
        # downscale=None -> automatic (keep width near ``target_width``).
        self.downscale = downscale
        self.target_width = int(target_width)

    def stride_for(self, frame: np.ndarray) -> int:
        """Sub-sampling step used for ``frame`` (1 = full resolution)."""
        if self.downscale:
            return max(1, int(self.downscale))
        return max(1, int(frame.shape[1] // self.target_width))

    # -- configuration -----------------------------------------------------

    def update_ranges(self, hsv_ranges: dict) -> None:
        self.hsv_ranges = dict(hsv_ranges)

    # -- pipeline ----------------------------------------------------------

    def detect(self, frame: np.ndarray) -> Optional[Detection]:
        """Run the full pipeline on a BGR frame.

        Returns a Detection for the largest valid blob, or None.
        """
        if frame is None or frame.size == 0:
            return None

        step = self.stride_for(frame)
        small = frame[::step, ::step] if step > 1 else frame   # stride sampling
        # Areas shrink with the square of the step: scale the thresholds.
        min_area = max(1, int(round(self.min_area / (step * step))))

        hsv = frame_to_hsv(small)
        r = self.hsv_ranges
        mask = color_mask(hsv,
                          r["h_min"], r["h_max"],
                          r["s_min"], r["s_max"],
                          r["v_min"], r["v_max"])
        if not mask.any():
            return None

        # Remove salt-and-pepper noise before labelling.
        mask = morphological_open(mask, kernel_size=3)
        if not mask.any():
            return None

        max_area = int(mask.shape[0] * mask.shape[1] * self.max_area_ratio)
        blobs = analyse_components(mask, min_area=min_area,
                                   max_area=max_area)
        if not blobs:
            return None

        best = blobs[0]  # already sorted by descending area
        cx, cy = best["centroid"]
        x0, y0, x1, y1 = best["bbox"]
        # Back to full-resolution camera pixels.
        return Detection(x=cx * step, y=cy * step,
                         area=int(best["area"] * step * step),
                         bbox=(x0 * step, y0 * step, x1 * step, y1 * step))

    def detect_debug(self, frame: np.ndarray):
        """Like detect() but also returns intermediate images for the
        camera debug viewer: (mask, blobs)."""
        if frame is None or frame.size == 0:
            return None, []
        hsv = frame_to_hsv(frame)
        r = self.hsv_ranges
        mask = color_mask(hsv, r["h_min"], r["h_max"],
                          r["s_min"], r["s_max"], r["v_min"], r["v_max"])
        mask = morphological_open(mask, kernel_size=3)
        max_area = int(mask.shape[0] * mask.shape[1] * self.max_area_ratio)
        blobs = analyse_components(mask, min_area=self.min_area,
                                   max_area=max_area)
        return mask, blobs
