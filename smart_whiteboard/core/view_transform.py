"""Zoom and pan of the board content (the image viewer).

The *content* (background image + drawing) lives in content coordinates ``(0..W, 0..H)``.  The *view* shows it
magnified by ``zoom`` and shifted by ``(ox, oy)`` on the fixed ``W x H`` board:

    screen = content * zoom + (ox, oy)            content = (screen - (ox, oy)) / zoom

The pointer, the menu and the click ripples stay in *screen* (board) coordinates, so the menu never moves; drawing
is converted to content coordinates, so annotations stay glued to the image when it is zoomed or panned.

Constraints: ``1 <= zoom <= MAX_ZOOM`` and the content always covers the board (no empty margins appear):
``W - W*zoom <= ox <= 0``.  Zooming keeps the point under the anchor fixed.
"""
from __future__ import annotations

MIN_ZOOM = 1.0
MAX_ZOOM = 8.0
ZOOM_STEP = 1.25


class ViewTransform:
    def __init__(self, width: float, height: float) -> None:
        self.w, self.h = float(width), float(height)
        self.zoom = 1.0
        self.ox = 0.0
        self.oy = 0.0

    # -- state ----------------------------------------------------------------------------------------------------
    @property
    def is_identity(self) -> bool:
        return self.zoom == 1.0 and self.ox == 0.0 and self.oy == 0.0

    @property
    def percent(self) -> int:
        return int(round(self.zoom * 100))

    def reset(self) -> None:
        self.zoom, self.ox, self.oy = 1.0, 0.0, 0.0

    def _clamp(self) -> None:
        self.zoom = min(max(self.zoom, MIN_ZOOM), MAX_ZOOM)
        self.ox = min(0.0, max(self.w - self.w * self.zoom, self.ox))
        self.oy = min(0.0, max(self.h - self.h * self.zoom, self.oy))
        if self.zoom == 1.0:
            self.ox = self.oy = 0.0

    # -- conversions ----------------------------------------------------------------------------------------------
    def to_content(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.ox) / self.zoom, (y - self.oy) / self.zoom

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        return x * self.zoom + self.ox, y * self.zoom + self.oy

    def visible_rect(self) -> tuple[float, float, float, float]:
        """The part of the content that is on screen: (x, y, w, h) in content coordinates."""
        return -self.ox / self.zoom, -self.oy / self.zoom, self.w / self.zoom, self.h / self.zoom

    # -- operations ----------------------------------------------------------------------------------------------
    def set_zoom_at(self, zoom: float, ax: float | None = None, ay: float | None = None) -> None:
        """Zoom to ``zoom`` keeping screen point (ax, ay) fixed (default: the centre of the board)."""
        ax = self.w / 2 if ax is None else ax
        ay = self.h / 2 if ay is None else ay
        cx, cy = self.to_content(ax, ay)
        self.zoom = min(max(zoom, MIN_ZOOM), MAX_ZOOM)
        self.ox, self.oy = ax - cx * self.zoom, ay - cy * self.zoom
        self._clamp()

    def zoom_at(self, factor: float, ax: float | None = None, ay: float | None = None) -> None:
        self.set_zoom_at(self.zoom * factor, ax, ay)

    def zoom_in(self, ax: float | None = None, ay: float | None = None) -> None:
        self.zoom_at(ZOOM_STEP, ax, ay)

    def zoom_out(self, ax: float | None = None, ay: float | None = None) -> None:
        self.zoom_at(1 / ZOOM_STEP, ax, ay)

    def pan_by(self, dx: float, dy: float) -> None:
        """Drag the content by (dx, dy) screen pixels."""
        self.ox += dx
        self.oy += dy
        self._clamp()

    def move_view(self, fx: float, fy: float) -> None:
        """Move the *view window* by a fraction of the board (fx=+0.25 looks 25 % further right)."""
        self.pan_by(-fx * self.w, -fy * self.h)
