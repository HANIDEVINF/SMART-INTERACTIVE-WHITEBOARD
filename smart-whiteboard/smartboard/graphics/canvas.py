"""Canvas: the frame buffer that is projected on the board.

Shapes -> graphics/primitives.py (NumPy, anti-aliased signed-distance fields).
Text   -> graphics/text.py (cached TrueType masks).
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from . import primitives as P
from . import theme
from .text import get_text


class Canvas:
    def __init__(self, width: int, height: int, img: Optional[np.ndarray] = None):
        self.w, self.h = width, height
        self.img = img if img is not None else np.zeros((height, width, 3), np.uint8)
        self._bg: Optional[np.ndarray] = None
        self._bg_cache = {}

    @classmethod
    def wrap(cls, img: np.ndarray) -> "Canvas":
        return cls(img.shape[1], img.shape[0], img)

    # ---- backdrop -----------------------------------------------------------------
    def clear(self, color=None, orbs=None):
        """Fill with ``color`` or, when None, the cached gradient backdrop
        (``orbs`` = a hashable tuple of light spots, see theme.make_background)."""
        if color is None:
            key = orbs or ()
            if key not in self._bg_cache:
                self._bg_cache[key] = theme.make_background(self.w, self.h, key)
            self.img[:] = self._bg_cache[key]
        else:
            self.img[:] = color

    # ---- shapes -----------------------------------------------------------------------
    def rect(self, x0, y0, x1, y1, color, alpha=1.0):
        P.fill_rect(self.img, x0, y0, x1, y1, color, alpha)

    def gradient_rect(self, x0, y0, x1, y1, top, bottom):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        self.img[y0:y1, x0:x1] = P.vertical_gradient(y1 - y0, x1 - x0, top, bottom)

    def rrect(self, x0, y0, x1, y1, r, color, alpha=1.0, color2=None, outline=0.0):
        P.aa_rrect(self.img, x0, y0, x1, y1, r, color, alpha, color2, outline)

    def outline(self, x0, y0, x1, y1, color, t=2, r=0):
        if r:
            P.aa_rrect(self.img, x0, y0, x1, y1, r, color, 1.0, None, t)
        else:
            P.rect_outline(self.img, x0, y0, x1, y1, color, t)

    def circle(self, c, r, color, alpha=1.0):
        P.aa_circle(self.img, c[0], c[1], r, color, alpha)

    def ring(self, c, r, t, color, alpha=1.0):
        P.aa_ring(self.img, c[0], c[1], r, t, color, alpha)

    def line(self, a, b, color, width=2, alpha=1.0):
        P.aa_segment(self.img, a, b, width / 2.0, color, alpha)

    def polygon(self, pts, color, alpha=1.0):
        P.aa_polygon(self.img, pts, color, alpha)

    def ellipse(self, c, rx, ry, t, color, alpha=1.0):
        P.aa_ellipse_outline(self.img, c[0], c[1], rx, ry, t, color, alpha)

    def glow(self, c, r, color, strength=1.0):
        P.glow(self.img, c[0], c[1], r, color, strength)

    def shadow(self, x0, y0, x1, y1, r, blur=14.0, dy=8.0, opacity=0.55):
        P.shadow_rrect(self.img, x0, y0, x1, y1, r, blur, dy, opacity)

    # ---- text ---------------------------------------------------------------------------
    def text_size(self, s: str, size: int, bold: bool = False) -> Tuple[int, int]:
        return get_text().size(s, int(size), bold)

    def text(self, s: str, x, y, size=28, color=(255, 255, 255), bold=False, anchor="lt", alpha=1.0):
        """size = font height in pixels; anchor = h(l/c/r) + v(t/m/b)."""
        get_text().draw(self.img, s, x, y, size, color, bold, anchor, alpha)

    def text_fit(self, s, x, y, size, max_w, color=(255, 255, 255), bold=False, anchor="lt"):
        self.text(get_text().fit(s, int(size), int(max_w), bold), x, y, size, color, bold, anchor)

    # ---- images / sprites ----------------------------------------------------------------
    def blit(self, src: np.ndarray, x: int, y: int):
        """Copy ``src`` with its top-left at (x, y), clipped to the canvas."""
        h, w = src.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 > x0 and y1 > y0:
            self.img[y0:y1, x0:x1] = src[y0 - y:y1 - y, x0 - x:x1 - x]

    def sprite(self, spr, x, y, alpha=1.0):
        spr.blit(self.img, x - spr.pad, y - spr.pad, alpha)
