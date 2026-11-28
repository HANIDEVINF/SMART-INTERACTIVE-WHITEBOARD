"""Drawing primitives written with NumPy (no OpenCV drawing calls).

Two families:
  * hard-edged ones (segment_mask, fill_rect ...)  -> fast, used by the ink layer;
  * anti-aliased ones (aa_*)                       -> signed-distance fields (SDF).

SDF idea: for every pixel centre we compute the signed distance ``sd`` to the
shape outline (negative inside).  The pixel coverage is  clip(0.5 - sd, 0, 1),
which gives a one-pixel soft edge = anti-aliasing, for ANY shape, with no
super-sampling.  Every primitive only touches the bounding box of its shape,
so the cost depends on the shape size, not on the screen size.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

import numpy as np

Color = Tuple[int, int, int]


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def _clip_box(shape, x0, y0, x1, y1):
    h, w = shape[:2]
    return max(0, int(np.floor(x0))), max(0, int(np.floor(y0))), \
        min(w, int(np.ceil(x1)) + 1), min(h, int(np.ceil(y1)) + 1)


def _grid(bx0, by0, bx1, by1):
    """Pixel-centre coordinates (x + 0.5, y + 0.5) of a box."""
    yy, xx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
    return xx + 0.5, yy + 0.5


def _blend(img, bx0, by0, bx1, by1, cov, color, alpha=1.0):
    """img[box] = img + (color - img) * cov * alpha   (cov in 0..1, float32)."""
    a = (cov * alpha)[..., None]
    reg = img[by0:by1, bx0:bx1]
    col = np.asarray(color, np.float32)
    reg[:] = (reg + (col - reg) * a + 0.5).astype(np.uint8)


def vertical_gradient(h: int, w: int, top: Color, bottom: Color) -> np.ndarray:
    t = np.linspace(0.0, 1.0, max(h, 1), dtype=np.float32)[:, None, None]
    g = np.asarray(top, np.float32) * (1 - t) + np.asarray(bottom, np.float32) * t
    return np.repeat(np.clip(g + 0.5, 0, 255).astype(np.uint8), w, axis=1)


# ---------------------------------------------------------------------------------------------
# hard-edged primitives (ink layer, shapes of the drag & drop exercise)
# ---------------------------------------------------------------------------------------------
def segment_mask(shape, p0, p1, radius: float):
    """Pixels whose distance to the segment p0-p1 is <= radius (a thick line
    with round caps; p0 == p1 gives a disc).  Returns (ys, xs, mask)."""
    (x0, y0), (x1, y1) = p0, p1
    bx0, by0, bx1, by1 = _clip_box(shape, min(x0, x1) - radius, min(y0, y1) - radius,
                                   max(x0, x1) + radius, max(y0, y1) + radius)
    if bx1 <= bx0 or by1 <= by0:
        return slice(0, 0), slice(0, 0), np.zeros((0, 0), bool)
    xx, yy = _grid(bx0, by0, bx1, by1)
    d = _dist_to_segment(xx, yy, x0, y0, x1, y1)
    return slice(by0, by1), slice(bx0, bx1), d <= radius


def _dist_to_segment(xx, yy, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return np.hypot(xx - x0, yy - y0)
    t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / L2, 0.0, 1.0)   # projection on the segment
    return np.hypot(xx - (x0 + t * dx), yy - (y0 + t * dy))


def fill_rect(img, x0, y0, x1, y1, color, alpha: float = 1.0):
    x0, y0, x1, y1 = int(max(0, x0)), int(max(0, y0)), int(min(img.shape[1], x1)), int(min(img.shape[0], y1))
    if x1 <= x0 or y1 <= y0:
        return
    if alpha >= 1.0:
        img[y0:y1, x0:x1] = color
    else:
        reg = img[y0:y1, x0:x1].astype(np.float32)
        img[y0:y1, x0:x1] = (reg * (1 - alpha) + np.array(color, np.float32) * alpha + 0.5).astype(np.uint8)


def rect_outline(img, x0, y0, x1, y1, color, t: int = 2):
    fill_rect(img, x0, y0, x1, y0 + t, color)
    fill_rect(img, x0, y1 - t, x1, y1, color)
    fill_rect(img, x0, y0, x0 + t, y1, color)
    fill_rect(img, x1 - t, y0, x1, y1, color)


def fill_polygon(img, pts: Sequence, color):
    """Even-odd (crossing number) polygon fill, vectorised over the bounding box."""
    pts = np.asarray(pts, np.float32)
    bx0, by0, bx1, by1 = _clip_box(img.shape, pts[:, 0].min(), pts[:, 1].min(),
                                   pts[:, 0].max(), pts[:, 1].max())
    if bx1 <= bx0 or by1 <= by0:
        return
    xx, yy = _grid(bx0, by0, bx1, by1)
    img[by0:by1, bx0:bx1][_inside(pts, xx, yy)] = color


def _inside(pts, xx, yy):
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
    return inside


def fill_circle(img, c, r, color):
    sy, sx, m = segment_mask(img.shape, c, c, r)
    if m.size:
        img[sy, sx][m] = color


def star_points(cx, cy, r_out, r_in, n=5, rot=-np.pi / 2):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * np.pi / n
        pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    return pts


# ---------------------------------------------------------------------------------------------
# anti-aliased primitives (signed distance fields)
# ---------------------------------------------------------------------------------------------
def _rrect_sd(xx, yy, x0, y0, x1, y1, r):
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    hx, hy = (x1 - x0) / 2.0 - r, (y1 - y0) / 2.0 - r
    qx, qy = np.abs(xx - cx) - hx, np.abs(yy - cy) - hy
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def aa_rrect(img, x0, y0, x1, y1, r, color, alpha=1.0, color2=None, outline=0.0):
    """Rounded rectangle.  ``color2`` -> vertical gradient colour -> color2;
    ``outline`` > 0 -> only a border of that thickness."""
    r = max(0.0, min(r, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    bx0, by0, bx1, by1 = _clip_box(img.shape, x0 - 1, y0 - 1, x1 + 1, y1 + 1)
    if bx1 <= bx0 or by1 <= by0:
        return
    xx, yy = _grid(bx0, by0, bx1, by1)
    sd = _rrect_sd(xx, yy, x0, y0, x1, y1, r)
    if outline > 0:
        cov = np.clip(outline / 2.0 + 0.5 - np.abs(sd + outline / 2.0), 0, 1)
    else:
        cov = np.clip(0.5 - sd, 0, 1)
    if color2 is not None:
        t = np.clip((yy - y0) / max(y1 - y0, 1), 0, 1)[..., None]
        color = np.asarray(color, np.float32) * (1 - t) + np.asarray(color2, np.float32) * t
        a = (cov * alpha)[..., None]
        reg = img[by0:by1, bx0:bx1]
        reg[:] = (reg + (color - reg) * a + 0.5).astype(np.uint8)
    else:
        _blend(img, bx0, by0, bx1, by1, cov, color, alpha)


def aa_circle(img, cx, cy, r, color, alpha=1.0):
    bx0, by0, bx1, by1 = _clip_box(img.shape, cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1)
    if bx1 <= bx0 or by1 <= by0:
        return
    xx, yy = _grid(bx0, by0, bx1, by1)
    cov = np.clip(r + 0.5 - np.hypot(xx - cx, yy - cy), 0, 1)
    _blend(img, bx0, by0, bx1, by1, cov, color, alpha)


def aa_ring(img, cx, cy, r, t, color, alpha=1.0):
    bx0, by0, bx1, by1 = _clip_box(img.shape, cx - r - t, cy - r - t, cx + r + t, cy + r + t)
    if bx1 <= bx0 or by1 <= by0:
        return
    xx, yy = _grid(bx0, by0, bx1, by1)
    cov = np.clip(t / 2.0 + 0.5 - np.abs(np.hypot(xx - cx, yy - cy) - r), 0, 1)
    _blend(img, bx0, by0, bx1, by1, cov, color, alpha)


def aa_segment(img, p0, p1, radius, color, alpha=1.0):
    """Thick anti-aliased line with round caps (radius = half the width)."""
    (x0, y0), (x1, y1) = p0, p1
    bx0, by0, bx1, by1 = _clip_box(img.shape, min(x0, x1) - radius - 1, min(y0, y1) - radius - 1,
                                   max(x0, x1) + radius + 1, max(y0, y1) + radius + 1)
    if bx1 <= bx0 or by1 <= by0:
        return
    xx, yy = _grid(bx0, by0, bx1, by1)
    cov = np.clip(radius + 0.5 - _dist_to_segment(xx, yy, x0, y0, x1, y1), 0, 1)
    _blend(img, bx0, by0, bx1, by1, cov, color, alpha)


def aa_polygon(img, pts: Sequence, color, alpha=1.0):
    """Anti-aliased polygon: sd = +/- distance to the nearest edge (sign by even-odd rule)."""
    pts = np.asarray(pts, np.float32)
    bx0, by0, bx1, by1 = _clip_box(img.shape, pts[:, 0].min() - 1, pts[:, 1].min() - 1,
                                   pts[:, 0].max() + 1, pts[:, 1].max() + 1)
    if bx1 <= bx0 or by1 <= by0:
        return
    xx, yy = _grid(bx0, by0, bx1, by1)
    d = np.full(xx.shape, 1e9, np.float32)
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        d = np.minimum(d, _dist_to_segment(xx, yy, a[0], a[1], b[0], b[1]))
    sd = np.where(_inside(pts, xx, yy), -d, d)
    _blend(img, bx0, by0, bx1, by1, np.clip(0.5 - sd, 0, 1), color, alpha)


def aa_ellipse_outline(img, cx, cy, rx, ry, t, color, alpha=1.0):
    """Ellipse border (approximate SDF: normalised radius scaled by the smaller semi-axis)."""
    m = max(rx, ry) + t + 2
    bx0, by0, bx1, by1 = _clip_box(img.shape, cx - m, cy - m, cx + m, cy + m)
    if bx1 <= bx0 or by1 <= by0:
        return
    xx, yy = _grid(bx0, by0, bx1, by1)
    rx, ry = max(rx, 1.0), max(ry, 1.0)
    k = (np.hypot((xx - cx) / rx, (yy - cy) / ry) - 1.0) * min(rx, ry)
    cov = np.clip(t / 2.0 + 0.5 - np.abs(k), 0, 1)
    _blend(img, bx0, by0, bx1, by1, cov, color, alpha)


def glow(img, cx, cy, r, color, strength=1.0):
    """Soft additive light spot (used under the cursor and on hovered widgets)."""
    bx0, by0, bx1, by1 = _clip_box(img.shape, cx - r, cy - r, cx + r, cy + r)
    if bx1 <= bx0 or by1 <= by0:
        return
    xx, yy = _grid(bx0, by0, bx1, by1)
    q = np.clip(1.0 - np.hypot(xx - cx, yy - cy) / r, 0, 1)
    k = (q * q * strength)[..., None]
    reg = img[by0:by1, bx0:bx1]
    reg[:] = np.minimum(reg + np.asarray(color, np.float32) * k, 255).astype(np.uint8)


def shadow_rrect(img, x0, y0, x1, y1, r, blur=14.0, dy=8.0, opacity=0.55):
    """Soft drop shadow below a rounded rectangle (smoothstep of the SDF)."""
    m = blur * 2 + abs(dy) + 2
    bx0, by0, bx1, by1 = _clip_box(img.shape, x0 - m, y0 - m + dy, x1 + m, y1 + m + dy)
    if bx1 <= bx0 or by1 <= by0:
        return
    xx, yy = _grid(bx0, by0, bx1, by1)
    sd = _rrect_sd(xx, yy, x0, y0 + dy, x1, y1 + dy, r)
    t = np.clip(0.5 - sd / (2.0 * blur), 0, 1)
    _blend(img, bx0, by0, bx1, by1, t * t * (3 - 2 * t), (0, 0, 0), opacity)
