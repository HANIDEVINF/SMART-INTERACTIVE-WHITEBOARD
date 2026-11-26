"""Image I/O and geometry helpers.

Windows note: ``cv2.imread`` / ``cv2.imwrite`` silently fail on paths containing non-ASCII
characters (accents, Arabic, ...). We therefore decode/encode in memory and let NumPy do the
actual file access, which is Unicode-safe.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp)"


def imread_unicode(path: str | Path) -> np.ndarray | None:
    """Read an image as a BGR uint8 array, or return None if it is missing/invalid."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.dtype != np.uint8:  # 16-bit PNG etc.
        img = cv2.convertScaleAbs(img, alpha=255.0 / np.iinfo(img.dtype).max) \
            if np.issubdtype(img.dtype, np.integer) else None
        if img is None:
            return None
    if img.ndim == 2:  # grayscale -> BGR
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:  # BGRA -> flatten over white so transparency is not shown as black
        alpha = img[..., 3:4].astype(np.float32) / 255.0
        rgb = img[..., :3].astype(np.float32)
        return np.rint(rgb * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    return img


def imwrite_unicode(path: str | Path, img: np.ndarray) -> None:
    """Write an image (format chosen from the file extension). Raises OSError/ValueError."""
    ext = Path(path).suffix.lower() or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise ValueError(f"Could not encode image as {ext}")
    buf.tofile(str(path))


def fit_rect(src_w: int, src_h: int, dst_w: int, dst_h: int) -> tuple[int, int, int, int]:
    """Largest rectangle with the aspect ratio of (src_w, src_h) centred inside (dst_w, dst_h).

    Returns (x, y, w, h). This is the "fit to canvas" computation of the image viewer:
        scale = min(dst_w / src_w, dst_h / src_h)
    """
    if src_w <= 0 or src_h <= 0 or dst_w <= 0 or dst_h <= 0:
        raise ValueError("All dimensions must be positive")
    scale = min(dst_w / src_w, dst_h / src_h)
    w = max(1, int(round(src_w * scale)))
    h = max(1, int(round(src_h * scale)))
    return (dst_w - w) // 2, (dst_h - h) // 2, w, h


def fit_image(img: np.ndarray, dst_w: int, dst_h: int,
              fill_bgr: tuple[int, int, int]) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Letterbox `img` into a (dst_h, dst_w) canvas, preserving its aspect ratio."""
    h, w = img.shape[:2]
    x, y, rw, rh = fit_rect(w, h, dst_w, dst_h)
    interp = cv2.INTER_AREA if rw < w else cv2.INTER_LINEAR
    resized = cv2.resize(img, (rw, rh), interpolation=interp)
    canvas = np.empty((dst_h, dst_w, 3), dtype=np.uint8)
    canvas[:] = fill_bgr
    canvas[y:y + rh, x:x + rw] = resized
    return canvas, (x, y, rw, rh)
