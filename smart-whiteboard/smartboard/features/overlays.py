"""FEATURE: presenter overlays that work on top of ANY screen.

  Spotlight : everything is dimmed except a soft circle around the pointer
              (focus the audience on one spot).
  Magnifier : a round lens at the pointer shows the content around it enlarged
              (our own bilinear resize).
"""
from __future__ import annotations

import numpy as np

from ..graphics import primitives as P
from ..graphics import theme
from ..vision import imgproc


class Overlays:
    def __init__(self):
        self.spotlight = False
        self.magnifier = False
        self.spot_radius = 190
        self.lens_radius = 150
        self.lens_zoom = 2.2

    # ---- spotlight -------------------------------------------------------------------------
    def apply_spotlight(self, img: np.ndarray, pos, scale: float = 1.0):
        r = self.spot_radius * scale
        if pos is None:
            np.right_shift(img, 2, out=img)
            return
        bx0, by0, bx1, by1 = P._clip_box(img.shape, pos[0] - r - 40, pos[1] - r - 40, pos[0] + r + 40, pos[1] + r + 40)
        keep = img[by0:by1, bx0:bx1].copy()
        np.right_shift(img, 2, out=img)                           # 25 % brightness outside
        if bx1 > bx0 and by1 > by0:
            xx, yy = P._grid(bx0, by0, bx1, by1)
            d = np.hypot(xx - pos[0], yy - pos[1])
            cov = np.clip((r - d) / (0.35 * r), 0, 1)[..., None]  # soft edge
            reg = img[by0:by1, bx0:bx1].astype(np.float32)
            img[by0:by1, bx0:bx1] = (reg + (keep.astype(np.float32) - reg) * cov + 0.5).astype(np.uint8)
        P.aa_ring(img, pos[0], pos[1], r * 0.98, 3, theme.CYAN, 0.55)

    # ---- magnifier -------------------------------------------------------------------------
    def apply_magnifier(self, img: np.ndarray, pos, scale: float = 1.0):
        if pos is None:
            return
        r = int(self.lens_radius * scale)
        zoom = self.lens_zoom
        half = r / zoom
        x, y = pos
        sx0, sy0 = int(round(x - half)), int(round(y - half))
        side = int(round(2 * half))
        h, w = img.shape[:2]
        if side < 4:
            return
        # source square (clamped by edge replication)
        ys = np.clip(np.arange(sy0, sy0 + side), 0, h - 1)
        xs = np.clip(np.arange(sx0, sx0 + side), 0, w - 1)
        src = img[ys][:, xs]
        big = imgproc.resize_bilinear(src, 2 * r, 2 * r)
        bx0, by0 = int(round(x - r)), int(round(y - r))
        P.shadow_rrect(img, bx0, by0, bx0 + 2 * r, by0 + 2 * r, r, 14, 8, 0.5)
        ix0, iy0, ix1, iy1 = max(0, bx0), max(0, by0), min(w, bx0 + 2 * r), min(h, by0 + 2 * r)
        if ix1 > ix0 and iy1 > iy0:
            yy, xx = np.mgrid[iy0:iy1, ix0:ix1].astype(np.float32)
            cov = np.clip(r - np.hypot(xx + 0.5 - x, yy + 0.5 - y) + 0.5, 0, 1)[..., None]
            lens = big[iy0 - by0:iy1 - by0, ix0 - bx0:ix1 - bx0].astype(np.float32)
            reg = img[iy0:iy1, ix0:ix1].astype(np.float32)
            img[iy0:iy1, ix0:ix1] = (reg + (lens - reg) * cov + 0.5).astype(np.uint8)
        P.aa_ring(img, x, y, r, 6, theme.WHITE, 0.95)
        P.aa_ring(img, x, y, r + 4, 2, theme.CYAN, 0.9)
        # tiny crosshair at the lens centre
        P.aa_segment(img, (x - 8, y), (x + 8, y), 0.8, theme.WHITE, 0.7)
        P.aa_segment(img, (x, y - 8), (x, y + 8), 0.8, theme.WHITE, 0.7)

    # ---- entry point -----------------------------------------------------------------------
    def apply(self, img: np.ndarray, pos, scale: float = 1.0):
        if self.spotlight:
            self.apply_spotlight(img, pos, scale)
        if self.magnifier:
            self.apply_magnifier(img, pos, scale)
