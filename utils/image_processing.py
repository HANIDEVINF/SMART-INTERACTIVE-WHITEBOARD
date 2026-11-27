"""Manual NumPy image-processing primitives.

This module implements the essential low-level operations of the computer
vision pipeline by hand (with NumPy) instead of delegating everything to
OpenCV.  Each function documents which step of the pipeline it implements.

Operations implemented here:
  * pixel access helpers
  * BGR -> grayscale conversion   (ITU-R BT.601 luma)
  * BGR -> HSV conversion         (standard RGB->HSV formulas, vectorised)
  * binary thresholding / HSV range masking (with hue wrap-around)
  * binary erosion / dilation     (square structuring element, shift-based)
  * connected-component statistics (area, centroid, bounding box) computed
    manually from label maps with np.bincount / np.nonzero
  * thick-line rasterisation on a NumPy RGBA layer (DDA + circular brush)

OpenCV is intentionally NOT used here; it is only used for video capture,
image file IO and the efficient connected-component *labelling* step
(see detection/components.py for the justification).
"""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Pixel access
# ---------------------------------------------------------------------------

def get_pixel(image: np.ndarray, x: int, y: int) -> np.ndarray:
    """Return the BGR(A) pixel at integer coordinates (x, y).

    ``image`` is a NumPy array with shape (H, W, C).  Pixel (x, y) means
    column x, row y -- the same convention used by OpenCV and Pygame.
    """
    h, w = image.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        raise IndexError(f"pixel ({x}, {y}) outside image of size {w}x{h}")
    return image[y, x]


def set_pixel(image: np.ndarray, x: int, y: int, value) -> None:
    """Write a BGR(A) pixel value at (x, y).  Modifies ``image`` in place."""
    h, w = image.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        raise IndexError(f"pixel ({x}, {y}) outside image of size {w}x{h}")
    image[y, x] = value


# ---------------------------------------------------------------------------
# Colour conversions
# ---------------------------------------------------------------------------

def bgr_to_gray(bgr: np.ndarray) -> np.ndarray:
    """Convert a BGR image to single-channel grayscale (uint8).

    Uses the ITU-R BT.601 luma coefficients:
        Y = 0.299 R + 0.587 G + 0.114 B
    Channels are extracted manually and combined with a weighted sum.
    """
    b = bgr[..., 0].astype(np.float32)
    g = bgr[..., 1].astype(np.float32)
    r = bgr[..., 2].astype(np.float32)
    y = 0.114 * b + 0.587 * g + 0.299 * r
    return np.clip(y, 0, 255).astype(np.uint8)


def bgr_to_hsv(bgr: np.ndarray) -> np.ndarray:
    """Convert a BGR image to HSV, fully vectorised with NumPy.

    Input : uint8 array (H, W, 3), channel order B, G, R.
    Output: float32 array (H, W, 3) with
            H in degrees [0, 360), S in [0, 1], V in [0, 1].

    The conversion follows the standard RGB->HSV algorithm:
      V = max(R,G,B);  C = V - min(R,G,B)
      S = C / V        (0 when V == 0)
      H depends on which channel attains the maximum.
    Working in float avoids the integer-division pitfalls of the classic
    8-bit formulation and makes the hue thresholds easy to reason about.
    """
    bgr_f = bgr.astype(np.float32) * np.float32(1.0 / 255.0)
    b, g, r = bgr_f[..., 0], bgr_f[..., 1], bgr_f[..., 2]

    v = np.maximum(np.maximum(r, g), b)
    c = v - np.minimum(np.minimum(r, g), b)
    chromatic = c > 1e-6                       # achromatic pixels keep H = 0

    # Saturation: 0 where the pixel is pure black (V == 0).
    s = c / np.maximum(v, 1e-6)

    # Hue, expressed in "sixths of the colour wheel" and scaled by 60 at the
    # end.  ONE division serves all three cases (the first version divided
    # three times over the whole image):
    #   R is max : (g - b) / c  (mod 6)
    #   G is max : (b - r) / c + 2
    #   B is max : (r - g) / c + 4
    # Where several channels tie for the maximum the order B > G > R is
    # kept, exactly as in the first version.
    inv_c = 1.0 / np.maximum(c, 1e-6)
    h6 = np.where(v == b, (r - g) * inv_c + 4.0,
                  np.where(v == g, (b - r) * inv_c + 2.0,
                           np.mod((g - b) * inv_c, 6.0)))
    h = np.where(chromatic, h6 * 60.0, 0.0)

    return np.stack([h, s, v], axis=-1).astype(np.float32)


