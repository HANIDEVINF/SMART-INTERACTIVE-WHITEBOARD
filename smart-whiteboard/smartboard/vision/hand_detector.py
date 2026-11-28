"""Hand pointer detection: skin segmentation + fingertip (same interface as RedDotDetector).

Pipeline (all steps in NumPy, see skin.py / fingertip.py / imgproc.py):
  1. decimate the frame (hand_downscale),
  2. BGR -> YCrCb, threshold Cr / Cb / Y -> skin mask,
  3. keep only the calibrated board region (ROI),
  4. 3x3 majority filter, then connected components,
  5. choose the hand blob: right size, close to the previous position,
  6. fingertip = farthest blob point from the border where the arm enters.

Limits (to explain in the report): skin-like colours in the room (wood, cardboard, a face in front of
the board), projected colours that shift the apparent skin colour (the UI avoids orange / yellow
fills), strong back light, very dark skin under weak light.  Mitigations: ROI, size and distance
gating, one-euro filter, "Learn skin colour" (Settings) which fits the thresholds to the real hand
under the real projector light.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from ..config import DetectionConfig
from . import fingertip, imgproc, skin
from .labeling import label_components
from .detector import Detection


class HandDetector:
    def __init__(self, cfg: DetectionConfig):
        self.cfg = cfg
        self._roi_poly: Optional[np.ndarray] = None
        self._roi = None
        self._border = None
        self.last_mask: Optional[np.ndarray] = None

    def set_roi(self, quad_cam: Optional[np.ndarray]) -> None:
        if quad_cam is None:
            self._roi_poly = None
        else:
            c = quad_cam.mean(axis=0)
            self._roi_poly = c + (quad_cam - c) * (1.0 + self.cfg.roi_margin * 2)
        self._roi = self._border = None

    def _regions(self, shape, k):
        sh = (-(-shape[0] // k), -(-shape[1] // k))
        if self._roi is None or self._roi.shape != sh:
            self._roi = imgproc.polygon_mask(sh, self._roi_poly / k) if self._roi_poly is not None else None
            self._border = fingertip.border_mask(sh, self._roi)
        return self._roi, self._border

    def detect(self, frame_bgr: np.ndarray, prior: Optional[Tuple[float, float]] = None) -> Optional[Detection]:
        c = self.cfg
        k = max(1, c.hand_downscale)
        small = frame_bgr[::k, ::k]
        y, cr, cb = skin.bgr_to_ycrcb(small)
        mask = skin.skin_mask(y, cr, cb, c)
        roi, border = self._regions(frame_bgr.shape, k)
        if roi is not None:
            mask &= roi
        mask = imgproc.majority_filter(mask, 5)
        self.last_mask = mask
        lab = label_components(mask)
        if lab.max() == 0:
            return None
        n = int(lab.max()) + 1
        flat = lab.ravel()
        areas = np.bincount(flat, minlength=n)
        yy, xx = np.indices(mask.shape)
        cxs = np.bincount(flat, xx.ravel(), n) / np.maximum(areas, 1)       # centroid of every blob
        cys = np.bincount(flat, yy.ravel(), n) / np.maximum(areas, 1)
        max_area = c.hand_max_frac * mask.size
        best, best_score = 0, 0.0
        for l in range(1, n):
            if not (c.hand_min_area <= areas[l] <= max_area):
                continue
            score = min(1.0, areas[l] / 400.0)
            if prior is not None:
                d = np.hypot(cxs[l] * k - prior[0], cys[l] * k - prior[1])
                score /= 1.0 + d / max(c.prior_gate_px, 1.0)
            if score > best_score:
                best, best_score = l, score
        if best == 0:
            return None
        ys_, xs_ = np.nonzero(lab == best)
        (tx, ty), (bx, by) = fingertip.find_fingertip(xs_.astype(np.float32), ys_.astype(np.float32),
                                                      border[ys_, xs_], c.tip_radius)
        tip = (tx * k + (k - 1) / 2.0, ty * k + (k - 1) / 2.0)
        base = (bx * k + (k - 1) / 2.0, by * k + (k - 1) / 2.0)
        # coarse tip found on the decimated image -> sharpen it on the full-resolution pixels
        H, W = frame_bgr.shape[:2]
        r = 54
        x0, y0 = max(0, int(tip[0]) - r), max(0, int(tip[1]) - r)
        x1, y1 = min(W, int(tip[0]) + r), min(H, int(tip[1]) + r)
        y_, cr_, cb_ = skin.bgr_to_ycrcb(frame_bgr[y0:y1, x0:x1])
        crop = imgproc.majority_filter(skin.skin_mask(y_, cr_, cb_, c), 5)      # no stray noise pixels
        tip = fingertip.refine_tip(crop, tip, base, (x0, y0))
        return Detection(tip[0], tip[1], int(areas[best]), best_score, mask, None)
