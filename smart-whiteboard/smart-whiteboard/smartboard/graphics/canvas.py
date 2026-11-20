"""Canvas: the frame buffer that is projected on the board.

Shapes use primitives.py (NumPy).  Text uses cv2.putText only because
rasterising a font is outside the scope of the project (justified use of a
predefined function).
"""
from __future__ import annotations

from typing import Tuple

import numpy as np

from . import primitives as P


class Canvas:
    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.img = np.zeros((height, width, 3), np.uint8)

    def clear(self, color):
        self.img[:] = color

    # shapes ---------------------------------------------------------------
    def rect(self, x0, y0, x1, y1, color, alpha=1.0):
        P.fill_rect(self.img, x0, y0, x1, y1, color, alpha)

    def rrect(self, x0, y0, x1, y1, r, color, alpha=1.0):
        P.fill_rounded_rect(self.img, x0, y0, x1, y1, r, color, alpha)

    def outline(self, x0, y0, x1, y1, color, t=2):
        P.rect_outline(self.img, x0, y0, x1, y1, color, t)

    def circle(self, c, r, color):
        P.fill_circle(self.img, c, r, color)

    def ring(self, c, r, t, color):
        P.ring(self.img, c, r, t, color)

    def line(self, a, b, color, width=2):
        P.draw_segment(self.img, a, b, color, width / 2.0)

    def polygon(self, pts, color):
        P.fill_polygon(self.img, pts, color)

    # text ---------------------------------------------------------------------
    def text_size(self, s: str, scale: float = 1.0, thick: int = 2) -> Tuple[int, int]:
        import cv2
        (w, h), base = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        return w, h + base

    def text(self, s: str, x, y, scale=1.0, color=(255, 255, 255), thick=2, anchor="lt"):
        """anchor: two letters, horizontal l/c/r + vertical t/m/b."""
        import cv2
        w, h = self.text_size(s, scale, thick)
        ox = {"l": 0, "c": -w / 2, "r": -w}[anchor[0]]
        oy = {"t": h, "m": h / 2, "b": 0}[anchor[1]]
        cv2.putText(self.img, s, (int(x + ox), int(y + oy - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, color, thick, cv2.LINE_AA)

    def blit(self, src: np.ndarray, x: int, y: int):
        """Copy ``src`` with its top-left at (x, y), clipped to the canvas."""
        h, w = src.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 > x0 and y1 > y0:
            self.img[y0:y1, x0:x1] = src[y0 - y:y1 - y, x0 - x:x1 - x]