# ---------------------------------------------------------------------------
# Thresholding / segmentation
# ---------------------------------------------------------------------------

def in_hsv_range(hsv: np.ndarray,
                 h_min: float, h_max: float,
                 s_min: float, s_max: float,
                 v_min: float, v_max: float) -> np.ndarray:
    """Boolean mask of pixels whose HSV values lie inside the given box.

    Hue is circular on [0, 360).  When ``h_min > h_max`` the range wraps
    around 0 degrees (e.g. red hues 350..10), which is handled by OR-ing
    the two non-wrapping intervals.
    """
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if h_min <= h_max:
        h_ok = (h >= h_min) & (h <= h_max)
    else:  # wrap-around range, e.g. [350, 10]
        h_ok = (h >= h_min) | (h <= h_max)
    return h_ok & (s >= s_min) & (s <= s_max) & (v >= v_min) & (v <= v_max)


def threshold_gray(gray: np.ndarray, thresh: int) -> np.ndarray:
    """Binary threshold: pixels >= thresh become True (foreground)."""
    return gray >= thresh


# ---------------------------------------------------------------------------
# Morphology (binary erosion / dilation with a square structuring element)
# ---------------------------------------------------------------------------

def _shift(mask: np.ndarray, dy: int, dx: int, fill: int) -> np.ndarray:
    """Shift a boolean array by (dy, dx); exposed borders get ``fill``."""
    out = np.full_like(mask, fill, dtype=bool)
    h, w = mask.shape
    y0, y1 = max(0, dy), min(h, h + dy)
    x0, x1 = max(0, dx), min(w, w + dx)
    sy0, sy1 = max(0, -dy), min(h, h - dy)
    sx0, sx1 = max(0, -dx), min(w, w - dx)
    out[y0:y1, x0:x1] = mask[sy0:sy1, sx0:sx1]
    return out


def binary_dilation(mask: np.ndarray, kernel_size: int = 3,
                    iterations: int = 1) -> np.ndarray:
    """Binary dilation with a square structuring element.

    Dilation grows foreground regions: a pixel becomes True if ANY pixel
    inside the structuring element centred on it is True.  Implemented as
    an OR over all shifted copies of the mask -- the discrete equivalent
    of a max-filter, which is exactly what dilation is.
    """
    r = kernel_size // 2
    out = mask.copy()
    for _ in range(iterations):
        acc = np.zeros_like(out)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                acc |= _shift(out, dy, dx, fill=False)
        out = acc
    return out


def binary_erosion(mask: np.ndarray, kernel_size: int = 3,
                   iterations: int = 1) -> np.ndarray:
    """Binary erosion with a square structuring element.

    Erosion shrinks foreground regions: a pixel stays True only if ALL
    pixels inside the structuring element are True -- the discrete
    equivalent of a min-filter.  Borders are treated as background, which
    is the standard convention.
    """
    r = kernel_size // 2
    out = mask.copy()
    for _ in range(iterations):
        acc = np.ones_like(out)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                acc &= _shift(out, dy, dx, fill=False)
        out = acc
    return out


