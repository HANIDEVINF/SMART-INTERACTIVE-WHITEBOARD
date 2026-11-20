"""Red-dot pointer detection (colour-marker segmentation).

Method (all steps in imgproc.py, NumPy only):
  1. decimate the frame by ``downscale`` (speed),
  2. BGR -> HSV,
  3. threshold: hue near red AND saturated AND *bright*,
  4. restrict to the calibrated board region (ROI mask),
  5. 3x3 majority filter (noise reduction),
  6. connected components, pick the best blob,
  7. intensity-weighted centroid -> sub-pixel position in camera pixels.

Limits (also listed in the README / report):
  * other red/bright objects (red clothes, red projected content) can be
    mistaken for the dot -> brightness threshold, ROI, shape score and
    "stay close to the previous position" gating reduce this;
  * the UI never uses red so the projector does not create false dots;
  * a very strong laser saturates the sensor and looks white with a red
    halo -> lower the camera exposure (config.camera.exposure).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from ..config import DetectionConfig
from . import imgproc


@dataclass
class Detection:
    x: float                 # camera pixel coordinates (full resolution)
    y: float
    area: int                # in downscaled pixels
    score: float
    mask: Optional[np.ndarray] = None   # downscaled mask (for the debug view)


class RedDotDetector:
    def __init__(self, cfg: DetectionConfig):
        self.cfg = cfg
        self._roi: Optional[np.ndarray] = None       # bool mask at downscaled size
        self._roi_poly: Optional[np.ndarray] = None  # polygon in full-res camera px
        self.last_mask: Optional[np.ndarray] = None

    # ---- region of interest ------------------------------------------------
    def set_roi(self, quad_cam: Optional[np.ndarray]) -> None:
        """quad_cam: 4x2 board corners in camera pixels (None = no ROI)."""
        if quad_cam is None:
            self._roi_poly = None
        else:
            c = quad_cam.mean(axis=0)
            self._roi_poly = c + (quad_cam - c) * (1.0 + self.cfg.roi_margin * 2)
        self._roi = None   # rebuilt lazily for the actual frame size

    def _get_roi(self, shape) -> Optional[np.ndarray]:
        if self._roi_poly is None:
            return None
        if self._roi is None or self._roi.shape != shape:
            k = self.cfg.downscale
            self._roi = imgproc.polygon_mask(shape, self._roi_poly / k)
        return self._roi

    # ---- main entry --------------------------------------------------------
    def detect(self, frame_bgr: np.ndarray,
               prior: Optional[Tuple[float, float]] = None) -> Optional[Detection]:
        c = self.cfg
        k = max(1, c.downscale)
        small = frame_bgr[::k, ::k]
        h, s, v = imgproc.bgr_to_hsv(small)
        mask = imgproc.threshold_red(h, s, v, c.hue_tolerance, c.sat_min, c.val_min)

        roi = self._get_roi(mask.shape)
        if roi is not None:
            mask &= roi
        mask = imgproc.majority_filter(mask, c.denoise_neighbors)
        self.last_mask = mask

        link = imgproc.dilate(mask, c.merge_radius) if c.merge_radius > 0 else mask
        blobs = imgproc.connected_components(mask, link)
        best, best_score = None, 0.0
        for b in blobs:
            if not (c.min_area <= b.area <= c.max_area):
                continue
            score = self._score(b, v, prior, k)
            if score > best_score:
                best, best_score = b, score
        if best is None:
            return None
        cx, cy = imgproc.weighted_centroid(best, v)
        # back to full-resolution pixel centre
        return Detection(cx * k + (k - 1) / 2.0, cy * k + (k - 1) / 2.0,
                         best.area, best_score, mask)

    def _score(self, b: imgproc.Blob, v: np.ndarray, prior, k: int) -> float:
        """Higher = more dot-like: compact, round-ish, bright, near last position."""
        brightness = float(v[b.ys, b.xs].mean())
        roundness = b.aspect * min(1.0, b.fill_ratio / 0.6)   # a disc fills pi/4 ~ 0.79
        size = min(1.0, b.area / 6.0)                           # tiny blobs are less reliable
        score = brightness * roundness * size
        if prior is not None:
            d = np.hypot(b.cx * k - prior[0], b.cy * k - prior[1])
            score /= 1.0 + d / self.cfg.prior_gate_px
        return score
