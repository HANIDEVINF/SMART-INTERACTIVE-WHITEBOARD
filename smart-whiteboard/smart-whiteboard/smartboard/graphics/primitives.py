"""Drawing primitives written with NumPy (no OpenCV drawing calls).

Every primitive works on a bounding box of the shape only, so cost is
proportional to the shape size, not to the screen size.
"""
from __future__ import annotations

from typing import Sequence, Tuple

import numpy as np

Color = Tuple[int, int, int]


def _clip_box(shape, x0, y0, x1, y1):
    h, w = shape[:2]
    return max(0, int(np.floor(x0))), max(0, int(np.floor(y0))), \
        min(w, int(np.ceil(x1)) + 1), min(h, int(np.ceil(y1)) + 1)


def segment_mask(shape, p0, p1, radius: float):
    """Pixels whose distance to the segment p0-p1 is <= radius (a thick line
    with round caps; p0 == p1 gives a disc).  Returns (ys, xs, mask)."""
    (x0, y0), (x1, y1) = p0, p1
    bx0, by0, bx1, by1 = _clip_box(shape, min(x0, x1) - radius, min(y0, y1) - radius,
                                   max(x0, x1) + radius, max(y0, y1) + radius)
    if bx1 <= bx0 or by1 <= by0:
        return slice(0, 0), slice(0, 0), np.zeros((0, 0), bool)
    yy, xx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        t = np.zeros_like(xx)
    else:
        t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / L2, 0.0, 1.0)   # projection on the segment
    d2 = (xx - (x0 + t * dx)) ** 2 + (yy - (y0 + t * dy)) ** 2
    return slice(by0, by1), slice(bx0, bx1), d2 <= radius * radius


def draw_segment(img: np.ndarray, p0, p1, color: Color, radius: float) -> None:
    sy, sx, m = segment_mask(img.shape, p0, p1, radius)
    if m.size:
        img[sy, sx][m] = color


def fill_circle(img, c, r, color):
    sy, sx, m = segment_mask(img.shape, c, c, r)
    if m.size:
        img[sy, sx][m] = color


def ring(img, c, r, thickness, color):
    cx, cy = c
    bx0, by0, bx1, by1 = _clip_box(img.shape, cx - r - thickness, cy - r - thickness,
                                   cx + r + thickness, cy + r + thickness)
    if bx1 <= bx0 or by1 <= by0:
        return
    yy, xx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    img[by0:by1, bx0:bx1][np.abs(d - r) <= thickness / 2.0] = color


def fill_rect(img, x0, y0, x1, y1, color, alpha: float = 1.0):
    x0, y0, x1, y1 = int(max(0, x0)), int(max(0, y0)), int(min(img.shape[1], x1)), int(min(img.shape[0], y1))
    if x1 <= x0 or y1 <= y0:
        return
    if alpha >= 1.0:
        img[y0:y1, x0:x1] = color
    else:
        reg = img[y0:y1, x0:x1].astype(np.float32)
        img[y0:y1, x0:x1] = (reg * (1 - alpha) + np.array(color, np.float32) * alpha).astype(np.uint8)


def rect_outline(img, x0, y0, x1, y1, color, t: int = 2):
    fill_rect(img, x0, y0, x1, y0 + t, color)
    fill_rect(img, x0, y1 - t, x1, y1, color)
    fill_rect(img, x0, y0, x0 + t, y1, color)
    fill_rect(img, x1 - t, y0, x1, y1, color)


def fill_rounded_rect(img, x0, y0, x1, y1, r, color, alpha: float = 1.0):
    """Rectangle with rounded corners (corner pixels tested against circles)."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    bx0, by0, bx1, by1 = _clip_box(img.shape, x0, y0, x1 - 1, y1 - 1)
    if bx1 <= bx0 or by1 <= by0:
        return
    yy, xx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    cx = np.clip(xx, x0 + r, x1 - 1 - r)
    cy = np.clip(yy, y0 + r, y1 - 1 - r)
    m = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    reg = img[by0:by1, bx0:bx1]
    if alpha >= 1.0:
        reg[m] = color
    else:
        reg[m] = (reg[m].astype(np.float32) * (1 - alpha) + np.array(color, np.float32) * alpha).astype(np.uint8)


def fill_polygon(img, pts: Sequence, color):
    """Even-odd (crossing number) polygon fill, vectorised over the bounding box."""
    pts = np.asarray(pts, np.float32)
    bx0, by0, bx1, by1 = _clip_box(img.shape, pts[:, 0].min(), pts[:, 1].min(),
                                   pts[:, 0].max(), pts[:, 1].max())
    if bx1 <= bx0 or by1 <= by0:
        return
    yy, xx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
    inside = np.zeros(xx.shape, bool)
    n = len(pts)
    for i in range(n):
        xa, ya = pts[i]
        xb, yb = pts[(i + 1) % n]
        if ya == yb:
            continue
        cond = ((ya > yy) != (yb > yy))
        xint = (xb - xa) * (yy - ya) / (yb - ya) + xa
        inside ^= cond & (xx < xint)
    img[by0:by1, bx0:bx1][inside] = color


def polyline(img, pts: Sequence, color, radius: float):
    for a, b in zip(pts[:-1], pts[1:]):
        draw_segment(img, a, b, color, radius)


def star_points(cx, cy, r_out, r_in, n=5, rot=-np.pi / 2):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * np.pi / n
        pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    return pts
