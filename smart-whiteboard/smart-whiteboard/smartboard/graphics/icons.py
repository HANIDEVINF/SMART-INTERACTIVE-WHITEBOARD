"""Vector icons drawn with the anti-aliased primitives (no image files).

Each icon is a small function that paints white shapes on black in a unit
square; the result is cached as an alpha mask (per name and size) and tinted
with any colour when drawn.   draw(canvas, "pen", cx, cy, size, colour)
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np

from . import primitives as P

W = (255, 255, 255)


class _Pen:
    """Tiny drawing helper: coordinates are fractions (0..1) of the icon size."""

    def __init__(self, img, s):
        self.img, self.s = img, s
        self.t = max(1.6, s * 0.075)          # default stroke thickness

    def p(self, x, y):
        return (x * self.s, y * self.s)

    def line(self, x0, y0, x1, y1, t=None):
        P.aa_segment(self.img, self.p(x0, y0), self.p(x1, y1), (t or self.t) / 2, W)

    def poly_line(self, pts, t=None):
        for a, b in zip(pts[:-1], pts[1:]):
            self.line(a[0], a[1], b[0], b[1], t)

    def circle(self, x, y, r):
        P.aa_circle(self.img, x * self.s, y * self.s, r * self.s, W)

    def ring(self, x, y, r, t=None):
        P.aa_ring(self.img, x * self.s, y * self.s, r * self.s, t or self.t, W)

    def poly(self, pts):
        P.aa_polygon(self.img, [self.p(*q) for q in pts], W)

    def rrect(self, x0, y0, x1, y1, r, outline=0.0):
        s = self.s
        P.aa_rrect(self.img, x0 * s, y0 * s, x1 * s, y1 * s, r * s, W, 1.0, None, outline)

    def arc(self, x, y, r, a0, a1, t=None, n=24):
        pts = [(x + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                y + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.poly_line(pts, t)


def _home(g):
    g.poly([(0.5, 0.14), (0.9, 0.5), (0.1, 0.5)])
    g.rrect(0.22, 0.46, 0.78, 0.86, 0.05)


def _pen(g):
    g.poly([(0.78, 0.12), (0.9, 0.24), (0.34, 0.8), (0.16, 0.84), (0.2, 0.66)])
    g.line(0.12, 0.9, 0.5, 0.9, g.t * 0.8)


def _image(g):
    g.rrect(0.1, 0.18, 0.9, 0.82, 0.08, g.t)
    g.circle(0.34, 0.4, 0.07)
    g.poly([(0.14, 0.76), (0.4, 0.5), (0.58, 0.66), (0.72, 0.52), (0.88, 0.76)])


def _shapes(g):
    g.rrect(0.1, 0.12, 0.46, 0.48, 0.05)
    g.circle(0.72, 0.3, 0.19)
    g.poly([(0.3, 0.56), (0.5, 0.9), (0.1, 0.9)])
    g.rrect(0.56, 0.58, 0.9, 0.9, 0.16, g.t)


def _book(g):
    g.poly([(0.5, 0.22), (0.5, 0.84), (0.1, 0.76), (0.1, 0.16)])
    g.poly([(0.5, 0.22), (0.9, 0.16), (0.9, 0.76), (0.5, 0.84)])


def _gear(g):
    for i in range(8):
        a = math.radians(i * 45)
        g.line(0.5 + 0.28 * math.cos(a), 0.5 + 0.28 * math.sin(a),
               0.5 + 0.4 * math.cos(a), 0.5 + 0.4 * math.sin(a), g.s and g.t * 1.9)
    g.ring(0.5, 0.5, 0.26, g.t * 1.3)
    g.ring(0.5, 0.5, 0.09, g.t)


def _eraser(g):
    g.poly([(0.12, 0.62), (0.52, 0.18), (0.88, 0.46), (0.5, 0.84), (0.3, 0.84)])
    g.line(0.18, 0.9, 0.9, 0.9, g.t)


def _undo(g):
    g.arc(0.52, 0.56, 0.28, 180, 330, g.t * 1.2)
    g.poly([(0.12, 0.38), (0.4, 0.34), (0.22, 0.62)])


def _redo(g):
    g.arc(0.48, 0.56, 0.28, 210, 360, g.t * 1.2)
    g.poly([(0.88, 0.38), (0.6, 0.34), (0.78, 0.62)])


def _trash(g):
    g.rrect(0.22, 0.28, 0.78, 0.9, 0.06, g.t)
    g.line(0.12, 0.26, 0.88, 0.26)
    g.line(0.4, 0.12, 0.6, 0.12)
    g.line(0.5, 0.42, 0.5, 0.76)


def _plus(g):
    g.line(0.5, 0.18, 0.5, 0.82, g.t * 1.3)
    g.line(0.18, 0.5, 0.82, 0.5, g.t * 1.3)


def _minus(g):
    g.line(0.18, 0.5, 0.82, 0.5, g.t * 1.3)


def _reset(g):
    g.arc(0.5, 0.5, 0.3, -40, 250, g.t * 1.2)
    g.poly([(0.74, 0.12), (0.84, 0.42), (0.54, 0.34)])


def _left(g):
    g.poly_line([(0.62, 0.16), (0.3, 0.5), (0.62, 0.84)], g.t * 1.4)


def _right(g):
    g.poly_line([(0.38, 0.16), (0.7, 0.5), (0.38, 0.84)], g.t * 1.4)


def _back(g):
    g.line(0.18, 0.5, 0.84, 0.5, g.t * 1.2)
    g.poly_line([(0.44, 0.2), (0.16, 0.5), (0.44, 0.8)], g.t * 1.2)


def _check(g):
    g.poly_line([(0.16, 0.54), (0.4, 0.78), (0.86, 0.24)], g.t * 1.5)


def _cross(g):
    g.line(0.2, 0.2, 0.8, 0.8, g.t * 1.4)
    g.line(0.8, 0.2, 0.2, 0.8, g.t * 1.4)


def _spotlight(g):
    g.poly([(0.5, 0.52), (0.14, 0.9), (0.86, 0.9)])
    g.circle(0.5, 0.26, 0.17)
    g.ring(0.5, 0.26, 0.26, g.t * 0.8)


def _magnifier(g):
    g.ring(0.42, 0.42, 0.26, g.t * 1.3)
    g.line(0.62, 0.62, 0.9, 0.9, g.t * 1.8)
    g.line(0.42, 0.3, 0.42, 0.54, g.t * 0.9)
    g.line(0.3, 0.42, 0.54, 0.42, g.t * 0.9)


def _quiz(g):
    g.ring(0.5, 0.5, 0.4, g.t * 1.1)
    g.arc(0.5, 0.4, 0.13, 180, 400, g.t * 1.2)
    g.line(0.5, 0.52, 0.5, 0.62, g.t * 1.2)
    g.circle(0.5, 0.76, 0.045)


def _timer(g):
    g.ring(0.5, 0.56, 0.34, g.t * 1.2)
    g.line(0.5, 0.56, 0.5, 0.34, g.t * 1.2)
    g.line(0.5, 0.56, 0.64, 0.64, g.t * 1.2)
    g.line(0.4, 0.1, 0.6, 0.1, g.t * 1.2)


def _target(g):
    g.ring(0.5, 0.5, 0.36, g.t)
    g.ring(0.5, 0.5, 0.16, g.t)
    g.circle(0.5, 0.5, 0.05)
    for a in (0, 90, 180, 270):
        r = math.radians(a)
        g.line(0.5 + 0.36 * math.cos(r), 0.5 + 0.36 * math.sin(r),
               0.5 + 0.48 * math.cos(r), 0.5 + 0.48 * math.sin(r), g.t)


def _camera(g):
    g.rrect(0.08, 0.28, 0.92, 0.84, 0.08, g.t)
    g.rrect(0.34, 0.16, 0.66, 0.3, 0.04)
    g.ring(0.5, 0.56, 0.16, g.t)


def _save(g):
    g.rrect(0.14, 0.14, 0.86, 0.86, 0.08, g.t)
    g.rrect(0.3, 0.14, 0.7, 0.4, 0.02)
    g.rrect(0.3, 0.56, 0.7, 0.86, 0.03)


def _line(g):
    g.line(0.16, 0.84, 0.84, 0.16, g.t * 1.4)
    g.circle(0.16, 0.84, 0.07)
    g.circle(0.84, 0.16, 0.07)


def _rect(g):
    g.rrect(0.14, 0.24, 0.86, 0.76, 0.05, g.t * 1.3)


def _circle(g):
    g.ring(0.5, 0.5, 0.36, g.t * 1.3)


def _arrow(g):
    g.line(0.16, 0.84, 0.76, 0.24, g.t * 1.4)
    g.poly([(0.88, 0.12), (0.84, 0.5), (0.5, 0.16)])


def _play(g):
    g.poly([(0.28, 0.16), (0.84, 0.5), (0.28, 0.84)])


def _pause(g):
    g.rrect(0.22, 0.16, 0.42, 0.84, 0.04)
    g.rrect(0.58, 0.16, 0.78, 0.84, 0.04)


def _grid(g):
    g.rrect(0.12, 0.12, 0.88, 0.88, 0.04, g.t)
    g.line(0.5, 0.12, 0.5, 0.88, g.t * 0.8)
    g.line(0.12, 0.5, 0.88, 0.5, g.t * 0.8)


def _sun(g):
    g.circle(0.5, 0.5, 0.2)
    for i in range(8):
        a = math.radians(i * 45)
        g.line(0.5 + 0.3 * math.cos(a), 0.5 + 0.3 * math.sin(a),
               0.5 + 0.42 * math.cos(a), 0.5 + 0.42 * math.sin(a), g.t)


def _moon(g):
    g.circle(0.5, 0.5, 0.36)
    # carve a bite out of the disc (black on black = erase)
    P.aa_circle(g.img, 0.64 * g.s, 0.4 * g.s, 0.3 * g.s, (0, 0, 0))


def _pointer(g):
    g.poly([(0.22, 0.1), (0.22, 0.78), (0.4, 0.62), (0.52, 0.9), (0.64, 0.84), (0.52, 0.58), (0.76, 0.58)])


def _wifi(g):
    for r in (0.18, 0.32, 0.46):
        g.arc(0.5, 0.78, r, 225, 315, g.t * 1.1)
    g.circle(0.5, 0.78, 0.05)


def _star(g):
    g.poly([tuple(q / g.s for q in pt) for pt in P.star_points(0.5 * g.s, 0.52 * g.s, 0.44 * g.s, 0.19 * g.s)])


def _power(g):
    g.arc(0.5, 0.52, 0.32, -60, 240, g.t * 1.3)
    g.line(0.5, 0.1, 0.5, 0.5, g.t * 1.3)


def _next(g):
    g.poly([(0.16, 0.2), (0.56, 0.5), (0.16, 0.8)])
    g.rrect(0.66, 0.2, 0.84, 0.8, 0.04)


def _prev(g):
    g.poly([(0.84, 0.2), (0.44, 0.5), (0.84, 0.8)])
    g.rrect(0.16, 0.2, 0.34, 0.8, 0.04)


ICONS = {k[1:]: v for k, v in list(globals().items()) if k.startswith("_") and callable(v)
         and k not in ("_Pen",) and v.__module__ == __name__ and k[1:] not in ("", )}
ICONS.pop("Pen", None)

_cache: Dict[Tuple[str, int], np.ndarray] = {}


def mask(name: str, size: int) -> np.ndarray:
    key = (name, size)
    if key not in _cache:
        ss = 2                                          # draw at 2x then box-downsample = smoother
        big = np.zeros((size * ss, size * ss, 3), np.uint8)
        ICONS.get(name, _target)(_Pen(big, size * ss))
        m = big[..., 0].astype(np.float32)
        m = m.reshape(size, ss, size, ss).mean(axis=(1, 3))
        _cache[key] = np.clip(m + 0.5, 0, 255).astype(np.uint8)
    return _cache[key]


def draw(canvas, name: str, cx: float, cy: float, size: int, color, alpha: float = 1.0):
    """Draw icon ``name`` centred on (cx, cy)."""
    size = max(8, int(size))
    m = mask(name, size)
    x0, y0 = int(round(cx - size / 2)), int(round(cy - size / 2))
    ix0, iy0 = max(0, x0), max(0, y0)
    ix1, iy1 = min(canvas.w, x0 + size), min(canvas.h, y0 + size)
    if ix1 <= ix0 or iy1 <= iy0:
        return
    a = m[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0].astype(np.float32) * (alpha / 255.0)
    reg = canvas.img[iy0:iy1, ix0:ix1]
    reg[:] = (reg + (np.asarray(color, np.float32) - reg) * a[..., None] + 0.5).astype(np.uint8)
