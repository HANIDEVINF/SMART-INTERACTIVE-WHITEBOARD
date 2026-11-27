"""Drawing mode: annotation layer, strokes, undo/redo, export.

The annotation layer is a NumPy RGBA array (board-sized).  Strokes are
stored as point lists so undo/redo is cheap: undoing pops the last stroke
and the layer is rebuilt by replaying the remaining strokes through the
manual NumPy rasteriser in ``utils.image_processing.rasterize_line``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import pygame

from interface.components import (Button, COLORS, FONT_S, FONT_MB, PAD,
                                  Screen, layout_row)
from utils.image_processing import rasterize_line

logger = logging.getLogger(__name__)

# RGBA colours matching the configured pen colours (hex -> tuple).
def _hex_to_rgba(hex_color: str, alpha: int = 255):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r, g, b, alpha)


class DrawingCanvas:
    """Transparent annotation layer with stroke history."""

    def __init__(self, width: int, height: int, history_limit: int = 40):
        self.width = width
        self.height = height
        self.history_limit = history_limit
        self.layer = np.zeros((height, width, 4), dtype=np.uint8)
        self.strokes: list[dict] = []
        self.redo_stack: list[dict] = []
        self._surface: pygame.Surface | None = None
        self._dirty = True
        self._active: dict | None = None  # stroke currently being drawn

    # -- stroke API --------------------------------------------------------

    def begin_stroke(self, point, color, thickness: int) -> None:
        """Start a new stroke at ``point`` (board coordinates)."""
        self._active = {
            "points": [(float(point[0]), float(point[1]))],
            "color": tuple(color),
            "thickness": int(thickness),
        }

    def extend_stroke(self, point) -> None:
        """Add a point to the active stroke and rasterise the segment."""
        if self._active is None:
            return
        prev = self._active["points"][-1]
        new = (float(point[0]), float(point[1]))
        if np.hypot(new[0] - prev[0], new[1] - prev[1]) < 0.5:
            return  # ignore sub-pixel jitter
        self._active["points"].append(new)
        rasterize_line(self.layer, prev, new,
                       self._active["color"], self._active["thickness"])
        self._dirty = True

    def end_stroke(self) -> None:
        """Commit the active stroke to the history."""
        if self._active is None:
            return
        if len(self._active["points"]) >= 1:
            self.strokes.append(self._active)
            # Enforce the history limit by dropping oldest strokes.
            while len(self.strokes) > self.history_limit:
                self.strokes.pop(0)
        self.redo_stack.clear()
        self._active = None
        self._dirty = True

    # -- history -----------------------------------------------------------

    def undo(self) -> bool:
        """Remove the most recent stroke.  Returns True if something was undone."""
        if self._active is not None:
            self._active = None
        if not self.strokes:
            return False
        stroke = self.strokes.pop()
        self.redo_stack.append(stroke)
        self._rebuild()
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        stroke = self.redo_stack.pop()
        self.strokes.append(stroke)
        self._rebuild()
        return True

    def clear(self) -> None:
        self.strokes.clear()
        self.redo_stack.clear()
        self._active = None
        self._rebuild()

    def _rebuild(self) -> None:
        """Replay every stroke onto a fresh layer (used by undo/redo/clear)."""
        self.layer[:] = 0
        for stroke in self.strokes:
            pts = stroke["points"]
            for i in range(1, len(pts)):
                rasterize_line(self.layer, pts[i - 1], pts[i],
                               stroke["color"], stroke["thickness"])
        self._dirty = True

    # -- rendering / export ------------------------------------------------

    def to_surface(self) -> pygame.Surface:
        """Pygame surface of the annotation layer (cached until dirty)."""
        if self._surface is None or self._dirty:
            data = self.layer.tobytes()
            try:
                self._surface = pygame.image.frombytes(
                    data, (self.width, self.height), "RGBA")
            except AttributeError:  # older pygame
                self._surface = pygame.image.fromstring(
                    data, (self.width, self.height), "RGBA")
            self._dirty = False
        return self._surface

    def export(self, path) -> bool:
        """Save the annotation layer as a PNG image."""
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.to_surface(), str(path))
            logger.info("Annotations exported to %s", path)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Export failed: %s", exc)
            return False


class DrawingScreen(Screen):
    """Freehand annotation screen.

    Interaction model (designed for a pointer + two-button remote):

    * **left click on the board** -> pen down; move to draw; click again
      to lift the pen.  Leaving the board or losing the marker lifts it.
    * **right click** -> lift the pen and undo the last stroke.
    * toolbar: colours, thicknesses, Undo, Redo, Clear (asks to confirm),
      Save (PNG with the board background).
    """

    title = "Whiteboard"
    has_toolbar = True
    BOARDS = {"blank": "Blank board", "grid": "Grid board",
              "dark": "Dark board"}
    GRID = 40

    def __init__(self, app):
        super().__init__(app)
        self.board_style = "blank"
        self.pen_down = False
        self.drawing = False
        self._clear_armed_until = 0.0

        self.canvas_rect = self.body_rect
        self.canvas = DrawingCanvas(self.canvas_rect.w, self.canvas_rect.h,
                                    history_limit=int(
                                        app.settings.get("history_limit", 40)))
        self.color_idx = 0
        self.thickness_idx = 1

        colors = app.settings.get("pen_colors", ["#e53935", "#1e88e5",
                                                 "#43a047", "#212121"])
        self._base_colors = [_hex_to_rgba(c) for c in colors]
        self.thicknesses = list(app.settings.get("pen_thicknesses",
                                                 [3, 6, 10, 16]))
        self.pen_colors = list(self._base_colors)
        self._bg_cache: pygame.Surface | None = None
        self._build_toolbar()
        self.set_board("blank")

    # -- construction ------------------------------------------------------

    def _build_toolbar(self):
        swatch_w, text_w = 64, 104
        widths = ([swatch_w] * len(self.pen_colors) + [None] +
                  [swatch_w] * len(self.thicknesses) + [None] +
                  [text_w] * 4)
        rects = layout_row(self.toolbar_row_rect(), widths, gap=10)
        it = iter(rects)

        self.color_buttons = []
        for i in range(len(self.pen_colors)):
            b = Button(*next(it), on_click=lambda i=i: self._select_color(i),
                       style="secondary")
            self.color_buttons.append(b)
        self.thick_buttons = []
        for i, t in enumerate(self.thicknesses):
            b = Button(*next(it), on_click=lambda i=i: self._select_thickness(i),
                       style="secondary", icon=self._dot_icon(t))
            self.thick_buttons.append(b)
        self.btn_undo = Button(*next(it), "Undo", on_click=self._undo,
                               style="secondary", font=FONT_S)
        self.btn_redo = Button(*next(it), "Redo", on_click=self.canvas.redo,
                               style="secondary", font=FONT_S)
        self.btn_clear = Button(*next(it), "Clear", on_click=self._clear,
                                style="danger", font=FONT_S)
        self.btn_save = Button(*next(it), "Save", on_click=self._export,
                               style="success", font=FONT_S)
        self.buttons = (self.color_buttons + self.thick_buttons +
                        [self.btn_undo, self.btn_redo, self.btn_clear,
                         self.btn_save])

    @staticmethod
    def _dot_icon(thickness):
        def draw(surface, rect, color):
            r = max(2, min(rect.h // 2 - 10, int(thickness * 0.9) + 1))
            pygame.draw.circle(surface, color, rect.center, r)
        return draw

    # -- board style ---------------------------------------------------------

    def set_board(self, style: str) -> None:
        """Choose the drawing surface (blank / grid / dark)."""
        if style not in self.BOARDS:
            style = "blank"
        self.board_style = style
        self.title = f"Whiteboard - {self.BOARDS[style]}"
        # The 'ink' colour (index 3 by default) flips to white on the dark
        # board, where black would be invisible.
        self.pen_colors = list(self._base_colors)
        if style == "dark" and len(self.pen_colors) >= 4:
            self.pen_colors[3] = (245, 245, 245, 255)
        for i, b in enumerate(self.color_buttons):
            b.swatch = tuple(self.pen_colors[i][:3])
        self._bg_cache = None

    def on_enter(self):
        self.pen_down = False
        self._end_stroke()

    def _background(self) -> pygame.Surface:
        if self._bg_cache is None:
            r = self.canvas_rect
            surf = pygame.Surface(r.size)
            dark = self.board_style == "dark"
            surf.fill(COLORS["chalk"] if dark else COLORS["paper"])
            if self.board_style in ("grid", "dark"):
                color = COLORS["chalk_grid"] if dark else COLORS["grid"]
                for x in range(0, r.w, self.GRID):
                    pygame.draw.line(surf, color, (x, 0), (x, r.h), 1)
                for y in range(0, r.h, self.GRID):
                    pygame.draw.line(surf, color, (0, y), (r.w, y), 1)
            self._bg_cache = surf
        return self._bg_cache

    # -- actions -----------------------------------------------------------

    def _select_color(self, i):
        self.color_idx = i

    def _select_thickness(self, i):
        self.thickness_idx = i

    def _end_stroke(self):
        if self.drawing:
            self.canvas.end_stroke()
            self.drawing = False

    def _undo(self):
        self.pen_down = False
        self._end_stroke()
        if not self.canvas.undo():
            self.flash("Nothing to undo")

    def _clear(self):
        now = time.time()
        if now < self._clear_armed_until:          # second click: confirm
            self.pen_down = False
            self._end_stroke()
            self.canvas.clear()
            self._clear_armed_until = 0.0
            self.btn_clear.set_label("Clear")
            self.flash("Board cleared")
        else:
            self._clear_armed_until = now + 3.0
            self.btn_clear.set_label("Sure?")
            self.flash("Click Clear again to erase everything", 3.0)

    def _export(self):
        out_dir = Path(self.app.settings.get("export_dir", "output"))
        fname = f"whiteboard_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path = out_dir / fname
        # Composite: board background + strokes.
        img = self._background().copy()
        img.blit(self.canvas.to_surface(), (0, 0))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(img, str(path))
            self.flash(f"Saved {path}")
        except Exception as exc:  # noqa: BLE001
            logger.error("Export failed: %s", exc)
            self.flash("Save failed -- see log")

    # -- interaction -------------------------------------------------------

    def on_body_click(self, pos):
        """Left click on the board toggles the pen."""
        if not self.canvas_rect.collidepoint(pos):
            return False
        self.pen_down = not self.pen_down
        if not self.pen_down:
            self._end_stroke()
        return True

    def on_right_click(self, pos):
        self._undo()
        return True

    # -- per-frame ---------------------------------------------------------

    def update(self, dt):
        super().update(dt)
        if self._clear_armed_until and time.time() >= self._clear_armed_until:
            self._clear_armed_until = 0.0
            self.btn_clear.set_label("Clear")

        for i, b in enumerate(self.color_buttons):
            b.selected = (i == self.color_idx)
        for i, b in enumerate(self.thick_buttons):
            b.selected = (i == self.thickness_idx)

        pointer = self.app.pointer_pos
        visible = self.app.pointer_visible and pointer is not None
        on_board = visible and self.canvas_rect.collidepoint(pointer)

        # Leaving the board (or losing the marker) lifts the pen, so ink
        # never appears unexpectedly when the pointer comes back.
        if self.pen_down and not on_board:
            self.pen_down = False
        if not self.pen_down:
            self._end_stroke()
            return

        local = (pointer[0] - self.canvas_rect.x,
                 pointer[1] - self.canvas_rect.y)
        if not self.drawing:
            self.canvas.begin_stroke(local, self.pen_colors[self.color_idx],
                                     self.thicknesses[self.thickness_idx])
            self.drawing = True
        else:
            self.canvas.extend_stroke(local)

    # -- rendering ---------------------------------------------------------

    def draw_background(self, s):
        s.fill(COLORS["bg"])
        s.blit(self._background(), self.canvas_rect.topleft)

    def draw_body(self, s):
        s.blit(self.canvas.to_surface(), self.canvas_rect.topleft)
        # Preview of the pen tip at the pointer (colour + thickness).
        p = self.app.pointer_pos
        if self.app.pointer_visible and p is not None \
                and self.canvas_rect.collidepoint(p):
            rgb = tuple(self.pen_colors[self.color_idx][:3])
            r = max(2, self.thicknesses[self.thickness_idx] // 2)
            pygame.draw.circle(s, rgb, (int(p[0]), int(p[1])), r)

    def draw_header(self, s):
        super().draw_header(s)
        # Pen state pill, left of the Home button.
        text = "PEN DOWN" if self.pen_down else "PEN UP"
        color = COLORS["success"] if self.pen_down else COLORS["panel_alt"]
        fg = COLORS["bg"] if self.pen_down else COLORS["text_dim"]
        t = FONT_MB.render(text, True, fg)
        pill = pygame.Rect(0, 0, t.get_width() + 36, 38)
        pill.midright = (self.btn_home.rect.left - 16, self.header_rect.centery)
        pygame.draw.rect(s, color, pill, border_radius=19)
        s.blit(t, t.get_rect(center=pill.center))
