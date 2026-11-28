"""Basic image-processing operations implemented with NumPy only.

The project asks us to re-implement the essential steps ourselves:
colour conversion, thresholding, noise reduction, connected components,
centroid and bounding box, and resampling.  Everything in this file is
vectorised NumPy (no OpenCV).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


# --------------------------------------------------------------------------
# Colour conversion
# --------------------------------------------------------------------------
def bgr_to_hsv(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert a uint8 BGR image to (H in degrees 0..360, S 0..1, V 0..1).

    V = max(R,G,B);  S = (max-min)/max;  H depends on which channel is max:
        R max : 60 * ((G-B)/d mod 6)
        G max : 60 * ((B-R)/d + 2)
        B max : 60 * ((R-G)/d + 4)
    """
    f = img.astype(np.float32) * (1.0 / 255.0)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    d = mx - mn
    safe = np.maximum(d, 1e-6)

    h_r = 60.0 * (((g - b) / safe) % 6.0)
    h_g = 60.0 * ((b - r) / safe + 2.0)
    h_b = 60.0 * ((r - g) / safe + 4.0)
    h = np.where(mx == r, h_r, np.where(mx == g, h_g, h_b))
    h = np.where(d > 1e-6, h, 0.0)

    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    return h.astype(np.float32), s.astype(np.float32), mx.astype(np.float32)


# --------------------------------------------------------------------------
# Thresholding / segmentation
# --------------------------------------------------------------------------
def threshold_red(h: np.ndarray, s: np.ndarray, v: np.ndarray,
                  hue_tol: float, s_min: float, v_min: float) -> np.ndarray:
    """Boolean mask of "bright, saturated, red" pixels.

    Red sits on both sides of the 0/360 hue wrap-around, so we use the
    circular distance to hue 0:  min(h, 360-h) <= tolerance.
    """
    hue_dist = np.minimum(h, 360.0 - h)
    return (hue_dist <= hue_tol) & (s >= s_min) & (v >= v_min)


# --------------------------------------------------------------------------
# Binary morphology / noise reduction
# --------------------------------------------------------------------------
def _neighbour_sum(mask: np.ndarray) -> np.ndarray:
    """Number of True pixels in the 3x3 neighbourhood (itself included)."""
    p = np.pad(mask.astype(np.uint8), 1)
    h, w = mask.shape
    acc = np.zeros((h, w), np.uint8)
    for dy in range(3):
        for dx in range(3):
            acc += p[dy:dy + h, dx:dx + w]
    return acc


def majority_filter(mask: np.ndarray, min_neighbors: int = 3) -> np.ndarray:
    """Remove isolated pixels: keep a pixel only if >= min_neighbors of its
    3x3 neighbourhood are set.  Cheap salt-noise reduction that keeps blobs
    of 2x2 pixels or more."""
    if min_neighbors <= 1:
        return mask
    return mask & (_neighbour_sum(mask) >= min_neighbors)


