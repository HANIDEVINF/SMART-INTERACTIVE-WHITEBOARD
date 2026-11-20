"""Red-dot pointer detection (colour-marker segmentation).

Method (all steps in imgproc.py, NumPy only):
  1. crop a search window around the last position (full board when lost),
  2. decimate the crop by ``downscale`` (speed),
  3. BGR -> HSV,
  4. threshold: hue near red AND saturated AND *bright*,
  5. add the saturated-white core of a strong laser (white pixels touching red ones),
  6. restrict to the calibrated board region (ROI mask),
  7. 3x3 majority filter (noise reduction),
  8. connected components, pick the best blob (compact, round, bright, near the last position),
  9. intensity-weighted centroid -> sub-pixel position in camera pixels.

Limits (also listed in the README / report):
  * other red/bright objects (red clothes, red projected content) can be
    mistaken for the dot -> brightness threshold, ROI, shape score and
    "stay close to the previous position" gating reduce this;
  * the UI never uses red so the projector does not create false dots;
  * a very strong laser saturates the sensor and looks white with a red
    halo -> the white core is added back; lowering the camera exposure
    (config.camera.exposure) helps even more.
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
    window: Optional[Tuple[int, int, int, int]] = None   # search window used (full-res px)


class RedDotDetector:
    def __init__(self, cfg: DetectionConfig):
        self.cfg = cfg
        self._roi: dict = {}                         # downscale -> bool ROI mask at that size
        self._roi_poly: Optional[np.ndarray] = None  # polygon in full-res camera px
        self.last_mask: Optional[np.ndarray] = None
        self.last_window = None

    # ---- region of interest ------------------------------------------------
    def set_roi(self, quad_cam: Optional[np.ndarray]) -> None:
        """quad_cam: 4x2 board corners in camera pixels (None = no ROI)."""
        if quad_cam is None:
            self._roi_poly = None
        else:
            c = quad_cam.mean(axis=0)
            self._roi_poly = c + (quad_cam - c) * (1.0 + self.cfg.roi_margin * 2)
        self._roi = {}     # rebuilt lazily for the actual frame size

    def _get_roi(self, frame_shape, k: int) -> Optional[np.ndarray]:
        if self._roi_poly is None:
            return None
        shape = (-(-frame_shape[0] // k), -(-frame_shape[1] // k))
        roi = self._roi.get(k)
        if roi is None or roi.shape != shape:
            roi = self._roi[k] = imgproc.polygon_mask(shape, self._roi_poly / k)
        return roi

    # ---- main entry --------------------------------------------------------
    def detect(self, frame_bgr: np.ndarray,
               prior: Optional[Tuple[float, float]] = None) -> Optional[Detection]:
        c = self.cfg
        H, W = frame_bgr.shape[:2]
        if prior is not None and c.search_window_px > 0:
            # tracking: small window at FULL resolution (the dot is 4x bigger than in the
            # decimated image -> much less flicker, better sub-pixel accuracy, still fast)
            r = int(c.search_window_px)
            x0, y0 = max(0, int(prior[0]) - r), max(0, int(prior[1]) - r)
            x1, y1 = min(W, int(prior[0]) + r), min(H, int(prior[1]) + r)
            det = self._detect_in(frame_bgr, (x0, y0, x1, y1), prior, 1)
            if det is not None:
                return det
        return self._detect_in(frame_bgr, (0, 0, W, H), prior, max(1, c.downscale))   # lost: whole board

    def _detect_in(self, frame, box, prior, k: int) -> Optional[Detection]:
        c = self.cfg
        af = (max(1, c.downscale) / k) ** 2          # area limits are given for the configured downscale
        x0, y0, x1, y1 = box
        small = frame[y0:y1:k, x0:x1:k]
        if small.size == 0:
            return None
        h, s, v = imgproc.bgr_to_hsv(small)
        mask = imgproc.threshold_red(h, s, v, c.hue_tolerance, c.sat_min, c.val_min)
        if mask.any():                                   # saturated white core of a strong laser
            core = (v >= c.core_v_min) & (s <= c.core_s_max)
            mask |= core & imgproc.dilate(mask, 2)
        roi = self._get_roi(frame.shape, k)
        if roi is not None:
            mask &= roi[y0 // k:y0 // k + mask.shape[0], x0 // k:x0 // k + mask.shape[1]]
        mask = imgproc.majority_filter(mask, c.denoise_neighbors)
        self.last_mask, self.last_window = mask, box

        link = imgproc.dilate(mask, c.merge_radius) if c.merge_radius > 0 else mask
        blobs = imgproc.connected_components(mask, link)
        best, best_score = None, 0.0
        for b in blobs:
            if not (c.min_area * af <= b.area <= c.max_area * af):
                continue
            score = self._score(b, v, prior, k, (x0, y0), af)
            if score > best_score:
                best, best_score = b, score
        if best is None:
            return None
        cx, cy = imgproc.weighted_centroid(best, v)
        # back to full-resolution pixel centre
        return Detection(x0 + cx * k + (k - 1) / 2.0, y0 + cy * k + (k - 1) / 2.0,
                         best.area, best_score, mask, box)

    def _score(self, b: imgproc.Blob, v: np.ndarray, prior, k: int, off, af: float = 1.0) -> float:
        """Higher = more dot-like: compact, round-ish, bright, near last position."""
        brightness = float(v[b.ys, b.xs].mean())
        roundness = b.aspect * min(1.0, b.fill_ratio / 0.6)   # a disc fills pi/4 ~ 0.79
        size = min(1.0, b.area / af / 6.0)                           # tiny blobs are less reliable
        score = brightness * roundness * size
        if prior is not None:
            d = np.hypot(off[0] + b.cx * k - prior[0], off[1] + b.cy * k - prior[1])
            score /= 1.0 + d / self.cfg.prior_gate_px
        return score
