"""FEATURE: image display + zoom + pan + return to the original view.

State = (image index, zoom, centre).  zoom = 1 means "fit the image in the
viewport"; centre is the image point shown in the middle of the viewport.
The visible region is resampled with our own bilinear routine.
"""
from __future__ import annotations

import glob
import os
from typing import List, Optional, Tuple

import numpy as np

from ..vision import imgproc

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 1.0, 8.0, 1.35


class ImageViewer:
    def __init__(self, folder: str):
        self.paths: List[str] = sorted(
            p for ext in ("png", "jpg", "jpeg", "bmp") for p in glob.glob(os.path.join(folder, f"*.{ext}")))
        self.idx = 0
        self.img: Optional[np.ndarray] = None
        self.zoom = 1.0
        self.center = (0.0, 0.0)
        self.panning = False          # LEFT click on the image toggles panning
        self._cache_key = None
        self._cache = None
        self._load()

    # ---- loading ---------------------------------------------------------------------
    def _load(self):
        self.img = None
        if not self.paths:
            return
        import cv2  # decoding PNG/JPEG files = predefined function (justified: file format codec)
        self.img = cv2.imread(self.paths[self.idx], cv2.IMREAD_COLOR)
        self.reset_view()

    @property
    def name(self) -> str:
        return os.path.basename(self.paths[self.idx]) if self.paths else "(no image)"

    def next(self, step: int = 1):
        if self.paths:
            self.idx = (self.idx + step) % len(self.paths)
            self._load()

    # ---- view control ----------------------------------------------------------------------
    def reset_view(self):
        self.zoom = 1.0
        self.panning = False
        if self.img is not None:
            h, w = self.img.shape[:2]
            self.center = (w / 2.0, h / 2.0)

    def zoom_in(self):
        self.set_zoom(self.zoom * ZOOM_STEP)

    def zoom_out(self):
        self.set_zoom(self.zoom / ZOOM_STEP)

    def set_zoom(self, z: float):
        self.zoom = float(min(max(z, ZOOM_MIN), ZOOM_MAX))
        self._clamp_center()

    def pan_by(self, dx_view: float, dy_view: float, vw: int, vh: int):
        """Move the image with the pointer: pointer delta (view px) -> image delta."""
        s = self._scale(vw, vh)
        self.center = (self.center[0] - dx_view / s, self.center[1] - dy_view / s)
        self._clamp_center()

    # ---- geometry ----------------------------------------------------------------------------------
    def _scale(self, vw, vh) -> float:
        """view pixels per image pixel."""
        h, w = self.img.shape[:2]
        return min(vw / w, vh / h) * self.zoom

    def _clamp_center(self):
        if self.img is None:
            return
        h, w = self.img.shape[:2]
        self.center = (min(max(self.center[0], 0), w), min(max(self.center[1], 0), h))

    # ---- rendering -----------------------------------------------------------------------------------
    def render(self, vw: int, vh: int, bg, fast: bool = False) -> np.ndarray:
        """Return a (vh, vw, 3) image of the current view."""
        out = np.empty((vh, vw, 3), np.uint8)
        out[:] = bg
        if self.img is None:
            return out
        key = (vw, vh, round(self.zoom, 4), round(self.center[0], 1), round(self.center[1], 1), self.idx, fast)
        if key == self._cache_key:
            return self._cache
        h, w = self.img.shape[:2]
        s = self._scale(vw, vh)
        # region of the source image visible in the viewport
        x0, y0 = self.center[0] - vw / (2 * s), self.center[1] - vh / (2 * s)
        x1, y1 = x0 + vw / s, y0 + vh / s
        cx0, cy0, cx1, cy1 = max(0, int(np.floor(x0))), max(0, int(np.floor(y0))), \
            min(w, int(np.ceil(x1))), min(h, int(np.ceil(y1)))
        if cx1 > cx0 and cy1 > cy0:
            crop = self.img[cy0:cy1, cx0:cx1]
            # destination rectangle of this crop inside the viewport
            dx0, dy0 = int(round((cx0 - x0) * s)), int(round((cy0 - y0) * s))
            dw, dh = max(1, int(round((cx1 - cx0) * s))), max(1, int(round((cy1 - cy0) * s)))
            res = (imgproc.resize_nearest if fast else imgproc.resize_bilinear)(crop, dw, dh)
            sx0, sy0 = max(0, -dx0), max(0, -dy0)
            ex0, ey0 = max(0, dx0), max(0, dy0)
            ww, hh = min(dw - sx0, vw - ex0), min(dh - sy0, vh - ey0)
            if ww > 0 and hh > 0:
                out[ey0:ey0 + hh, ex0:ex0 + ww] = res[sy0:sy0 + hh, sx0:sx0 + ww]
        self._cache_key, self._cache = key, out
        return out
