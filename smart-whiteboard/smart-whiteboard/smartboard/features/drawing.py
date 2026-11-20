"""FEATURE: free drawing + shape tools.

Pure logic - no rendering of buttons, no input handling.  Because the remote
has no "hold" state, drawing works with clicks:
    pen / eraser : LEFT click puts the pen down, the next LEFT click lifts it
    line / arrow / rectangle / ellipse :
                   LEFT click = first corner, LEFT click again = second corner
                   (a live preview follows the pointer in between)

Ink is stored as a list of strokes (so Undo / Redo are possible) and
rendered into a PREMULTIPLIED RGBA layer:  P = colour * alpha (HxWx3),  A (HxW).
Painting a shape with coverage c (0..1, anti-aliased):
        P <- P (1-c) + colour c          A <- A (1-c) + 255 c         (ink)
        P <- P (1-c)                     A <- A (1-c)                 (eraser)
and the layer goes over any background:   out = bg (255-A)/255 + P.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from ..graphics import primitives as P
from ..graphics import theme

TOOLS = ["pen", "line", "arrow", "rect", "ellipse", "eraser"]
SHAPE_TOOLS = ("line", "arrow", "rect", "ellipse")


@dataclass
class Stroke:
    tool: str
    points: List[Tuple[float, float]]
    color: Tuple[int, int, int]
    radius: float

    @property
    def erase(self) -> bool:
        return self.tool == "eraser"


def shape_segments(tool: str, a, b, radius: float):
    """Polyline pieces [(p, q), ...] that draw a shape between corner a and corner b."""
    (x0, y0), (x1, y1) = a, b
    if tool == "line":
        return [(a, b)]
    if tool == "arrow":
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1:
            return [(a, b)]
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        h = min(L * 0.4, 18 + radius * 4)
        wing = lambda s: (x1 - h * (ux * math.cos(0.5) - s * uy * math.sin(0.5)),
                          y1 - h * (uy * math.cos(0.5) + s * ux * math.sin(0.5)))
        return [(a, b), (b, wing(1)), (b, wing(-1))]
    if tool == "rect":
        c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        return [(c[i], c[(i + 1) % 4]) for i in range(4)]
    if tool == "ellipse":
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0) / 2, abs(y1 - y0) / 2
        n = int(min(96, max(16, (rx + ry) / 4)))
        pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]
        return list(zip(pts[:-1], pts[1:]))
    return []


class DrawingCanvas:
    MIN_STEP = 2.0          # ignore pointer moves smaller than this (px)

    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.P = np.zeros((height, width, 3), np.uint8)       # premultiplied colour
        self.A = np.zeros((height, width), np.uint8)          # alpha
        self.strokes: List[Stroke] = []
        self.redo_stack: List[Stroke] = []
        self.color_idx = 0
        self.size_idx = 1
        self.tool = "pen"
        self.pen_down = False
        self.anchor: Optional[Tuple[float, float]] = None     # first corner of a shape
        self.cursor: Optional[Tuple[float, float]] = None
        self._cur: Optional[Stroke] = None
        self._bbox: Optional[List[int]] = None                # region that holds ink
        self.version = 0                                      # +1 whenever the ink changes

    # ---- compatibility / state -----------------------------------------------------------
    @property
    def mask(self) -> np.ndarray:
        return self.A > 0

    @property
    def eraser(self) -> bool:
        return self.tool == "eraser"

    @property
    def active(self) -> bool:
        """True while a stroke / shape is in progress."""
        return self.pen_down or self.anchor is not None

    # ---- pen settings -----------------------------------------------------------------------
    @property
    def color(self):
        return theme.PEN_COLORS[self.color_idx][1]

    @property
    def radius(self) -> float:
        return theme.PEN_SIZES[self.size_idx][1] * (3.0 if self.eraser else 1.0) / 2.0

    def set_color(self, idx: int):
        self.color_idx = idx
        if self.tool == "eraser":
            self.tool = "pen"

    def set_size(self, idx: int):
        self.size_idx = idx

    def set_tool(self, tool: str):
        self.lift()
        self.tool = tool

    def set_eraser(self, on: bool = True):
        self.set_tool("eraser" if on else "pen")

    # ---- pen state machine ----------------------------------------------------------------------
    def toggle_pen(self, pos):
        """LEFT click on the drawing area."""
        if pos is None:
            return
        if self.tool in SHAPE_TOOLS:
            if self.anchor is None:
                self.anchor, self.cursor, self.pen_down = pos, pos, True
            else:
                self.commit_shape(pos)
        elif self.pen_down:
            self.lift()
        else:
            self.lower(pos)

    def lower(self, pos):
        if pos is None:
            return
        self.pen_down = True
        self.redo_stack.clear()
        self._cur = Stroke(self.tool, [pos], self.color, self.radius)
        self.strokes.append(self._cur)
        self._paint_segment(self._cur, pos, pos)

    def lift(self):
        self.pen_down = False
        self.anchor = None
        self._cur = None

    def move(self, pos):
        """Call every frame with the pointer position."""
        if pos is None:
            return
        self.cursor = pos
        if self.tool in SHAPE_TOOLS or not self.pen_down or self._cur is None:
            return
        last = self._cur.points[-1]
        if math.hypot(pos[0] - last[0], pos[1] - last[1]) < self.MIN_STEP:
            return
        self._cur.points.append(pos)
        self._paint_segment(self._cur, last, pos)

    def commit_shape(self, pos):
        a, self.anchor, self.pen_down = self.anchor, None, False
        if a is None or math.hypot(pos[0] - a[0], pos[1] - a[1]) < 4:
            return False
        s = Stroke(self.tool, [a, pos], self.color, self.radius)
        self.strokes.append(s)
        self.redo_stack.clear()
        self._paint_stroke(s)
        return True

    def preview(self):
        """Segments of the shape being placed (drawn by the screen, not stored)."""
        if self.anchor is None or self.cursor is None:
            return []
        return shape_segments(self.tool, self.anchor, self.cursor, self.radius)

    # ---- editing -------------------------------------------------------------------------------
    def undo(self):
        self.lift()
        if self.strokes:
            self.redo_stack.append(self.strokes.pop())
            self._redraw()

    def redo(self):
        self.lift()
        if self.redo_stack:
            s = self.redo_stack.pop()
            self.strokes.append(s)
            self._paint_stroke(s)

    def clear(self):
        self.lift()
        self.strokes.clear()
        self.redo_stack.clear()
        self.P[:] = 0
        self.A[:] = 0
        self._bbox = None
        self.version += 1

    # ---- rendering -------------------------------------------------------------------------------
    def _paint_segment(self, s: Stroke, a, b):
        r = s.radius
        bx0, by0, bx1, by1 = P._clip_box(self.A.shape, min(a[0], b[0]) - r - 1, min(a[1], b[1]) - r - 1,
                                         max(a[0], b[0]) + r + 1, max(a[1], b[1]) + r + 1)
        if bx1 <= bx0 or by1 <= by0:
            return
        xx, yy = P._grid(bx0, by0, bx1, by1)
        cov = np.clip(r + 0.5 - P._dist_to_segment(xx, yy, a[0], a[1], b[0], b[1]), 0, 1)
        A = self.A[by0:by1, bx0:bx1]
        Pm = self.P[by0:by1, bx0:bx1]
        if s.erase:
            k = (1 - cov)
            A[:] = (A * k + 0.5).astype(np.uint8)
            Pm[:] = (Pm * k[..., None] + 0.5).astype(np.uint8)
        else:
            Pm[:] = (Pm * (1 - cov)[..., None] + np.asarray(s.color, np.float32) * cov[..., None] + 0.5).astype(np.uint8)
            A[:] = (A * (1 - cov) + 255 * cov + 0.5).astype(np.uint8)
            if self._bbox is None:
                self._bbox = [bx0, by0, bx1, by1]
            else:
                bb = self._bbox
                bb[0], bb[1], bb[2], bb[3] = min(bb[0], bx0), min(bb[1], by0), max(bb[2], bx1), max(bb[3], by1)
        self.version += 1

    def _paint_stroke(self, s: Stroke):
        if s.tool in SHAPE_TOOLS:
            for a, b in shape_segments(s.tool, s.points[0], s.points[1], s.radius):
                self._paint_segment(s, a, b)
        elif len(s.points) == 1:
            self._paint_segment(s, s.points[0], s.points[0])
        else:
            for a, b in zip(s.points[:-1], s.points[1:]):
                self._paint_segment(s, a, b)

    def _redraw(self):
        self.P[:] = 0
        self.A[:] = 0
        self._bbox = None
        for s in self.strokes:
            self._paint_stroke(s)
        self.version += 1

    def render_onto(self, img: np.ndarray, top: int = 0):
        """Composite the ink over ``img`` (rows >= top only): out = img (255-A)/255 + P."""
        if self._bbox is None:
            return
        x0, y0, x1, y1 = self._bbox
        y0 = max(y0, top)
        if y1 <= y0 or x1 <= x0:
            return
        a = self.A[y0:y1, x0:x1]
        reg = img[y0:y1, x0:x1].astype(np.uint16)
        out = (reg * (255 - a)[..., None].astype(np.uint16) + 127) // 255 + self.P[y0:y1, x0:x1]
        img[y0:y1, x0:x1] = np.minimum(out, 255).astype(np.uint8)
