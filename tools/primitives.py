"""Anti-aliased drawing primitives implemented with NumPy only.

Instead of calling cv2.line / cv2.circle, every primitive is expressed as a *coverage map*:
for each pixel inside a small bounding box we compute how much of the pixel is covered by
the shape (0.0 = untouched, 1.0 = fully covered). The pen colour is then blended using that
coverage ("alpha compositing").

Mathematics
-----------
Thick line segment P0->P1 with width w (a "capsule": rectangle with round caps).
For a pixel centre X, project it on the segment:

        t = clamp( ((X - P0) . (P1 - P0)) / |P1 - P0|^2 , 0, 1 )
        C = P0 + t (P1 - P0)              # closest point on the segment
        d = |X - C|                       # distance from pixel to the segment

The pixel is fully inside when d <= w/2 - 0.5 and fully outside when d >= w/2 + 0.5; in between
we use a linear ramp, which gives smooth edges:

        coverage = clamp( w/2 + 0.5 - d , 0, 1 )

Circle outline of radius R and stroke width w: the distance to the ideal circle is | |X - C| - R |,
and the same ramp is applied:  coverage = clamp( w/2 + 0.5 - | |X - C| - R | , 0, 1 ).

Alpha compositing ("source over") of colour Cs with alpha As onto a destination (Cd, Ad):

        Ao = As + Ad (1 - As)
        Co = ( Cs As + Cd Ad (1 - As) ) / Ao
"""
from __future__ import annotations

import math

import numpy as np

BBox = tuple[int, int, int, int]  # (x0, y0, x1, y1), x1/y1 exclusive


def union_bbox(a: BBox | None, b: BBox | None) -> BBox | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def _clip_box(x0: float, y0: float, x1: float, y1: float, w: int, h: int) -> BBox | None:
    bx0, by0 = max(int(math.floor(x0)), 0), max(int(math.floor(y0)), 0)
    bx1, by1 = min(int(math.ceil(x1)) + 1, w), min(int(math.ceil(y1)) + 1, h)
    if bx0 >= bx1 or by0 >= by1:
        return None
    return bx0, by0, bx1, by1


def segment_coverage(shape: tuple[int, ...], p0, p1, width: float):
    """Coverage map of a thick segment. Returns (bbox, coverage float32) or None if off-canvas."""
    h, w = shape[:2]
    width = max(float(width), 1.0)
    r = width / 2.0
    (x0, y0), (x1, y1) = p0, p1
    pad = r + 1.5
    box = _clip_box(min(x0, x1) - pad, min(y0, y1) - pad,
                    max(x0, x1) + pad, max(y0, y1) + pad, w, h)
    if box is None:
        return None
    bx0, by0, bx1, by1 = box
    xs = np.arange(bx0, bx1, dtype=np.float32)[None, :]
    ys = np.arange(by0, by1, dtype=np.float32)[:, None]
    dx, dy = x1 - x0, y1 - y0
    length2 = dx * dx + dy * dy
    if length2 < 1e-9:
        t = 0.0
    else:
        t = np.clip(((xs - x0) * dx + (ys - y0) * dy) / length2, 0.0, 1.0)
    cx = x0 + t * dx
    cy = y0 + t * dy
    dist = np.hypot(xs - cx, ys - cy)
    cov = np.clip(r + 0.5 - dist, 0.0, 1.0).astype(np.float32)
    return box, cov


def ring_coverage(shape: tuple[int, ...], center, radius: float, width: float):
    """Coverage map of a circle outline (stroke width `width`)."""
    h, w = shape[:2]
    width = max(float(width), 1.0)
    cx, cy = center
    reach = radius + width / 2.0 + 1.5
    box = _clip_box(cx - reach, cy - reach, cx + reach, cy + reach, w, h)
    if box is None:
        return None
    bx0, by0, bx1, by1 = box
    xs = np.arange(bx0, bx1, dtype=np.float32)[None, :]
    ys = np.arange(by0, by1, dtype=np.float32)[:, None]
    dist = np.hypot(xs - cx, ys - cy)
    cov = np.clip(width / 2.0 + 0.5 - np.abs(dist - radius), 0.0, 1.0).astype(np.float32)
    return box, cov


def over(dst_bgra: np.ndarray, color_bgr, cov: np.ndarray) -> np.ndarray:
    """Composite a solid colour with per-pixel coverage `cov` over a BGRA (straight alpha) patch."""
    d = dst_bgra.astype(np.float32)
    a_d = d[..., 3] / 255.0
    a_s = cov
    a_o = a_s + a_d * (1.0 - a_s)
    w_s = np.where(a_o > 1e-6, a_s / np.maximum(a_o, 1e-6), 0.0)[..., None]
    col = np.asarray(color_bgr, dtype=np.float32)
    out = np.empty_like(dst_bgra)
    out[..., :3] = np.rint(d[..., :3] * (1.0 - w_s) + col * w_s).astype(np.uint8)
    out[..., 3] = np.rint(a_o * 255.0).astype(np.uint8)
    return out
