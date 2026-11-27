"""Drawing engine: a NumPy-based layered canvas with patch-based undo/redo.

Layers (all in *board coordinates*, e.g. 1600 x 900 px):
    background : optional BGR image (letter-boxed), otherwise a flat paper colour
    ink        : BGRA uint8 layer holding everything the user drew (straight alpha)
    composite  : BGR uint8 result shown on screen  = background blended with ink

Undo/redo
---------
Storing a full-canvas copy per action would cost ~6 MB each. Instead every action records
only the *bounding box that actually changed* together with the "before" and "after" pixels
of that box. A typical pen stroke therefore costs a few kilobytes.

The same engine will be driven by the camera pointer: the GUI only calls
begin_stroke / stroke_to / end_stroke (or the one-shot shape methods) with board coordinates,
no matter whether they originate from the mouse or from the tracked pointer.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from tools.image_tools import fit_image, imwrite_unicode
from tools.primitives import BBox, over, ring_coverage, segment_coverage, union_bbox


class Tool(str, Enum):
    PEN = "pen"
    ERASER = "eraser"
    LINE = "line"
    RECT = "rect"
    CIRCLE = "circle"
    TEXT = "text"


@dataclass
class _HistoryEntry:
    label: str
    bbox: BBox
    before: np.ndarray
    after: np.ndarray


_FONT_CANDIDATES = ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf")


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)  # Pillow >= 10.1


class DrawingEngine:
    def __init__(self, width: int = 1600, height: int = 900,
                 paper_rgb: tuple[int, int, int] = (250, 249, 246), max_history: int = 100) -> None:
        self.width, self.height = int(width), int(height)
        self.paper_bgr = (int(paper_rgb[2]), int(paper_rgb[1]), int(paper_rgb[0]))
        self.max_history = max_history

        self.ink = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.background: np.ndarray | None = None
        self.source: np.ndarray | None = None          # the image as loaded (full resolution, used when zoomed)
        self.placement: tuple[int, int, int, int] | None = None   # where `source` sits on the board (x, y, w, h)
        self.composite = np.empty((self.height, self.width, 3), dtype=np.uint8)

        self._stroke_cov = np.zeros((self.height, self.width), dtype=np.float32)
        self._snapshot: np.ndarray | None = None   # ink before the running action
        self._action_dirty: BBox | None = None     # union of boxes touched by the running action
        self._pending_dirty: BBox | None = None    # boxes not yet reported to the view
        self._undo: list[_HistoryEntry] = []
        self._redo: list[_HistoryEntry] = []

        self._stroke_tool = Tool.PEN
        self._stroke_color = (0, 0, 0)
        self._stroke_width = 6.0
        self._last_pt: tuple[float, float] | None = None

        self.refresh()

    # ------------------------------------------------------------ properties
    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def can_undo(self) -> bool:
        return bool(self._undo) and self._snapshot is None

    @property
    def can_redo(self) -> bool:
        return bool(self._redo) and self._snapshot is None

    @property
    def history_size(self) -> int:
        return len(self._undo)

    @property
    def has_ink(self) -> bool:
        return bool(self.ink[..., 3].any())

    @property
    def has_background(self) -> bool:
        return self.background is not None

    @property
    def in_action(self) -> bool:
        return self._snapshot is not None

    # ------------------------------------------------------------- composite
    def refresh(self, bbox: BBox | None = None) -> None:
        """Recompute the composite image for `bbox` (whole canvas when None)."""
        x0, y0, x1, y1 = bbox if bbox else (0, 0, self.width, self.height)
        if self.background is not None:
            base = self.background[y0:y1, x0:x1].astype(np.float32)
        else:
            base = np.asarray(self.paper_bgr, dtype=np.float32)
        ink = self.ink[y0:y1, x0:x1]
        alpha = ink[..., 3:4].astype(np.float32) / 255.0
        out = base * (1.0 - alpha) + ink[..., :3].astype(np.float32) * alpha
        self.composite[y0:y1, x0:x1] = np.rint(out).astype(np.uint8)

    def take_dirty(self) -> BBox | None:
        """Return (and clear) the region changed since the last call, refreshing the composite."""
        box, self._pending_dirty = self._pending_dirty, None
        if box is not None:
            self.refresh(box)
        return box

    def _mark(self, box: BBox) -> None:
        self._action_dirty = union_bbox(self._action_dirty, box)
        self._pending_dirty = union_bbox(self._pending_dirty, box)

    # --------------------------------------------------------------- actions
    def _begin(self) -> None:
        if self._snapshot is not None:  # a previous action was never closed: close it first
            self._finish("interrupted")
        self._snapshot = self.ink.copy()
        self._action_dirty = None

    def _finish(self, label: str) -> BBox | None:
        snap, self._snapshot = self._snapshot, None
        dirty, self._action_dirty = self._action_dirty, None
        if snap is None or dirty is None:
            return None
        x0, y0, x1, y1 = dirty
        self._stroke_cov[y0:y1, x0:x1] = 0.0
        diff = (snap[y0:y1, x0:x1] != self.ink[y0:y1, x0:x1]).any(axis=2)
        if not diff.any():
            return None
        ys = np.flatnonzero(diff.any(axis=1))
        xs = np.flatnonzero(diff.any(axis=0))
        box = (x0 + int(xs[0]), y0 + int(ys[0]), x0 + int(xs[-1]) + 1, y0 + int(ys[-1]) + 1)
        bx0, by0, bx1, by1 = box
        self._undo.append(_HistoryEntry(label, box, snap[by0:by1, bx0:bx1].copy(),
                                        self.ink[by0:by1, bx0:bx1].copy()))
        self._redo.clear()
        if len(self._undo) > self.max_history:
            self._undo.pop(0)
        return box

    def cancel_action(self) -> BBox | None:
        """Abort the running action and restore the ink layer."""
        snap, self._snapshot = self._snapshot, None
        dirty, self._action_dirty = self._action_dirty, None
        self._last_pt = None
        if snap is None or dirty is None:
            return None
        x0, y0, x1, y1 = dirty
        self.ink[y0:y1, x0:x1] = snap[y0:y1, x0:x1]
        self._stroke_cov[y0:y1, x0:x1] = 0.0
        self._pending_dirty = union_bbox(self._pending_dirty, dirty)
        return dirty

    def _apply(self, covered, color_bgr, erase: bool = False) -> None:
        """Blend a coverage map into the ink layer, always starting from the pre-action snapshot.

        Using the *maximum* coverage reached so far (not the sum) avoids the darker blobs that
        repeated compositing of overlapping, semi-transparent segment ends would create.
        """
        if covered is None or self._snapshot is None:
            return
        (x0, y0, x1, y1), cov = covered
        stroke = self._stroke_cov[y0:y1, x0:x1]
        np.maximum(stroke, cov, out=stroke)
        base = self._snapshot[y0:y1, x0:x1]
        if erase:
            out = base.copy()
            out[..., 3] = np.rint(base[..., 3].astype(np.float32) * (1.0 - stroke)).astype(np.uint8)
        else:
            out = over(base, color_bgr, stroke)
        self.ink[y0:y1, x0:x1] = out
        self._mark((x0, y0, x1, y1))

    # ---------------------------------------------------- live (pen / eraser)
    def begin_stroke(self, tool: Tool, color_bgr, width: float, pt) -> BBox | None:
        self._begin()
        self._stroke_tool, self._stroke_color, self._stroke_width = tool, color_bgr, float(width)
        self._last_pt = (float(pt[0]), float(pt[1]))
        self._segment(self._last_pt, self._last_pt)
        return self.take_dirty()

    def stroke_to(self, pt) -> BBox | None:
        if self._last_pt is None or self._snapshot is None:
            return None
        new = (float(pt[0]), float(pt[1]))
        self._segment(self._last_pt, new)
        self._last_pt = new
        return self.take_dirty()

    def end_stroke(self) -> BBox | None:
        self._last_pt = None
        self._finish("eraser" if self._stroke_tool == Tool.ERASER else "pen")
        return self.take_dirty()

    def _segment(self, p0, p1) -> None:
        cov = segment_coverage(self.ink.shape, p0, p1, self._stroke_width)
        self._apply(cov, self._stroke_color, erase=self._stroke_tool == Tool.ERASER)

    # ------------------------------------------------------------ one-shot shapes
    def draw_line(self, p0, p1, color_bgr, width: float) -> BBox | None:
        self._begin()
        self._apply(segment_coverage(self.ink.shape, p0, p1, width), color_bgr)
        self._finish("line")
        return self.take_dirty()

    def draw_rect(self, p0, p1, color_bgr, width: float) -> BBox | None:
        (x0, y0), (x1, y1) = p0, p1
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        self._begin()
        for a, b in zip(corners, corners[1:] + corners[:1]):
            self._apply(segment_coverage(self.ink.shape, a, b, width), color_bgr)
        self._finish("rectangle")
        return self.take_dirty()

    def draw_circle(self, center, radius: float, color_bgr, width: float) -> BBox | None:
        self._begin()
        self._apply(ring_coverage(self.ink.shape, center, max(radius, 0.5), width), color_bgr)
        self._finish("circle")
        return self.take_dirty()

    def draw_text(self, pt, text: str, color_bgr, size: int) -> BBox | None:
        """Render `text` (multi-line allowed) with Pillow into a coverage mask and composite it."""
        text = text.rstrip()
        if not text:
            return None
        font = _load_font(max(int(size), 8))
        probe = ImageDraw.Draw(Image.new("L", (1, 1)))
        l, t, r, b = probe.multiline_textbbox((0, 0), text, font=font)
        mask = Image.new("L", (int(r - l) + 4, int(b - t) + 4), 0)
        ImageDraw.Draw(mask).multiline_text((2 - l, 2 - t), text, font=font, fill=255)
        cov = np.asarray(mask, dtype=np.float32) / 255.0
        x, y = int(round(pt[0])), int(round(pt[1]))
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + cov.shape[1], self.width), min(y + cov.shape[0], self.height)
        if x0 >= x1 or y0 >= y1:
            return None
        cov = cov[y0 - y:y1 - y, x0 - x:x1 - x]
        self._begin()
        self._apply(((x0, y0, x1, y1), cov), color_bgr)
        self._finish("text")
        return self.take_dirty()

    # --------------------------------------------------------------- history
    def undo(self) -> BBox | None:
        if not self.can_undo:
            return None
        entry = self._undo.pop()
        x0, y0, x1, y1 = entry.bbox
        self.ink[y0:y1, x0:x1] = entry.before
        self._redo.append(entry)
        self.refresh(entry.bbox)
        return entry.bbox

    def redo(self) -> BBox | None:
        if not self.can_redo:
            return None
        entry = self._redo.pop()
        x0, y0, x1, y1 = entry.bbox
        self.ink[y0:y1, x0:x1] = entry.after
        self._undo.append(entry)
        self.refresh(entry.bbox)
        return entry.bbox

    # ----------------------------------------------------------- whole canvas
    def clear_ink(self) -> BBox | None:
        """Erase all drawings (undoable). The background image is kept."""
        self._begin()
        self.ink[:] = 0
        self._mark((0, 0, self.width, self.height))
        box = self._finish("clear")
        self.take_dirty()
        return box

    def set_background(self, image_bgr: np.ndarray | None) -> tuple[int, int, int, int] | None:
        """Show `image_bgr` letter-boxed behind the ink (aspect ratio preserved). None removes it."""
        placement = None
        if image_bgr is None:
            self.background = None
            self.source = None
        else:
            self.background, placement = fit_image(image_bgr, self.width, self.height, self.paper_bgr)
            self.source = np.ascontiguousarray(image_bgr)
        self.placement = placement
        self.refresh()
        self._pending_dirty = (0, 0, self.width, self.height)
        return placement

    def set_ink(self, ink: np.ndarray | None) -> None:
        """Replace the whole drawing layer (None = empty). Used to bring back a lesson page's annotations."""
        self._snapshot = None
        self._action_dirty = None
        self._last_pt = None
        if ink is None:
            self.ink[:] = 0
        else:
            if ink.shape != self.ink.shape:
                raise ValueError("ink layer has the wrong shape")
            self.ink[:] = ink
        self.refresh()
        self._pending_dirty = (0, 0, self.width, self.height)

    def clear_history(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def reset(self) -> None:
        """Back to a blank board: no ink, no background, empty history."""
        self._snapshot = None
        self._action_dirty = None
        self._last_pt = None
        self.ink[:] = 0
        self._stroke_cov[:] = 0.0
        self._undo.clear()
        self._redo.clear()
        self.background = None
        self.source = None
        self.placement = None
        self.refresh()
        self._pending_dirty = (0, 0, self.width, self.height)

    def export_png(self, path) -> None:
        imwrite_unicode(path, self.composite)
