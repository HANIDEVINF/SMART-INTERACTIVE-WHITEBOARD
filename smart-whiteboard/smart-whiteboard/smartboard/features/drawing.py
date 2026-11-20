"""FEATURE: free drawing.

Pure logic - no rendering of buttons, no input handling.  Because the
remote has no "hold" state, the pen works as a toggle: a LEFT click puts the
pen down, the next LEFT click lifts it.  While the pen is down the stroke
follows the pointer.

The drawing is a list of strokes (so Undo is possible) rendered into a
layer + boolean mask (so it can be composited over any background; the
eraser really removes ink).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from ..graphics import primitives as P
from ..graphics import theme


@dataclass
class Stroke:
    points: List[Tuple[float, float]]
    color: Tuple[int, int, int]
    radius: float
    erase: bool = False


class DrawingCanvas:
    MIN_STEP = 2.0          # ignore pointer moves smaller than this (px)

    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.layer = np.zeros((height, width, 3), np.uint8)
        self.mask = np.zeros((height, width), bool)
        self.strokes: List[Stroke] = []
        self.color_idx = 0
        self.size_idx = 1
        self.eraser = False
        self.pen_down = False
        self._cur: Optional[Stroke] = None

    # ---- pen settings -------------------------------------------------------------
    @property
    def color(self):
        return theme.PEN_COLORS[self.color_idx][1]

    @property
    def radius(self) -> float:
        return theme.PEN_SIZES[self.size_idx][1] * (3.0 if self.eraser else 1.0) / 2.0

    def set_color(self, idx: int):
        self.color_idx, self.eraser = idx, False

    def set_size(self, idx: int):
        self.size_idx = idx

    def set_eraser(self, on: bool = True):
        self.eraser = on

    # ---- pen state machine ----------------------------------------------------------
    def toggle_pen(self, pos):
        """LEFT click on the drawing area."""
        if self.pen_down:
            self.lift()
        else:
            self.lower(pos)

    def lower(self, pos):
        if pos is None:
            return
        self.pen_down = True
        self._cur = Stroke([pos], self.color, self.radius, self.eraser)
        self.strokes.append(self._cur)
        self._paint(self._cur, pos, pos)

    def lift(self):
        self.pen_down = False
        self._cur = None

    def move(self, pos):
        """Call every frame with the pointer position."""
        if not self.pen_down or self._cur is None or pos is None:
            return
        last = self._cur.points[-1]
        if np.hypot(pos[0] - last[0], pos[1] - last[1]) < self.MIN_STEP:
            return
        self._cur.points.append(pos)
        self._paint(self._cur, last, pos)

    # ---- editing -------------------------------------------------------------------------
    def undo(self):
        self.lift()
        if self.strokes:
            self.strokes.pop()
            self._redraw()

    def clear(self):
        self.lift()
        self.strokes.clear()
        self.layer[:] = 0
        self.mask[:] = False

    # ---- rendering -------------------------------------------------------------------------
    def _paint(self, s: Stroke, a, b):
        sy, sx, m = P.segment_mask(self.layer.shape, a, b, s.radius)
        if m.size:
            if s.erase:
                self.mask[sy, sx][m] = False
            else:
                self.layer[sy, sx][m] = s.color
                self.mask[sy, sx][m] = True

    def _redraw(self):
        self.layer[:] = 0
        self.mask[:] = False
        for s in self.strokes:
            if len(s.points) == 1:
                self._paint(s, s.points[0], s.points[0])
            for a, b in zip(s.points[:-1], s.points[1:]):
                self._paint(s, a, b)

    def render_onto(self, img: np.ndarray, top: int = 0):
        """Composite the ink over ``img`` (rows >= top only)."""
        m = self.mask[top:]
        img[top:][m] = self.layer[top:][m]