def morphological_open(mask: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """Opening = erosion followed by dilation.  Removes small isolated
    noise blobs while preserving the size of large regions."""
    return binary_dilation(binary_erosion(mask, kernel_size), kernel_size)


def morphological_close(mask: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """Closing = dilation followed by erosion.  Fills small holes and gaps
    inside foreground regions."""
    return binary_erosion(binary_dilation(mask, kernel_size), kernel_size)


# ---------------------------------------------------------------------------
# Connected-component statistics (manual, from a label map)
# ---------------------------------------------------------------------------

def component_stats(labels: np.ndarray, n_labels: int) -> dict:
    """Compute area, centroid and bounding box for every label manually.

    ``labels`` is an integer array produced by a connected-component
    labelling algorithm (background = 0).  Instead of scanning the image
    once per component we use ``np.bincount`` over the flattened label
    map, weighted by precomputed x/y coordinate grids.  This yields, for
    every component i in a single vectorised pass:

        area_i      = number of pixels with label i
        sum_x_i     = sum of x coordinates of those pixels
        sum_y_i     = sum of y coordinates
        centroid    = (sum_x / area, sum_y / area)

    Bounding boxes are then obtained with ``np.nonzero`` per surviving
    component (only a handful survive the area filter, so this is cheap).

    Returns a dict mapping label -> {"area", "centroid", "bbox"}.
    """
    h, w = labels.shape
    flat = labels.ravel()

    # Coordinate grids, flattened once.
    xs = np.tile(np.arange(w, dtype=np.float64), h)
    ys = np.repeat(np.arange(h, dtype=np.float64), w)

    counts = np.bincount(flat, minlength=n_labels).astype(np.float64)
    sum_x = np.bincount(flat, weights=xs, minlength=n_labels)
    sum_y = np.bincount(flat, weights=ys, minlength=n_labels)

    stats = {}
    for i in range(1, n_labels):  # label 0 is background
        area = counts[i]
        if area <= 0:
            continue
        cx = sum_x[i] / area
        cy = sum_y[i] / area

        # Bounding box: min/max row/col of this label.
        ys_i, xs_i = np.nonzero(labels == i)
        bbox = (int(xs_i.min()), int(ys_i.min()),
                int(xs_i.max()), int(ys_i.max()))

        stats[i] = {
            "area": int(area),
            "centroid": (float(cx), float(cy)),
            "bbox": bbox,
        }
    return stats


# ---------------------------------------------------------------------------
# Line rasterisation (manual, NumPy)
# ---------------------------------------------------------------------------

def rasterize_line(layer: np.ndarray, p0, p1, color, thickness: int) -> None:
    """Draw a thick straight line segment onto an RGBA layer in place.

    ``layer`` has shape (H, W, 4) with dtype uint8; ``color`` is an
    (R, G, B, A) tuple.  The algorithm is a digital differential analyser
    (DDA): we step along the longer axis in unit increments and stamp a
    filled circular brush at every step.  The brush is generated with a
    NumPy meshgrid distance test, so the whole rasterisation is manual.

    This is deliberately NOT pygame.draw.line: the requirement is that the
    core drawing primitive be implemented with NumPy so the student can
    explain and defend the rasterisation in the report.
    """
    h, w = layer.shape[:2]
    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])

    dx, dy = x1 - x0, y1 - y0
    length = float(np.hypot(dx, dy))
    if length < 1e-6:
        steps = 1
    else:
        # Step at sub-pixel intervals so consecutive stamps overlap and the
        # line has no gaps regardless of angle.
        steps = max(1, int(np.ceil(length / max(1.0, thickness * 0.5))))

    radius = max(1, thickness / 2.0)
    r = int(np.ceil(radius))
    # Circular brush mask, computed once per call.
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    brush = (xx * xx + yy * yy) <= (radius * radius)

    cr, cg, cb, ca = color
    for i in range(steps + 1):
        t = i / steps
        cx = int(round(x0 + dx * t))
        cy = int(round(y0 + dy * t))
        # Stamp the brush, clipped to the layer bounds.
        y_lo, y_hi = max(0, cy - r), min(h, cy + r + 1)
        x_lo, x_hi = max(0, cx - r), min(w, cx + r + 1)
        if y_lo >= y_hi or x_lo >= x_hi:
            continue
        by_lo, by_hi = y_lo - (cy - r), y_hi - (cy - r)
        bx_lo, bx_hi = x_lo - (cx - r), x_hi - (cx - r)
        sub = brush[by_lo:by_hi, bx_lo:bx_hi]
        region = layer[y_lo:y_hi, x_lo:x_hi]
        # Alpha-composite the stamp: new = src*alpha + dst*(1-alpha).
        a = (ca / 255.0) * sub[..., None]
        region[..., :3] = (region[..., :3].astype(np.float32) * (1 - a)
                           + np.array([cr, cg, cb], dtype=np.float32) * a
                           ).astype(np.uint8)
        region[..., 3] = np.maximum(region[..., 3],
                                    (sub * ca).astype(np.uint8))
