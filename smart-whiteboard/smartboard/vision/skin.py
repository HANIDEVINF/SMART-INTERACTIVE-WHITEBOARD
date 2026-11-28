"""Skin-colour segmentation (hand mode) - written from scratch with NumPy.

Why YCrCb and not RGB/HSV?  Y carries the brightness, Cr and Cb carry the colour.  Skin of very
different tones has a similar (Cr, Cb) cluster and only differs in Y, so two simple range tests on
Cr and Cb are enough and the result is far less sensitive to the amount of light than RGB.

    Y  = 0.299 R + 0.587 G + 0.114 B
    Cr = (R - Y) * 0.713 + 128
    Cb = (B - Y) * 0.564 + 128
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np


def bgr_to_ycrcb(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    f = img.astype(np.float32)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    return y, (r - y) * 0.713 + 128.0, (b - y) * 0.564 + 128.0


def skin_mask(y, cr, cb, cfg) -> np.ndarray:
    """Boolean mask of the pixels whose colour lies inside the skin box."""
    return ((cr >= cfg.skin_cr_min) & (cr <= cfg.skin_cr_max) &
            (cb >= cfg.skin_cb_min) & (cb <= cfg.skin_cb_max) & (y >= cfg.skin_y_min))


def learn_skin(frame: np.ndarray, box: Tuple[int, int, int, int]) -> Optional[dict]:
    """Adapt the skin box to the real hand: the user covers ``box`` (x0, y0, x1, y1 in camera
    pixels) with the open hand; we take the 5th..95th percentile of Cr and Cb there, widened a bit
    (the box may contain a few non-skin pixels, so percentiles are used instead of min / max).
    Returns the new config values, or None if the region is too small."""
    x0, y0, x1, y1 = [int(v) for v in box]
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if (x1 - x0) * (y1 - y0) < 400:
        return None
    y, cr, cb = bgr_to_ycrcb(frame[y0:y1, x0:x1])
    ok = y > 35                                           # ignore black pixels
    if ok.sum() < 300:
        return None
    lo_r, hi_r = np.percentile(cr[ok], [5, 95])
    lo_b, hi_b = np.percentile(cb[ok], [5, 95])
    pad = 7.0
    return {"skin_cr_min": float(lo_r - pad), "skin_cr_max": float(hi_r + pad),
            "skin_cb_min": float(lo_b - pad), "skin_cb_max": float(hi_b + pad),
            "skin_y_min": float(max(35.0, np.percentile(y[ok], 2) * 0.6))}
