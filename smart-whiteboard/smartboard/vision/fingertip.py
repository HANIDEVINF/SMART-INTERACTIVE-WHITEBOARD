"""Fingertip of a hand blob (hand mode): the pointer is where the finger points.

The arm enters the picture from an edge of the board (the camera frame or the ROI border), so
the "base" of the hand is the part of the blob that touches that border, and the fingertip is the
blob pixel FARTHEST from the base.  The tip is then the mean of the pixels within ``radius`` of that
extreme point: a mean is far more stable than the single farthest pixel (which flickers).

    base  = mean of blob pixels near the border (or the blob centroid when the hand is inside)
    far   = argmax |p - base|
    tip   = mean{ p : |p - far| <= radius }
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from . import imgproc


def border_mask(shape: Tuple[int, int], roi: Optional[np.ndarray], width: int = 3) -> np.ndarray:
    """True within ``width`` pixels of the picture border or of the outside of the ROI."""
    h, w = shape
    out = np.zeros(shape, bool)
    out[:width, :] = out[-width:, :] = True
    out[:, :width] = out[:, -width:] = True
    if roi is not None:
        out |= imgproc.dilate(~roi, width)
    return out


def find_fingertip(xs: np.ndarray, ys: np.ndarray, near_border: np.ndarray, radius: float = 4.0,
                   prior: Optional[Tuple[float, float]] = None):
    """xs, ys: pixels of the blob; near_border: bool per pixel (touches the border).
    Returns ((tip x, tip y), (base x, base y)) in the same pixel units."""
    if near_border.any():
        bx, by = xs[near_border].mean(), ys[near_border].mean()
    else:
        bx, by = xs.mean(), ys.mean()
    d2 = (xs - bx) ** 2 + (ys - by) ** 2
    i = int(np.argmax(d2))
    fx, fy = xs[i], ys[i]
    close = (xs - fx) ** 2 + (ys - fy) ** 2 <= radius * radius
    return (float(xs[close].mean()), float(ys[close].mean())), (float(bx), float(by))


def refine_tip(skin_crop: np.ndarray, tip_xy, base_xy, off, reach: float = 1.5,
               ring: Tuple[float, float] = (14.0, 48.0)):
    """Sharpen the tip on the FULL-resolution skin mask of a window (top-left corner ``off``).

    1. finger axis: centroid C of the skin pixels in a ring behind the coarse tip (between
       ring[0] and ring[1] pixels away) = the middle of the finger body; the axis points from
       C to the tip.  A centroid of many pixels is far steadier than the single farthest pixel.
    2. apex = the extreme skin pixels along that axis; tip = mean of those within ``reach``."""
    ys, xs = np.nonzero(skin_crop)
    if len(xs) < 8:
        return tip_xy
    px, py = xs + off[0] + 0.5, ys + off[1] + 0.5
    dist = np.hypot(px - tip_xy[0], py - tip_xy[1])
    body = (dist >= ring[0]) & (dist <= ring[1])
    if body.sum() < 10:
        return tip_xy
    d = np.array([tip_xy[0] - px[body].mean(), tip_xy[1] - py[body].mean()])
    n = np.hypot(*d)
    if n < 1e-6:
        return tip_xy
    d /= n
    proj = (px - tip_xy[0]) * d[0] + (py - tip_xy[1]) * d[1]
    ok = dist <= 2 * ring[0]                      # only the neighbourhood of the tip
    cap = ok & (proj >= proj[ok].max() - reach)
    return float(px[cap].mean()), float(py[cap].mean())
