"""Segmentation: HSV conversion + range masking.

Thin, well-named wrappers around the manual NumPy primitives in
``utils.image_processing`` so the detection pipeline reads clearly.
"""

from __future__ import annotations

import numpy as np

from utils.image_processing import bgr_to_hsv, in_hsv_range


def frame_to_hsv(frame: np.ndarray) -> np.ndarray:
    """BGR frame -> HSV float array (H in degrees)."""
    return bgr_to_hsv(frame)


def color_mask(hsv: np.ndarray, h_min, h_max, s_min, s_max,
               v_min, v_max) -> np.ndarray:
    """Boolean mask of pixels inside the configured HSV box."""
    return in_hsv_range(hsv, h_min, h_max, s_min, s_max, v_min, v_max)
