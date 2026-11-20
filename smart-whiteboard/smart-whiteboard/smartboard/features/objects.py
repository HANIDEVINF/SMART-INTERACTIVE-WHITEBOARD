"""FEATURE: object drag & drop.

Click-to-grab / click-to-drop (the remote cannot "hold"):
    LEFT click on an object   -> grabbed, it follows the pointer
    LEFT click again          -> dropped (a drop zone can snap/validate it)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from ..graphics import primitives as P
from ..graphics import theme


@dataclass
class Shape:
    kind: str                    # square | circle | triangle | star
    x: float
    y: float
    size: float
    color: Tuple[int, int, int]
    home: Tuple[float, float] = (0, 0)

    def contains(self, px, py) -> bool:
        r = self.size
        if self.kind == "circle":
            return (px - self.x) ** 2 + (py - self.y) ** 2 <= r * r
        return abs(px - self.x) <= r and abs(py - self.y) <= r   # bounding box for the others

    def draw(self, img, grabbed: bool = False):
        r = self.size
        if self.kind == "square":
            P.fill_rect(img, self.x - r, self.y - r, self.x + r, self.y + r, self.color)
        elif self.kind == "circle":
            P.fill_circle(img, (self.x, self.y), r, self.color)
        elif self.kind == "triangle":
            P.fill_polygon(img, [(self.x, self.y - r), (self.x + r, self.y + r), (self.x - r, self.y + r)], self.color)
        elif self.kind == "star":
            P.fill_polygon(img, P.star_points(self.x, self.y, r * 1.15, r * 0.5), self.color)
        if grabbed:
            P.rect_outline(img, self.x - r - 8, self.y - r - 8, self.x + r + 8, self.y + r + 8, theme.WHITE, 3)


@dataclass
class Zone:
    rect: Tuple[int, int, int, int]
    kind: str
    label: str


class Scene:
    """A tiny 'sort the shapes' exercise: drop each shape in the zone with its name."""

    def __init__(self, width: int, height: int, top: int):
        self.w, self.h, self.top = width, height, top
        self.shapes: List[Shape] = []
        self.zones: List[Zone] = []
        self.grabbed: Optional[Shape] = None
        self._offset = (0.0, 0.0)
        self.build()

    def build(self):
        w, h, top = self.w, self.h, self.top
        self.grabbed = None
        cols = [(0, 225, 255), (255, 220, 40), (90, 230, 110), (255, 90, 230)]
        kinds = ["square", "circle", "triangle", "star"]
        self.shapes = []
        for i, (k, c) in enumerate(zip(kinds, cols)):
            x = w * (0.2 + 0.2 * i)
            y = top + (h - top) * 0.30
            self.shapes.append(Shape(k, x, y, 60, c, (x, y)))
        zw, zh = w * 0.18, (h - top) * 0.26
        self.zones = []
        for i, k in enumerate(kinds):
            x0 = w * (0.2 + 0.2 * i) - zw / 2
            y0 = top + (h - top) * 0.62
            self.zones.append(Zone((int(x0), int(y0), int(x0 + zw), int(y0 + zh)), k, k.capitalize()))

    def reset(self):
        self.build()

    def top_shape_at(self, x, y) -> Optional[Shape]:
        for s in reversed(self.shapes):
            if s.contains(x, y):
                return s
        return None

    def click(self, pos) -> str:
        """LEFT click handler. Returns a message for the toast ('' = nothing)."""
        if self.grabbed is not None:
            s, self.grabbed = self.grabbed, None
            for z in self.zones:
                x0, y0, x1, y1 = z.rect
                if x0 <= s.x < x1 and y0 <= s.y < y1:
                    s.x, s.y = (x0 + x1) / 2, (y0 + y1) / 2
                    return "Correct!" if z.kind == s.kind else f"This is a {s.kind}, not a {z.kind}"
            return ""
        s = self.top_shape_at(*pos)
        if s:
            self.grabbed = s
            self._offset = (s.x - pos[0], s.y - pos[1])
            self.shapes.remove(s)       # bring to front
            self.shapes.append(s)
            return "Grabbed - click again to drop"
        return ""

    def move(self, pos):
        if self.grabbed is not None and pos is not None:
            self.grabbed.x = pos[0] + self._offset[0]
            self.grabbed.y = pos[1] + self._offset[1]

    def solved(self) -> bool:
        for s in self.shapes:
            ok = any(z.kind == s.kind and z.rect[0] <= s.x < z.rect[2] and z.rect[1] <= s.y < z.rect[3]
                     for z in self.zones)
            if not ok:
                return False
        return True
