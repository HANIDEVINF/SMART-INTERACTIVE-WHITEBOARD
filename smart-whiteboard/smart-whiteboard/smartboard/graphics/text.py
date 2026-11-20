"""Crisp anti-aliased text.

Uses Pillow + the bundled Inter font when available (rendered once, cached
as an alpha mask and blended with NumPy); falls back to cv2.putText so the
program still runs without Pillow.  (Rasterising a font file is outside the
scope of the project -> justified use of a library.)
"""
from __future__ import annotations

import os
from collections import OrderedDict
from typing import Tuple

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_FONT_DIRS = [os.path.join(_HERE, "..", "..", "assets", "fonts"), "assets/fonts"]
_SYSTEM = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
           "/usr/share/fonts/opentype/inter/Inter-Regular.otf"]
_SYSTEM_BOLD = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/opentype/inter/Inter-Bold.otf"]


def _find(names, system):
    for d in _FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    for p in system:
        if os.path.exists(p):
            return p
    return None


class TextRenderer:
    def __init__(self):
        try:
            from PIL import ImageFont  # noqa: F401
            self._pil = True
        except ImportError:
            self._pil = False
        self.regular = _find(["Inter-Regular.otf"], _SYSTEM)
        self.bold = _find(["Inter-Bold.otf"], _SYSTEM_BOLD) or self.regular
        self._fonts = {}
        self._cache: "OrderedDict" = OrderedDict()
        self.use_pil = self._pil and self.regular is not None

    def _font(self, size: int, bold: bool):
        from PIL import ImageFont
        key = (size, bold)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(self.bold if bold else self.regular, size)
        return self._fonts[key]

    def mask(self, s: str, size: int, bold: bool = False) -> Tuple[np.ndarray, int]:
        """(alpha mask HxW uint8, distance from the top of the mask to the baseline)."""
        key = (s, size, bold)
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            return hit
        if self.use_pil:
            from PIL import Image, ImageDraw
            f = self._font(size, bold)
            asc, desc = f.getmetrics()
            w = max(1, int(np.ceil(f.getlength(s))) + 2)
            im = Image.new("L", (w, asc + desc + 2), 0)
            ImageDraw.Draw(im).text((1, 0), s, font=f, fill=255)
            m, base = np.asarray(im, np.uint8), asc
        else:                                            # cv2 fallback
            import cv2
            scale = size / 28.0
            th = 2 if bold else 1
            (w, h), bl = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, th)
            m = np.zeros((h + bl + 4, w + 4), np.uint8)
            cv2.putText(m, s, (2, h + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, 255, th, cv2.LINE_AA)
            base = h + 1
        self._cache[key] = (m, base)
        if len(self._cache) > 800:
            self._cache.popitem(last=False)
        return self._cache[key]

    def size(self, s: str, size: int, bold: bool = False) -> Tuple[int, int]:
        m, _ = self.mask(s, size, bold)
        return m.shape[1] - 2, m.shape[0]

    def fit(self, s: str, size: int, max_w: int, bold: bool = False) -> str:
        """Shorten ``s`` with an ellipsis so that it is at most max_w pixels wide."""
        if self.size(s, size, bold)[0] <= max_w:
            return s
        while len(s) > 1 and self.size(s + "...", size, bold)[0] > max_w:
            s = s[:-1]
        return s + "..."

    def draw(self, img, s, x, y, size=28, color=(255, 255, 255), bold=False, anchor="lt", alpha=1.0):
        """anchor = horizontal l/c/r + vertical t/m/b ('m' = middle of the capital letters)."""
        if not s:
            return
        size = int(size)
        m, base = self.mask(s, size, bold)
        h, w = m.shape
        ox = {"l": 0, "c": -(w - 2) / 2.0, "r": -(w - 2)}[anchor[0]]
        oy = {"t": 0.0, "m": -base + 0.36 * size, "b": -base}[anchor[1]]
        x0, y0 = int(round(x + ox)) - 1, int(round(y + oy))
        ix0, iy0 = max(0, x0), max(0, y0)
        ix1, iy1 = min(img.shape[1], x0 + w), min(img.shape[0], y0 + h)
        if ix1 <= ix0 or iy1 <= iy0:
            return
        a = m[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0].astype(np.float32) * (alpha / 255.0)
        reg = img[iy0:iy1, ix0:ix1]
        reg[:] = (reg + (np.asarray(color, np.float32) - reg) * a[..., None] + 0.5).astype(np.uint8)


_TEXT = None


def get_text() -> TextRenderer:
    global _TEXT
    if _TEXT is None:
        _TEXT = TextRenderer()
    return _TEXT
