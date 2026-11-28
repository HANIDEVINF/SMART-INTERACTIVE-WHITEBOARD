"""Cached widget sprites with per-pixel alpha.

Rendering a rounded, shaded, anti-aliased button costs several ms, far too
much to repeat every frame.  A widget is therefore drawn ONCE into a sprite
and then just blitted.

Trick to get alpha out of drawing code that only knows opaque canvases:
draw the widget on a black tile and on a white tile.  Blending is linear in
the background, so
        black = C * a                (premultiplied colour)
        white = C * a + 255 * (1-a)
        =>  a = 1 - (white - black) / 255
"""
from __future__ import annotations

import numpy as np


class Sprite:
    """Premultiplied sprite split for fast blitting:
       * ``inner``  - the largest centred rectangle that is fully opaque -> plain slice copy;
       * the rest   - only pixels with visible alpha, as index lists -> blended with integers."""

    def __init__(self, pm: np.ndarray, alpha: np.ndarray, pad: int = 0):
        alpha = alpha.copy()
        alpha[alpha < 8] = 0                      # invisible shadow tails are dropped
        self.pm = pm
        self.a = alpha
        self.pad = pad
        self.h, self.w = alpha.shape
        opq = alpha == 255
        self.inner = None
        ys, xs = np.nonzero(opq)
        if len(ys):
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            for m in range(0, max(1, min(y1 - y0, x1 - x0) // 2)):
                if opq[y0 + m:y1 - m, x0 + m:x1 - m].all():
                    self.inner = (y0 + m, y1 - m, x0 + m, x1 - m)
                    break
        rest = alpha > 0
        if self.inner:
            a, b, c, d = self.inner
            rest = rest.copy()
            rest[a:b, c:d] = False
        self.py, self.px = np.nonzero(rest)
        self.pa = alpha[self.py, self.px].astype(np.uint16)
        self.inv = (255 - self.pa)[:, None]
        self.ppm = pm[self.py, self.px].astype(np.uint16)

    def blit(self, img: np.ndarray, x: int, y: int, alpha: float = 1.0) -> None:
        """Composite at (x, y) = top-left of the sprite *tile* (padding included)."""
        x, y = int(x), int(y)
        if alpha >= 0.999 and x >= 0 and y >= 0 and x + self.w <= img.shape[1] and y + self.h <= img.shape[0]:
            reg = img[y:y + self.h, x:x + self.w]
            if self.inner:
                a, b, c, d = self.inner
                reg[a:b, c:d] = self.pm[a:b, c:d]
            if len(self.py):
                cur = reg[self.py, self.px].astype(np.uint16)
                out = (cur * self.inv + 127) // 255 + self.ppm
                reg[self.py, self.px] = np.minimum(out, 255).astype(np.uint8)
            return
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(img.shape[1], x + self.w), min(img.shape[0], y + self.h)
        if x1 <= x0 or y1 <= y0:
            return
        sy, sx = slice(y0 - y, y1 - y), slice(x0 - x, x1 - x)
        a = (self.a[sy, sx].astype(np.float32) * alpha)[..., None]
        reg = img[y0:y1, x0:x1].astype(np.float32)
        out = reg * (1 - a / 255.0) + self.pm[sy, sx].astype(np.float32) * alpha
        img[y0:y1, x0:x1] = np.clip(out + 0.5, 0, 255).astype(np.uint8)


def render_sprite(w: int, h: int, draw, pad: int = 0) -> Sprite:
    """``draw(canvas, ox, oy)`` paints the widget with its top-left at (ox, oy)."""
    from .canvas import Canvas
    W, H = int(w) + 2 * pad, int(h) + 2 * pad
    black = np.zeros((H, W, 3), np.uint8)
    white = np.full((H, W, 3), 255, np.uint8)
    draw(Canvas.wrap(black), pad, pad)
    draw(Canvas.wrap(white), pad, pad)
    diff = (white.astype(np.int16) - black.astype(np.int16)).mean(axis=2)
    alpha = np.clip(255.0 - diff + 0.5, 0, 255).astype(np.uint8)
    alpha[alpha < 3] = 0
    return Sprite(black, alpha, pad)
