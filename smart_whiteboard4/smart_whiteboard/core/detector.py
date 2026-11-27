"""HSV colour-marker pointer detector, implemented step by step with NumPy.

Pipeline (every stage is written here, OpenCV is only used to shrink the frame):

    1. resize          frame -> `detect_width` pixels wide (speed; coordinates are mapped back)
    2. BGR -> HSV      bgr_to_hsv()          explicit formulas, OpenCV's 8-bit convention
    3. threshold       threshold_hsv()       per-channel range test -> boolean mask
    4. noise removal   opening then closing  erode()/dilate() as separable min/max filters
    5. components      connected_components() run-length labelling + union-find
    6. moments         area, centroid and second moments computed analytically from the runs
    7. filter / select area window + shape confidence, best remaining blob wins
    8. centroid        (m10/m00, m01/m00), mapped back to camera-frame pixels

Mathematics
-----------
BGR -> HSV.  With V = max(R,G,B), m = min(R,G,B), delta = V - m:

        S = 255 * delta / V                      (0 when V = 0)
        h = 60 * (G-B)/delta          if V = R
            120 + 60 * (B-R)/delta    if V = G
            240 + 60 * (R-G)/delta    if V = B   (h in degrees, +360 if negative)
        H = h / 2                                 (OpenCV stores 8-bit hue as 0..179)

Hue is an angle, so a red marker straddles 0/179. When hsv_low.H > hsv_high.H the hue test
becomes  (H >= low) OR (H <= high)  -- the "wrapped" range.

Erosion / dilation with a k x k square are *separable*: a k x k minimum equals a 1 x k minimum
along rows followed by a k x 1 minimum along columns, so the cost is 2k instead of k^2 per
pixel. Opening (erode, dilate) deletes specks smaller than the kernel; closing (dilate, erode)
fills small holes inside the marker.

Image moments of a binary blob B:  m00 = |B| (area),  m10 = sum x,  m01 = sum y, centroid
(m10/m00, m01/m00). Second order central moments mu20, mu02, mu11 describe the blob's spread.
Because the mask is stored as horizontal *runs* (row y, columns s..e-1), every sum is a closed
form per run:  sum_{x=s}^{e-1} x = (s+e-1)(e-s)/2   and   sum x^2 = S(e-1) - S(s-1),
S(n) = n(n+1)(2n+1)/6.  No per-pixel Python loop is needed.

Advantages / limitations of the colour-marker approach are documented in README.md.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace

import cv2
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

HSV = tuple[int, int, int]
MAX_RUNS = 20000   # a mask with more runs than this is noise, not a marker


# =============================================================================
# Parameters
# =============================================================================
@dataclass(frozen=True)
class DetectionParams:
    hsv_low: HSV = (35, 90, 70)
    hsv_high: HSV = (85, 255, 255)
    min_area: int = 150          # px at camera resolution
    max_area: int = 40000
    kernel_size: int = 5
    confidence_min: float = 0.35
    detect_width: int = 320
    method: str = "color_marker"   # "color_marker" | "hand" (MediaPipe)

    def sanitized(self) -> "DetectionParams":
        """Clamp every field into a safe range (user input / hand-edited JSON)."""
        low = (_clamp_int(self.hsv_low[0], 0, 179), _clamp_int(self.hsv_low[1], 0, 255),
               _clamp_int(self.hsv_low[2], 0, 255))
        high = (_clamp_int(self.hsv_high[0], 0, 179), _clamp_int(self.hsv_high[1], 0, 255),
                _clamp_int(self.hsv_high[2], 0, 255))
        min_area = _clamp_int(self.min_area, 1, 10_000_000)
        return DetectionParams(
            hsv_low=low, hsv_high=high, min_area=min_area,
            max_area=max(min_area, _clamp_int(self.max_area, 1, 100_000_000)),
            kernel_size=_clamp_int(self.kernel_size, 1, 31) | 1,
            confidence_min=min(max(float(self.confidence_min), 0.0), 1.0),
            detect_width=_clamp_int(self.detect_width, 80, 1920),
            method=self.method if self.method in ("color_marker", "hand") else "color_marker")

    @classmethod
    def from_settings(cls, settings) -> "DetectionParams":
        d = cls()
        try:
            g = settings.get
            return cls(
                hsv_low=tuple(int(v) for v in g("detection.hsv_low", d.hsv_low))[:3],
                hsv_high=tuple(int(v) for v in g("detection.hsv_high", d.hsv_high))[:3],
                min_area=int(g("detection.min_area", d.min_area)),
                max_area=int(g("detection.max_area", d.max_area)),
                kernel_size=int(g("detection.kernel_size", d.kernel_size)),
                confidence_min=float(g("detection.confidence_min", d.confidence_min)),
                detect_width=int(g("detection.detect_width", d.detect_width)),
                method=str(g("detection.method", d.method)),
            ).sanitized()
        except (TypeError, ValueError):
            return d

    def write_to(self, settings) -> None:
        settings.set("detection.hsv_low", list(self.hsv_low))
        settings.set("detection.hsv_high", list(self.hsv_high))
        settings.set("detection.min_area", self.min_area)
        settings.set("detection.max_area", self.max_area)
        settings.set("detection.kernel_size", self.kernel_size)
        settings.set("detection.confidence_min", round(self.confidence_min, 3))
        settings.set("detection.detect_width", self.detect_width)
        settings.set("detection.method", self.method)

    def with_(self, **changes) -> "DetectionParams":
        return replace(self, **changes).sanitized()


def _clamp_int(value, lo: int, hi: int) -> int:
    return int(min(max(int(round(float(value))), lo), hi))


# =============================================================================
# Result types
# =============================================================================
@dataclass(frozen=True)
class Detection:
    x: float                      # centroid, camera-frame pixels
    y: float
    area: float                   # px at camera resolution
    confidence: float             # 0..1 shape validity
    bbox: tuple[float, float, float, float]   # x0, y0, x1, y1 in camera pixels


@dataclass
class DetectionResult:
    detection: Detection | None
    status: str                   # ok | no_pixels | area_too_small | area_too_large | low_confidence | noisy
    message: str
    mask: np.ndarray              # cleaned binary mask (uint8 0/255) at detection resolution
    candidates: int
    process_ms: float
    landmarks: list | None = None     # hand backend: 21 (x, y) camera-pixel points
    gesture_state: str = ""           # hand backend: "" | "next" | "previous" (pinch currently held)


@dataclass
class Component:
    area: int
    cx: float
    cy: float
    x0: int
    y0: int
    x1: int                       # exclusive
    y1: int
    mu20: float
    mu02: float
    mu11: float

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0


# =============================================================================
# Stage 2: colour conversion
# =============================================================================
def bgr_to_hsv(bgr: np.ndarray) -> np.ndarray:
    """BGR uint8 (H, W, 3) -> HSV uint8 with H in 0..179 (same convention as OpenCV)."""
    f = bgr.astype(np.float32)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    v = np.maximum(np.maximum(b, g), r)
    delta = v - np.minimum(np.minimum(b, g), r)
    safe_delta = np.where(delta > 0, delta, 1.0)
    safe_v = np.where(v > 0, v, 1.0)

    s = np.where(v > 0, delta / safe_v * 255.0, 0.0)
    h = np.where(v == r, 60.0 * (g - b) / safe_delta,
                 np.where(v == g, 120.0 + 60.0 * (b - r) / safe_delta,
                          240.0 + 60.0 * (r - g) / safe_delta))
    h = np.where(delta > 0, h, 0.0)
    h = np.where(h < 0, h + 360.0, h)

    out = np.empty(bgr.shape, dtype=np.uint8)
    out[..., 0] = np.mod(np.rint(h / 2.0), 180).astype(np.uint8)
    out[..., 1] = np.rint(s).astype(np.uint8)
    out[..., 2] = np.rint(v).astype(np.uint8)
    return out


# =============================================================================
# Stage 3: thresholding
# =============================================================================
def threshold_hsv(hsv: np.ndarray, low: HSV, high: HSV) -> np.ndarray:
    """Boolean mask of pixels whose H, S and V all lie inside [low, high] (hue may wrap)."""
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if low[0] <= high[0]:
        hue_ok = (h >= low[0]) & (h <= high[0])
    else:                                  # wrapped range, e.g. red: 170..10
        hue_ok = (h >= low[0]) | (h <= high[0])
    return hue_ok & (s >= low[1]) & (s <= high[1]) & (v >= low[2]) & (v <= high[2])


# =============================================================================
# Stage 4: morphology (separable min / max filters)
# =============================================================================
def _window_reduce(a: np.ndarray, k: int, axis: int, reducer, pad_value: bool) -> np.ndarray:
    pad = k // 2
    widths = [(0, 0)] * a.ndim
    widths[axis] = (pad, pad)
    padded = np.pad(a, widths, mode="constant", constant_values=pad_value)
    return reducer(sliding_window_view(padded, k, axis=axis), axis=-1)


def erode(mask: np.ndarray, k: int) -> np.ndarray:
    """Binary erosion with a k x k square: a pixel survives only if its whole window is set.
    The border counts as foreground so blobs touching the image edge are not eaten away."""
    k = int(k) | 1
    if k <= 1:
        return mask
    return _window_reduce(_window_reduce(mask, k, 1, np.all, True), k, 0, np.all, True)


def dilate(mask: np.ndarray, k: int) -> np.ndarray:
    """Binary dilation with a k x k square: a pixel is set if any pixel of its window is set."""
    k = int(k) | 1
    if k <= 1:
        return mask
    return _window_reduce(_window_reduce(mask, k, 1, np.any, False), k, 0, np.any, False)


def opening(mask: np.ndarray, k: int) -> np.ndarray:
    return dilate(erode(mask, k), k)


def closing(mask: np.ndarray, k: int) -> np.ndarray:
    return erode(dilate(mask, k), k)


# =============================================================================
# Stage 5-6: connected components + moments (run-length two-pass labelling)
# =============================================================================
def connected_components(mask: np.ndarray, max_runs: int = MAX_RUNS) -> list[Component]:
    """Label 8-connected blobs of a boolean mask and compute their statistics.

    1. Extract horizontal runs (row, start, end) with one np.diff.
    2. Union-find: two runs on consecutive rows belong to the same blob when their column
       ranges touch (8-connectivity: s2 <= e1 and e2 >= s1 with exclusive ends).
    3. Sum the closed-form per-run moments per blob with np.bincount.

    Raises ValueError when the mask holds more than `max_runs` runs (pure noise).
    """
    height, width = mask.shape
    padded = np.zeros((height, width + 2), dtype=np.int8)
    padded[:, 1:-1] = mask
    d = np.diff(padded, axis=1)
    rows, starts = np.nonzero(d == 1)
    _, ends = np.nonzero(d == -1)            # exclusive end columns, same row-major order
    n = len(rows)
    if n == 0:
        return []
    if n > max_runs:
        raise ValueError("too many runs")

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    first = np.searchsorted(rows, np.arange(height + 1)).tolist()
    s_list, e_list = starts.tolist(), ends.tolist()
    for r in range(height - 1):
        i, i_end = first[r], first[r + 1]
        j, j_end = first[r + 1], first[r + 2]
        while i < i_end and j < j_end:
            if s_list[j] <= e_list[i] and e_list[j] >= s_list[i]:
                union(i, j)
            if e_list[i] < e_list[j]:
                i += 1
            else:
                j += 1

    roots = np.fromiter((find(i) for i in range(n)), dtype=np.int64, count=n)
    _, inv = np.unique(roots, return_inverse=True)
    count = int(inv.max()) + 1

    s = starts.astype(np.float64)
    e = ends.astype(np.float64)
    y = rows.astype(np.float64)
    length = e - s
    sum_x = (s + e - 1.0) * length / 2.0
    sum_xx = ((e - 1.0) * e * (2.0 * e - 1.0) - (s - 1.0) * s * (2.0 * s - 1.0)) / 6.0

    def acc(w):
        return np.bincount(inv, weights=w, minlength=count)

    m00 = acc(length)
    m10 = acc(sum_x)
    m01 = acc(y * length)
    m20 = acc(sum_xx)
    m02 = acc(y * y * length)
    m11 = acc(y * sum_x)

    x0 = np.full(count, np.iinfo(np.int64).max)
    x1 = np.zeros(count, dtype=np.int64)
    y0 = np.full(count, np.iinfo(np.int64).max)
    y1 = np.zeros(count, dtype=np.int64)
    np.minimum.at(x0, inv, starts)
    np.maximum.at(x1, inv, ends)
    np.minimum.at(y0, inv, rows)
    np.maximum.at(y1, inv, rows + 1)

    out = []
    for c in range(count):
        a = m00[c]
        cx, cy = m10[c] / a, m01[c] / a
        out.append(Component(
            area=int(a), cx=float(cx), cy=float(cy),
            x0=int(x0[c]), y0=int(y0[c]), x1=int(x1[c]), y1=int(y1[c]),
            mu20=float(m20[c] / a - cx * cx), mu02=float(m02[c] / a - cy * cy),
            mu11=float(m11[c] / a - cx * cy)))
    return out


def component_confidence(c: Component) -> float:
    """Shape validity in 0..1: how much the blob looks like a compact round/square marker.

        fill   = area / (bbox width * bbox height)    disc = pi/4 = 0.785, square = 1, thin line ~ 0.1
        aspect = min(w, h) / max(w, h)                1 for compact blobs, small for sticks
        confidence = min(1, fill / 0.78) * aspect
    """
    box = c.width * c.height
    if box <= 0:
        return 0.0
    fill = c.area / box
    aspect = min(c.width, c.height) / max(c.width, c.height)
    return float(min(1.0, fill / 0.78) * aspect)


# =============================================================================
# Colour sampling helpers (used by the tuning panel)
# =============================================================================
def hsv_range_from_sample(sample: HSV, sensitivity: float = 50.0) -> tuple[HSV, HSV]:
    """HSV window around a picked colour. Sensitivity 0..100 widens the tolerances:
    hue +-(10 + 0.3 s), saturation +-(60 + s), value +-(80 + s). Hue wraps around 0/179."""
    h, s, v = (float(x) for x in sample)
    sens = min(max(float(sensitivity), 0.0), 100.0)
    h_tol, s_tol, v_tol = 10 + 0.3 * sens, 60 + sens, 80 + sens
    if h_tol >= 90:
        low_h, high_h = 0, 179
    else:
        low_h, high_h = int(round(h - h_tol)) % 180, int(round(h + h_tol)) % 180
    low = (low_h, max(0, int(round(s - s_tol))), max(0, int(round(v - v_tol))))
    high = (high_h, min(255, int(round(s + s_tol))), min(255, int(round(v + v_tol))))
    return low, high


def median_hsv_at(frame_bgr: np.ndarray, x: float, y: float, radius: int = 4) -> HSV:
    """Representative HSV of the patch around (x, y). Hue is averaged as an angle so reds
    (which sit on both sides of 0) do not average to green."""
    h_img, w_img = frame_bgr.shape[:2]
    xi, yi = int(round(x)), int(round(y))
    patch = frame_bgr[max(yi - radius, 0):min(yi + radius + 1, h_img),
                      max(xi - radius, 0):min(xi + radius + 1, w_img)]
    if patch.size == 0:
        raise ValueError("sample point is outside the frame")
    hsv = bgr_to_hsv(patch).reshape(-1, 3)
    angle = hsv[:, 0].astype(np.float64) * (2.0 * math.pi / 180.0)
    hue = (math.atan2(np.sin(angle).mean(), np.cos(angle).mean()) % (2.0 * math.pi)) * 90.0 / math.pi
    return int(round(hue)) % 180, int(np.median(hsv[:, 1])), int(np.median(hsv[:, 2]))


# =============================================================================
# Full detector
# =============================================================================
def detect(frame_bgr: np.ndarray, params: DetectionParams) -> DetectionResult:
    t0 = time.perf_counter()
    h, w = frame_bgr.shape[:2]
    if w > params.detect_width:
        small_w = params.detect_width
        small_h = max(1, int(round(h * small_w / w)))
        small = cv2.resize(frame_bgr, (small_w, small_h), interpolation=cv2.INTER_AREA)
    else:
        small = frame_bgr
    sh, sw = small.shape[:2]
    sx, sy = sw / w, sh / h                       # camera px -> detection px

    hsv = bgr_to_hsv(small)
    raw = threshold_hsv(hsv, params.hsv_low, params.hsv_high)
    clean = closing(opening(raw, params.kernel_size), params.kernel_size)
    mask_u8 = clean.astype(np.uint8) * 255

    def result(detection, status, message, count=0) -> DetectionResult:
        return DetectionResult(detection, status, message, mask_u8, count,
                               (time.perf_counter() - t0) * 1000.0)

    try:
        comps = connected_components(clean)
    except ValueError:
        return result(None, "noisy", "Too much noise: tighten the HSV range or raise the kernel size")
    if not comps:
        return result(None, "no_pixels", "No marker-coloured pixels in view")

    area_scale = 1.0 / (sx * sy)                  # detection px^2 -> camera px^2
    best, best_score = None, -1.0
    for c in comps:
        area = c.area * area_scale
        if not (params.min_area <= area <= params.max_area):
            continue
        conf = component_confidence(c)
        if conf < params.confidence_min:
            continue
        score = area * conf
        if score > best_score:
            best, best_score = (c, area, conf), score

    if best is None:                              # explain why using the largest blob
        c = max(comps, key=lambda comp: comp.area)
        area = c.area * area_scale
        if area < params.min_area:
            return result(None, "area_too_small",
                          f"Largest blob too small ({area:.0f} px < {params.min_area} px)", len(comps))
        if area > params.max_area:
            return result(None, "area_too_large",
                          f"Largest blob too big ({area:.0f} px > {params.max_area} px)", len(comps))
        return result(None, "low_confidence",
                      f"Blob shape rejected (confidence {component_confidence(c):.2f} "
                      f"< {params.confidence_min:.2f})", len(comps))

    c, area, conf = best
    # detection-pixel index j covers camera pixels [j/s, (j+1)/s); centre of pixel i is at i
    det = Detection(
        x=(c.cx + 0.5) / sx - 0.5, y=(c.cy + 0.5) / sy - 0.5, area=float(area), confidence=conf,
        bbox=(c.x0 / sx, c.y0 / sy, c.x1 / sx, c.y1 / sy))
    return result(det, "ok", f"Marker found - area {area:.0f} px, confidence {conf:.2f}", len(comps))