def dilate(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Binary dilation with a 3x3 square element (OR of shifted copies)."""
    out = mask
    for _ in range(iterations):
        p = np.pad(out, 1)
        h, w = out.shape
        acc = np.zeros_like(out)
        for dy in range(3):
            for dx in range(3):
                acc |= p[dy:dy + h, dx:dx + w]
        out = acc
    return out


def polygon_mask(shape: Tuple[int, int], pts: np.ndarray) -> np.ndarray:
    """Mask of a CONVEX polygon (our calibrated board quadrilateral).

    A pixel is inside when it lies on the same side of every edge
    (sign of the 2-D cross product is constant)."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    pos = np.ones((h, w), bool)
    neg = np.ones((h, w), bool)
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cross = (x1 - x0) * (yy - y0) - (y1 - y0) * (xx - x0)
        pos &= cross >= 0
        neg &= cross <= 0
    return pos | neg


# --------------------------------------------------------------------------
# Connected components + blob features
# --------------------------------------------------------------------------
@dataclass
class Blob:
    xs: np.ndarray
    ys: np.ndarray
    area: int
    cx: float
    cy: float
    bbox: Tuple[int, int, int, int]  # x0, y0, x1, y1 (inclusive)

    @property
    def fill_ratio(self) -> float:
        x0, y0, x1, y1 = self.bbox
        return self.area / float((x1 - x0 + 1) * (y1 - y0 + 1))

    @property
    def aspect(self) -> float:
        x0, y0, x1, y1 = self.bbox
        w, h = x1 - x0 + 1, y1 - y0 + 1
        return min(w, h) / float(max(w, h))


def connected_components(mask: np.ndarray, link: np.ndarray = None,
                         max_pixels: int = 6000) -> List[Blob]:
    """8-connected component labelling by flood fill on the *set pixels only*.

    ``mask`` holds the real pixels, ``link`` (optional, a dilated copy) is
    used to decide connectivity so that a dot broken into pieces by sensor
    noise remains one blob.  Because the dot is tiny the number of set
    pixels is small and a Python flood fill is fast; if the mask contains
    more than ``max_pixels`` pixels it is a big red area, not a pointer,
    and we return nothing.
    """
    if link is None:
        link = mask
    ys, xs = np.nonzero(link)
    if len(ys) == 0 or len(ys) > max_pixels:
        return []
    pixels = set(zip(xs.tolist(), ys.tolist()))
    seen = set()
    blobs: List[Blob] = []
    for start in pixels:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp = []
        while stack:
            x, y = stack.pop()
            comp.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in pixels and q not in seen:
                        seen.add(q)
                        stack.append(q)
        arr = np.array(comp)
        cx_, cy_ = arr[:, 0], arr[:, 1]
        keep = mask[cy_, cx_]               # only genuine (non-dilated) pixels
        if not keep.any():
            continue
        bx, by = cx_[keep], cy_[keep]
        blobs.append(Blob(bx, by, int(keep.sum()), float(bx.mean()), float(by.mean()),
                          (int(bx.min()), int(by.min()), int(bx.max()), int(by.max()))))
    return blobs


def weighted_centroid(blob: Blob, weights: np.ndarray) -> Tuple[float, float]:
    """Intensity-weighted centroid  sum(w*x)/sum(w) -> sub-pixel accuracy."""
    w = weights[blob.ys, blob.xs].astype(np.float64)
    tot = w.sum()
    if tot <= 0:
        return blob.cx, blob.cy
    return float((blob.xs * w).sum() / tot), float((blob.ys * w).sum() / tot)


# --------------------------------------------------------------------------
# Resampling
# --------------------------------------------------------------------------
def resize_bilinear(img: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    """Bilinear resize by inverse mapping (4-tap gather + linear blend)."""
    h, w = img.shape[:2]
    ys = (np.arange(out_h, dtype=np.float32) + 0.5) * (h / out_h) - 0.5
    xs = (np.arange(out_w, dtype=np.float32) + 0.5) * (w / out_w) - 0.5
    ys = np.clip(ys, 0, h - 1)
    xs = np.clip(xs, 0, w - 1)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    y1 = np.minimum(y0 + 1, h - 1)
    x1 = np.minimum(x0 + 1, w - 1)
    wy = (ys - y0)[:, None, None]
    wx = (xs - x0)[None, :, None]
    f = img.astype(np.float32)
    if f.ndim == 2:
        f = f[..., None]
    top = f[y0][:, x0] * (1 - wx) + f[y0][:, x1] * wx
    bot = f[y1][:, x0] * (1 - wx) + f[y1][:, x1] * wx
    out = top * (1 - wy) + bot * wy
    out = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    return out[..., 0] if img.ndim == 2 else out


def resize_nearest(img: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    """Nearest-neighbour resize (fast path used while panning)."""
    h, w = img.shape[:2]
    ys = np.minimum((np.arange(out_h) * h / out_h).astype(np.int32), h - 1)
    xs = np.minimum((np.arange(out_w) * w / out_w).astype(np.int32), w - 1)
    return img[ys][:, xs]
