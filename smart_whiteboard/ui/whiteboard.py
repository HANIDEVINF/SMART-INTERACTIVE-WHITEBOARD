"""The interactive whiteboard: the painting canvas widget and the page that hosts it.

WhiteboardCanvas knows nothing about the mouse *or* the camera: both feed it through the same
three methods in **board coordinates** (pointer_down / pointer_move / pointer_up). In Phase 3-5
the tracked pointer (after the homography) will simply call these methods too.
"""
from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QMessageBox, QVBoxLayout,
                               QWidget)

from core.coordinate_mapping import fit_board_in_canvas
from core.interaction import Command, InteractionEngine, Mode
from core.lesson import Lesson, LessonSession, lesson_nav_hit, lesson_nav_slots
from core.menu_model import BACK_ID, MenuModel, build_menu
from core.view_transform import ViewTransform
from core.settings import DATA_DIR, Settings
from core.tracker import TRACKING
from tools.drawing import DrawingEngine, Tool
from tools.image_tools import IMAGE_EXTENSIONS, IMAGE_FILTER, imread_unicode
from ui.pointer_menu import Ripple, paint_hud, paint_lesson_bar, paint_menu, paint_ripples
from ui.styles import AMBER, GREEN, INK_COLORS, ROSE
from ui.toolbar import ActionBar, StyleBar, ToolRail

SHAPE_TOOLS = (Tool.LINE, Tool.RECT, Tool.CIRCLE)
ERASER_FACTOR = 3.0   # eraser diameter = thickness * 3 + 6 px
BOARD_MARGIN = 10


class WhiteboardCanvas(QWidget):
    """Paints the engine's composite image, live shape previews and the pointer overlay."""

    historyChanged = Signal()
    textRequested = Signal(float, float)           # board coordinates of the click
    pointerMoved = Signal(float, float, bool)      # board x, y, inside the board
    menuClicked = Signal(str)                      # mouse click on the on-board menu ('' = on the panel, no item)
    rightClicked = Signal()                        # mouse right button = remote 'Previous'
    viewChanged = Signal()                         # zoom / pan changed

    def __init__(self, engine: DrawingEngine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.tool = Tool.PEN
        self.color = QColor("#1F2937")
        self.thickness = 6

        self._drawing = False
        self._shape_start: tuple[float, float] | None = None
        self._shape_cur: tuple[float, float] | None = None
        self._hover: tuple[float, float] | None = None

        # Tracked-pointer overlay (driven by the camera pipeline in later phases)
        self.pointer_pos: tuple[float, float] | None = None
        self.pointer_state = "lost"        # "tracking" | "holding" | "lost"
        self.pointer_visible = True
        self.tracking_badge: tuple[str, str] | None = None   # (state, text) shown on the board while tracking

        # image viewer: zoom / pan of the content (see core/view_transform.py)
        self.view = ViewTransform(engine.width, engine.height)
        self.pan_mode = False
        self._pan_last: tuple[float, float] | None = None
        self._mouse_pan = False

        # interaction overlay (Phase 5): on-board menu, click ripples, mode HUD
        self.menu: MenuModel | None = None
        self.menu_hover: str | None = None
        self.menu_focus: str | None = None          # keyboard focus highlight (None = not using the keyboard)
        self.lesson_label: str | None = None        # "Page 2 / 7" while a lesson is presented (None = no lesson)
        self.lesson_can_prev = False
        self.lesson_can_next = False
        self.dwell_target: str | None = None
        self.dwell_progress = 0.0
        self.ripples: list[Ripple] = []
        self.mode_label = "Navigation"
        self.hud_pen_down = False
        self.hud_source = "mouse"
        self.show_hud = True
        self.show_ripples = True
        self._menu_press = False
        self._ripple_timer = QTimer(self)
        self._ripple_timer.setInterval(30)
        self._ripple_timer.timeout.connect(self._tick_ripples)

        self.setMouseTracking(True)
        self.setMinimumSize(480, 300)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    # ------------------------------------------------------------------ geometry
    def board_rect(self) -> QRectF:
        """Where the board is drawn in this widget (single source of truth: core.coordinate_mapping)."""
        x, y, w, h = fit_board_in_canvas(self.engine.size, (self.width(), self.height()), BOARD_MARGIN)
        return QRectF(x, y, w, h)

    def scale(self) -> float:
        return self.board_rect().width() / self.engine.width

    def widget_to_board(self, pos: QPointF) -> tuple[float, float]:
        r = self.board_rect()
        s = r.width() / self.engine.width
        return (pos.x() - r.x()) / s, (pos.y() - r.y()) / s

    def board_to_widget(self, x: float, y: float) -> QPointF:
        r = self.board_rect()
        s = r.width() / self.engine.width
        return QPointF(r.x() + x * s, r.y() + y * s)

    def _inside(self, x: float, y: float) -> bool:
        return 0 <= x < self.engine.width and 0 <= y < self.engine.height

    def _clamp(self, x: float, y: float) -> tuple[float, float]:
        return (min(max(x, 0.0), self.engine.width - 1.0), min(max(y, 0.0), self.engine.height - 1.0))

    # ------------------------------------------------------------------- state
    def eraser_width(self) -> float:
        return self.thickness * ERASER_FACTOR + 6

    def set_tool(self, tool: Tool) -> None:
        self.cancel_in_progress()
        self.tool = tool
        self.update()

    def set_color(self, color: QColor) -> None:
        self.color = color
        self.update()

    def set_thickness(self, value: int) -> None:
        self.thickness = int(value)
        self.update()

    def color_bgr(self) -> tuple[int, int, int]:
        return self.color.blue(), self.color.green(), self.color.red()

    def cancel_in_progress(self) -> bool:
        """Abort a running stroke/shape. Returns True when something was cancelled."""
        had = self._drawing or self._shape_start is not None
        self._pan_last = None
        self._mouse_pan = False
        if self._drawing:
            self.engine.cancel_action()
            self.engine.take_dirty()
        self._drawing = False
        self._shape_start = self._shape_cur = None
        if had:
            self.update()
        return had

    # --------------------------------------------- pointer API (mouse AND camera)
    def pointer_down(self, x: float, y: float) -> None:
        """Pointer pressed at board (screen) coordinates; drawn at the matching content position."""
        if self.pan_mode:
            self._pan_last = (x, y)
            return
        self._draw_down(*self.view.to_content(x, y))

    def pointer_move(self, x: float, y: float) -> None:
        if self._pan_last is not None:
            self.view.pan_by(x - self._pan_last[0], y - self._pan_last[1])
            self._pan_last = (x, y)
            self._view_changed()
            return
        self._draw_move(*self.view.to_content(x, y))

    def pointer_up(self, x: float, y: float) -> None:
        if self._pan_last is not None:
            self._pan_last = None
            return
        self._draw_up(*self.view.to_content(x, y))

    def _draw_down(self, x: float, y: float) -> None:
        if not self._inside(x, y) and self.tool in (Tool.PEN, Tool.ERASER, Tool.TEXT):
            return
        x, y = self._clamp(x, y)
        if self.tool in (Tool.PEN, Tool.ERASER):
            width = self.eraser_width() if self.tool == Tool.ERASER else self.thickness
            box = self.engine.begin_stroke(self.tool, self.color_bgr(), width, (x, y))
            self._drawing = True
            self._repaint_board_rect(box)
        elif self.tool in SHAPE_TOOLS:
            self._shape_start = self._shape_cur = (x, y)
            self.update()
        elif self.tool == Tool.TEXT:
            self.textRequested.emit(x, y)

    def _draw_move(self, x: float, y: float) -> None:
        if self._drawing:
            self._repaint_board_rect(self.engine.stroke_to(self._clamp(x, y)))
        elif self._shape_start is not None:
            self._shape_cur = self._clamp(x, y)
            self.update()

    def _draw_up(self, x: float, y: float) -> None:
        if self._drawing:
            self._repaint_board_rect(self.engine.stroke_to(self._clamp(x, y)))
            self._repaint_board_rect(self.engine.end_stroke())
            self._drawing = False
            self.historyChanged.emit()
        elif self._shape_start is not None:
            start, end = self._shape_start, self._clamp(x, y)
            self._shape_start = self._shape_cur = None
            if math.dist(start, end) >= 2.0:
                box = self._commit_shape(start, end)
                self._repaint_board_rect(box)
                self.historyChanged.emit()
            self.update()

    def _commit_shape(self, start, end):
        color, width = self.color_bgr(), self.thickness
        if self.tool == Tool.LINE:
            return self.engine.draw_line(start, end, color, width)
        if self.tool == Tool.RECT:
            return self.engine.draw_rect(start, end, color, width)
        return self.engine.draw_circle(start, math.dist(start, end), color, width)

    # ------------------------------------------------------------- tracked pointer
    def set_tracked_pointer(self, x: float | None, y: float | None, state: str = "tracking") -> None:
        """Update the on-board pointer marker (board coordinates). None = detection lost."""
        self.pointer_pos = None if x is None or y is None else (x, y)
        self.pointer_state = state if self.pointer_pos else "lost"
        self.update()

    # -------------------------------------------------------------------- Qt events
    def add_ripple(self, x: float, y: float, kind: str) -> None:
        if not self.show_ripples:
            return
        self.ripples.append(Ripple(x, y, kind))
        self._ripple_timer.start()
        self.update()

    def _tick_ripples(self) -> None:
        now = time.monotonic()
        self.ripples = [r for r in self.ripples if r.alive(now)]
        if not self.ripples:
            self._ripple_timer.stop()
        self.update()

    def _nav_hit(self, pos) -> str | None:
        if self.lesson_label is None:
            return None
        x, y = self.widget_to_board(pos)
        return lesson_nav_hit(x, y, self.engine.width, self.engine.height)

    def _over_menu(self, pos) -> bool:
        if self.menu is None or not self.menu.is_open:
            return False
        x, y = self.widget_to_board(pos)
        return self.menu.over_panel(x, y, self.engine.width, self.engine.height)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            nav = self._nav_hit(e.position())
            if nav is not None:
                self._menu_press = True
                self.menuClicked.emit(nav)
                return
            if self._over_menu(e.position()):                     # the menu sits above the drawing
                self._menu_press = True
                x, y = self.widget_to_board(e.position())
                self.menuClicked.emit(self.menu.hit(x, y, self.engine.width, self.engine.height) or "")
                return
            self.pointer_down(*self.widget_to_board(e.position()))
        elif e.button() == Qt.MouseButton.MiddleButton:
            self._mouse_pan = True
            self._pan_last = self.widget_to_board(e.position())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif e.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        x, y = self.widget_to_board(e.position())
        self._hover = (x, y)
        self.pointerMoved.emit(x, y, self._inside(x, y))
        if self._mouse_pan and self._pan_last is not None:
            self.pointer_move(x, y)
        elif e.buttons() & Qt.MouseButton.LeftButton and not self._menu_press:
            self.pointer_move(x, y)
        else:
            self.update()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.MiddleButton and self._mouse_pan:
            self._mouse_pan = False
            self._pan_last = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self.pan_mode else Qt.CursorShape.CrossCursor)
            return
        if e.button() == Qt.MouseButton.LeftButton and self._menu_press:
            self._menu_press = False
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self.pointer_up(*self.widget_to_board(e.position()))

    def leaveEvent(self, _e) -> None:  # noqa: N802
        self._hover = None
        self.pointerMoved.emit(-1.0, -1.0, False)
        self.update()

    # ------------------------------------------------------------------ zoom / pan
    def _view_changed(self) -> None:
        self.update()
        self.viewChanged.emit()

    def zoom_in(self, ax: float | None = None, ay: float | None = None) -> None:
        self.view.zoom_in(ax, ay)
        self._view_changed()

    def zoom_out(self, ax: float | None = None, ay: float | None = None) -> None:
        self.view.zoom_out(ax, ay)
        self._view_changed()

    def fit_view(self) -> None:
        self.view.reset()
        self._view_changed()

    def move_view(self, fx: float, fy: float) -> None:
        self.view.move_view(fx, fy)
        self._view_changed()

    def set_pan_mode(self, on: bool) -> None:
        self.cancel_in_progress()
        self.pan_mode = bool(on)
        self.setCursor(Qt.CursorShape.OpenHandCursor if on else Qt.CursorShape.CrossCursor)
        self.viewChanged.emit()
        self.update()

    def wheelEvent(self, e) -> None:  # noqa: N802
        steps = e.angleDelta().y() / 120.0
        if steps:
            ax, ay = self.widget_to_board(e.position())
            self.view.zoom_at(1.25 ** steps, ax, ay)
            self._view_changed()
        e.accept()

    def _repaint_board_rect(self, box) -> None:
        if box is None:
            return
        if not self.view.is_identity:             # content coordinates differ from screen coordinates
            self.update()
            return
        x0, y0, x1, y1 = box
        a, b = self.board_to_widget(x0, y0), self.board_to_widget(x1, y1)
        self.update(QRectF(a, b).toAlignedRect().adjusted(-3, -3, 3, 3))

    # --------------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.board_rect()

        # soft drop shadow
        for i, alpha in enumerate((10, 14, 18, 22)):
            grow = (4 - i) * 3
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(20, 24, 60, alpha))
            p.drawRoundedRect(rect.adjusted(-grow, -grow + 3, grow, grow + 3), 18 + grow, 18 + grow)

        clip = QPainterPath()
        clip.addRoundedRect(rect, 14, 14)
        p.save()
        p.setClipPath(clip)
        self._paint_content(p, rect)
        p.restore()

        self._paint_hover_cursor(p)
        if self.menu is not None and self.menu.is_open:
            p.save()
            p.translate(rect.topLeft())
            s = self.scale()
            p.scale(s, s)
            paint_menu(p, self.menu, self.engine.width, self.engine.height, self.menu_hover, self.menu_focus,
                       self.dwell_target, self.dwell_progress)
            p.restore()
        if self.lesson_label is not None:
            p.save()
            p.translate(rect.topLeft())
            s = self.scale()
            p.scale(s, s)
            paint_lesson_bar(p, lesson_nav_slots(self.engine.width, self.engine.height), self.lesson_label,
                             self.menu_hover, self.dwell_target, self.dwell_progress, self.lesson_can_prev,
                             self.lesson_can_next)
            p.restore()
        self._paint_tracked_pointer(p)
        if self.ripples:
            p.save()
            p.translate(rect.topLeft())
            s = self.scale()
            p.scale(s, s)
            paint_ripples(p, self.ripples)
            p.restore()
        self._paint_tracking_badge(p, rect)
        if self.show_hud:
            paint_hud(p, rect, self.mode_label, self.hud_pen_down, self.hud_source,
                      "" if self.view.is_identity else f"zoom {self.view.percent}%" + ("  PAN" if self.pan_mode else ""))

    def _paint_content(self, p: QPainter, rect: QRectF) -> None:
        """Background + drawing (+ live shape preview), through the zoom/pan transform."""
        eng, v = self.engine, self.view
        w, h = eng.size
        s = rect.width() / w
        if v.is_identity:
            img = QImage(eng.composite.data, w, h, w * 3, QImage.Format.Format_BGR888)
            p.drawImage(rect, img)
        else:
            p.save()
            p.translate(rect.topLeft())
            p.scale(s, s)
            p.translate(v.ox, v.oy)
            p.scale(v.zoom, v.zoom)
            p.fillRect(QRectF(0, 0, w, h), QColor(eng.paper_bgr[2], eng.paper_bgr[1], eng.paper_bgr[0]))
            if eng.source is not None and eng.placement is not None:       # crisp: the original image, not the 1600x900 copy
                sh, sw = eng.source.shape[:2]
                src = QImage(eng.source.data, sw, sh, eng.source.strides[0], QImage.Format.Format_BGR888)
                x, y, pw, ph = eng.placement
                p.drawImage(QRectF(x, y, pw, ph), src)
            ink = QImage(eng.ink.data, w, h, w * 4, QImage.Format.Format_ARGB32)
            p.drawImage(QRectF(0, 0, w, h), ink)
            p.restore()
        if self._shape_start and self._shape_cur:      # live preview (the real shape is committed by NumPy on release)
            self._paint_shape_preview(p, rect)

    def _paint_tracking_badge(self, p: QPainter, rect: QRectF) -> None:
        """Small pill in the board's top-left corner: pointer lost / outside / not calibrated ..."""
        if self.tracking_badge is None or self.tracking_badge[0] == "ok":
            return
        state, text = self.tracking_badge
        color = QColor(ROSE if state == "error" else AMBER)
        font = p.font()
        font.setPointSize(10)
        font.setBold(True)
        p.setFont(font)
        w = p.fontMetrics().horizontalAdvance(text) + 26
        pill = QRectF(rect.x() + 14, rect.y() + 14, w, 28)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 230))
        p.drawRoundedRect(pill, 14, 14)
        p.setPen(QColor("white"))
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_shape_preview(self, p: QPainter, rect: QRectF) -> None:
        s = rect.width() / self.engine.width
        p.save()
        p.translate(rect.topLeft())
        p.scale(s, s)
        p.translate(self.view.ox, self.view.oy)
        p.scale(self.view.zoom, self.view.zoom)
        pen = QPen(self.color, max(self.thickness, 1), Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        (x0, y0), (x1, y1) = self._shape_start, self._shape_cur
        if self.tool == Tool.LINE:
            p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        elif self.tool == Tool.RECT:
            p.drawRect(QRectF(QPointF(x0, y0), QPointF(x1, y1)).normalized())
        else:
            r = math.dist((x0, y0), (x1, y1))
            p.drawEllipse(QPointF(x0, y0), r, r)
        p.restore()

    def _paint_hover_cursor(self, p: QPainter) -> None:
        if self._hover is None or not self._inside(*self._hover):
            return
        if self.menu is not None and self.menu.is_open and \
                self.menu.over_panel(*self._hover, self.engine.width, self.engine.height):
            return
        if self.tool in (Tool.PEN, Tool.ERASER):
            diameter = self.eraser_width() if self.tool == Tool.ERASER else self.thickness
            r = max(diameter * self.scale() * self.view.zoom / 2, 2.0)
            c = self.board_to_widget(*self._hover)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 200), 3))
            p.drawEllipse(c, r, r)
            p.setPen(QPen(QColor(30, 34, 70, 200), 1.2))
            p.drawEllipse(c, r, r)

    def _paint_tracked_pointer(self, p: QPainter) -> None:
        if not self.pointer_visible or self.pointer_pos is None:
            return
        c = self.board_to_widget(*self.pointer_pos)
        color = QColor(GREEN if self.pointer_state == "tracking" else AMBER)
        p.setPen(QPen(color, 2.5))
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 50))
        p.drawEllipse(c, 16, 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(c, 4.5, 4.5)


class WhiteboardPage(QWidget):
    """Whiteboard canvas + toolbars, file operations, shortcuts and confirmation dialogs."""

    homeRequested = Signal()
    fullscreenRequested = Signal()
    message = Signal(str, str)      # (text, kind)  -> shown as a toast by the main window
    recentChanged = Signal()
    trackingToggled = Signal(bool)  # the user switched camera pointer tracking on/off
    navigateRequested = Signal(str)  # menu asked for another page: home | calibration | settings | remote
    modeChanged = Signal(str)
    lessonExited = Signal()

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self.settings = settings
        self.engine = DrawingEngine(
            int(settings.get("board.width", 1600)), int(settings.get("board.height", 900)),
            tuple(settings.get("board.paper_color_rgb", (250, 249, 246))))
        self.canvas = WhiteboardCanvas(self.engine)
        self.action_bar = ActionBar()
        self.rail = ToolRail()
        self.style_bar = StyleBar()
        self.action_bar.info.setText(f"{self.engine.width} x {self.engine.height} px board")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)
        outer.addWidget(self.action_bar)
        middle = QHBoxLayout()
        middle.setSpacing(12)
        middle.addWidget(self.rail, 0, Qt.AlignmentFlag.AlignTop)
        middle.addWidget(self.canvas, 1)
        outer.addLayout(middle, 1)
        outer.addWidget(self.style_bar)

        # wiring
        self.rail.toolSelected.connect(self.select_tool)
        self.style_bar.colorChanged.connect(self.canvas.set_color)
        self.style_bar.thicknessChanged.connect(self._on_thickness)
        self.action_bar.homeClicked.connect(self.homeRequested)
        self.action_bar.undoClicked.connect(self.undo)
        self.action_bar.redoClicked.connect(self.redo)
        self.action_bar.clearClicked.connect(self.confirm_clear)
        self.action_bar.openClicked.connect(self.open_image_dialog)
        self.action_bar.saveClicked.connect(self.save_png_dialog)
        self.action_bar.fullscreenClicked.connect(self.fullscreenRequested)
        self.canvas.historyChanged.connect(self._sync_history)
        self.canvas.textRequested.connect(self._add_text)
        self.canvas.pointerMoved.connect(self._on_pointer_moved)
        self.action_bar.trackToggled.connect(self._on_track_toggled)
        self.style_bar.zoomInClicked.connect(lambda: self.canvas.zoom_in())
        self.style_bar.zoomOutClicked.connect(lambda: self.canvas.zoom_out())
        self.style_bar.fitClicked.connect(self.canvas.fit_view)
        self.style_bar.panToggled.connect(self.set_pan_mode)
        self.canvas.viewChanged.connect(self._on_view_changed)
        self.canvas.pointer_visible = bool(settings.get("pointer.visible", True))

        # ---- Phase 5: interaction modes, on-board menu, remote clicks -------------------------------
        self.menu = MenuModel(build_menu(INK_COLORS))
        self.canvas.menu = self.menu
        self.interaction = InteractionEngine(int(settings.get("interaction.dwell_ms", 1200)))
        self.remote = None
        self.session: LessonSession | None = None
        self._page_cache: dict[int, object] = {}
        self._fullscreen = False
        self._kbd_focus = False
        self._tick = QTimer(self)                      # keeps dwell running while the pointer rests
        self._tick.setInterval(40)
        self._tick.timeout.connect(self._feed_pointer)
        self.action_bar.modeSelected.connect(self.set_mode)
        self.action_bar.menuClicked.connect(self.toggle_menu)
        self.canvas.menuClicked.connect(self._on_menu_mouse)
        self.canvas.rightClicked.connect(self.on_remote_previous)

        self._install_shortcuts()
        self._restore_pen_settings()
        self._sync_history()
        self.apply_interface()
        saved_mode = str(settings.get("interaction.mode", "navigation"))
        self.set_mode(saved_mode if saved_mode in {m.value for m in Mode} else "navigation", announce=False)

    # ----------------------------------------------------------------- shortcuts
    def _install_shortcuts(self) -> None:
        def add(seq: str, fn) -> None:
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)

        add("Ctrl+Z", self.undo)
        add("Ctrl+Y", self.redo)
        add("Ctrl+Shift+Z", self.redo)
        add("Ctrl+S", self.save_png_dialog)
        add("Ctrl+O", self.open_image_dialog)
        add("Ctrl+Del", self.confirm_clear)
        add("Ctrl+Shift+R", self.confirm_reset)
        for key, tool in (("P", Tool.PEN), ("E", Tool.ERASER), ("L", Tool.LINE),
                          ("R", Tool.RECT), ("C", Tool.CIRCLE), ("T", Tool.TEXT)):
            add(key, lambda t=tool: self.select_tool(t.value))
        add("K", lambda: self.action_bar.track_btn.toggle())
        add("M", self.toggle_menu)
        for seq in ("+", "="):
            add(seq, lambda: self.canvas.zoom_in())
        add("-", lambda: self.canvas.zoom_out())
        add("0", self.canvas.fit_view)
        for seq, fx, fy in (("Ctrl+Left", -0.25, 0), ("Ctrl+Right", 0.25, 0), ("Ctrl+Up", 0, -0.25),
                            ("Ctrl+Down", 0, 0.25)):
            add(seq, lambda fx=fx, fy=fy: self.canvas.move_view(fx, fy))
        for key, mode in (("1", Mode.NAVIGATION), ("2", Mode.DRAWING), ("3", Mode.SELECTION)):
            add(key, lambda m=mode: self.set_mode(m.value))
        add("Up", lambda: self._menu_key_move(-1))
        add("Down", lambda: self._menu_key_move(1))
        add("Return", self._menu_key_activate)
        add("Enter", self._menu_key_activate)
        add("Backspace", lambda: self._menu_back() if self.menu.is_open else None)
        add("[", lambda: self.style_bar.set_thickness(self.canvas.thickness - 1))
        add("]", lambda: self.style_bar.set_thickness(self.canvas.thickness + 1))

    # ------------------------------------------------------------------ pen state
    def _restore_pen_settings(self) -> None:
        color = QColor(self.settings.get("pen.color", "#1F2937"))
        thickness = int(self.settings.get("pen.thickness", 6))
        tool = self.settings.get("pen.tool", "pen")
        if not color.isValid():
            color = QColor("#1F2937")
        self.canvas.set_color(color)
        self.style_bar.set_color(color)
        self.style_bar.set_thickness(max(1, min(40, thickness)))
        self.select_tool(tool if tool in {t.value for t in Tool} else "pen")

    def save_pen_settings(self) -> None:
        self.settings.set("pen.color", self.canvas.color.name())
        self.settings.set("pen.thickness", self.canvas.thickness)
        self.settings.set("pen.tool", self.canvas.tool.value)

    def select_tool(self, tool_name: str) -> None:
        tool = Tool(tool_name)
        self.canvas.set_tool(tool)
        self.rail.set_tool(tool.value)
        self.canvas.setCursor(Qt.CursorShape.IBeamCursor if tool == Tool.TEXT
                              else Qt.CursorShape.CrossCursor)

    def set_pan_mode(self, on: bool) -> None:
        self.canvas.set_pan_mode(on)
        self.style_bar.set_pan_checked(on)
        self._sync_menu()

    def _on_view_changed(self) -> None:
        self.style_bar.set_zoom_text(f"{self.canvas.view.percent}%")
        self.style_bar.set_pan_checked(self.canvas.pan_mode)

    def _on_thickness(self, value: int) -> None:
        self.canvas.set_thickness(value)

    def _on_pointer_moved(self, x: float, y: float, inside: bool) -> None:
        self.style_bar.set_coords_text(f"x {x:.0f}   y {y:.0f}" if inside else "")
        self._feed_pointer()                       # the mouse is the pointer while camera tracking is off

    def cancel_in_progress(self) -> bool:
        return self.canvas.cancel_in_progress()

    # ------------------------------------------------------------- camera pointer
    @property
    def tracking_enabled(self) -> bool:
        return self.action_bar.track_btn.isChecked()

    def _on_track_toggled(self, on: bool) -> None:
        if not on:
            self.canvas.set_tracked_pointer(None, None)
            self.canvas.tracking_badge = None
            self.canvas.update()
            self._feed_pointer()                   # fall back to the mouse (lifts the pen if the camera held it)
        else:
            self.action_bar.set_track_status("warn", "Starting camera...")
        self.trackingToggled.emit(on)

    def set_pointer_visible(self, visible: bool) -> None:
        self.canvas.pointer_visible = bool(visible)
        self.canvas.update()

    def clear_tracking(self, text: str = "Camera off") -> None:
        """No vision data (camera stopped / signal lost): remove the pointer and say why."""
        if not self.tracking_enabled:
            return
        self.canvas.set_tracked_pointer(None, None)
        self._set_badge("error", text)
        self._feed_pointer()

    def _set_badge(self, state: str, text: str) -> None:
        self.action_bar.set_track_status(state, text)
        self.canvas.tracking_badge = (state, text)
        self.canvas.update()

    def show_vision_result(self, res) -> None:
        """Place the tracked pointer on the board from a VisionResult (board coordinates)."""
        if not self.tracking_enabled:
            return
        if res.calib_state == "none":
            self.canvas.set_tracked_pointer(None, None)
            self._set_badge("warn", "Not calibrated")
        elif res.calib_state == "mismatch":
            self.canvas.set_tracked_pointer(None, None)
            self._set_badge("error", "Recalibrate (camera changed)")
        elif res.board is None:
            self.canvas.set_tracked_pointer(None, None)
            self._set_badge("warn", "Pointer lost" if res.track.position is None else "Outside the board")
        else:
            live = res.track.state == TRACKING
            self.canvas.set_tracked_pointer(res.board.x, res.board.y, "tracking" if live else "holding")
            self._set_badge("ok" if live else "warn",
                            f"Tracking  {res.tracking_fps:.0f} fps" if live else "Searching...")
        self._feed_pointer()

    def set_fullscreen_state(self, on: bool) -> None:
        self._fullscreen = bool(on)
        self.action_bar.set_fullscreen(on)
        self._sync_menu()

    # ============================================================ Phase 5: interaction
    def set_remote(self, remote) -> None:
        """Connect the two-button remote: Next = left click, Previous = right click at the pointer position."""
        self.remote = remote
        remote.nextTriggered.connect(self.on_remote_next)
        remote.previousTriggered.connect(self.on_remote_previous)

    def apply_interface(self) -> None:
        """Read Settings > General > Interface (status pill, click rings, menu size)."""
        s = self.settings
        self.canvas.show_hud = bool(s.get("interface.hud", True))
        self.canvas.show_ripples = bool(s.get("interface.ripples", True))
        try:
            self.menu.scale = float(s.get("interface.menu_scale", 1.0))
        except (TypeError, ValueError):
            self.menu.scale = 1.0
        self.canvas.update()

    def set_dwell_ms(self, ms: int) -> None:
        self.interaction.set_dwell_ms(ms)
        self.settings.set("interaction.dwell_ms", int(ms))

    def set_mode(self, name: str, announce: bool = True) -> None:
        mode = Mode(name)
        self._run(self.interaction.set_mode(mode))
        self.action_bar.set_mode(mode.value)
        self.canvas.mode_label = mode.label
        self.settings.set("interaction.mode", mode.value)
        self.canvas.update()
        if mode is Mode.SELECTION:
            self._tick.start()
        else:
            self._tick.stop()
            self.canvas.dwell_target, self.canvas.dwell_progress = None, 0.0
        self._sync_menu()
        self.modeChanged.emit(mode.value)
        if announce:
            hints = {Mode.NAVIGATION: "Next = click on the menu item under the pointer",
                     Mode.DRAWING: "Next = pen down / up at the pointer",
                     Mode.SELECTION: "rest on a menu item to confirm it"}
            self.message.emit(f"{mode.label} mode - {hints[mode]}", "info")

    @property
    def mode(self) -> Mode:
        return self.interaction.mode

    def activate(self) -> None:
        """Page shown."""
        if self.interaction.mode is Mode.SELECTION:
            self._tick.start()
        self._sync_menu()

    def deactivate(self) -> None:
        """Page hidden: lift the pen, stop dwell."""
        self._run(self.interaction.release_all())
        self._tick.stop()

    # -- pointer source: camera when tracking, else the mouse ---------------------------------------------------
    def _pointer_sample(self) -> tuple[float, float, bool, str]:
        c = self.canvas
        if self.tracking_enabled:
            if c.pointer_pos is not None and c.pointer_state == "tracking":
                return c.pointer_pos[0], c.pointer_pos[1], True, "camera"
            return 0.0, 0.0, False, "camera"
        if c._hover is not None and c._inside(*c._hover):
            return c._hover[0], c._hover[1], True, "mouse"
        return 0.0, 0.0, False, "mouse"

    def _feed_pointer(self) -> None:
        x, y, valid, source = self._pointer_sample()
        hover = None
        if valid:
            if self.menu.is_open:
                hover = self.menu.hit(x, y, self.engine.width, self.engine.height)
            if hover is None and self.session is not None:
                hover = lesson_nav_hit(x, y, self.engine.width, self.engine.height)
        if hover is not None:
            self._kbd_focus = False
            self.canvas.menu_focus = None
        cmds = self.interaction.pointer(x, y, valid, time.monotonic() * 1000.0, hover)
        c = self.canvas
        shown = (hover, self.interaction.dwell.target if hover else None, round(self.interaction.dwell_progress, 2),
                 self.interaction.pen_down, source)
        before = (c.menu_hover, c.dwell_target, round(c.dwell_progress, 2), c.hud_pen_down, c.hud_source)
        c.menu_hover = hover
        c.dwell_target = self.interaction.dwell.target if hover else None
        c.dwell_progress = self.interaction.dwell_progress
        c.hud_source = source
        self._run(cmds)
        c.hud_pen_down = self.interaction.pen_down
        if before != (c.menu_hover, c.dwell_target, round(c.dwell_progress, 2), c.hud_pen_down, c.hud_source) \
                or before != shown:
            c.update()

    def _run(self, cmds: list[Command]) -> None:
        for cmd in cmds:
            if cmd.kind == "pen_down":
                self.canvas.pointer_down(cmd.x, cmd.y)
            elif cmd.kind == "pen_move":
                self.canvas.pointer_move(cmd.x, cmd.y)
            elif cmd.kind == "pen_up":
                self.canvas.pointer_up(cmd.x, cmd.y)
            elif cmd.kind == "activate" and cmd.target:
                self._menu_activate(cmd.target)
            elif cmd.kind == "back":
                self._menu_back()
        self.canvas.hud_pen_down = self.interaction.pen_down

    # -- remote buttons ------------------------------------------------------------------------------------------
    def on_remote_next(self) -> None:
        """Next = left click at the current pointer position."""
        self._feed_pointer()
        if not self.interaction.valid:
            self.message.emit("No pointer position - track the marker or move the mouse over the board", "warn")
            return
        self.canvas.add_ripple(self.interaction.x, self.interaction.y, "left")
        self._run(self.interaction.left_click())
        self._feed_pointer()

    def on_remote_previous(self) -> None:
        """Previous = right click: lifts the pen, else goes back one menu level / opens the menu."""
        self._feed_pointer()
        if self.interaction.valid:
            self.canvas.add_ripple(self.interaction.x, self.interaction.y, "right")
        self._run(self.interaction.right_click())
        self._feed_pointer()

    # -- teaching mode: present a lesson page by page -------------------------------------------------------
    @property
    def lesson_active(self) -> bool:
        return self.session is not None

    def start_lesson(self, lesson: Lesson, index: int = 0) -> None:
        """Show ``lesson`` page by page on the board; notes drawn on a page are kept while the lesson is open."""
        self._run(self.interaction.release_all())
        self.canvas.cancel_in_progress()
        self.canvas.set_pan_mode(False)
        self.engine.reset()
        self._page_cache.clear()
        self.session = LessonSession(lesson, index)
        self.menu.set_lesson_active(True)
        self.menu.close()
        self._apply_lesson_page()

    def _apply_lesson_page(self) -> None:
        from ui.lesson_render import render_page
        sess = self.session
        if sess is None:
            return
        img = self._page_cache.get(sess.index)
        if img is None:
            img = self._page_cache[sess.index] = render_page(sess.lesson, sess.index)
        self.engine.set_background(img)
        self.engine.set_ink(sess.ink_for_current())
        self.engine.clear_history()
        self.canvas.fit_view()
        self.canvas.lesson_label = sess.label
        self.canvas.lesson_can_prev = not sess.at_first
        self.canvas.lesson_can_next = not sess.at_last
        self._sync_history()
        self._sync_menu()
        self.canvas.update()

    def _lesson_go(self, move) -> None:
        sess = self.session
        if sess is None:
            return
        self._run(self.interaction.release_all()) if self.interaction.pen_down else None
        self.canvas.cancel_in_progress()
        sess.store_ink(self.engine.ink)
        if move(sess):
            self._apply_lesson_page()
            self.message.emit(f"{sess.label}  -  {sess.page.title}", "info")
        else:
            self.message.emit("This is the last page" if sess.at_last else "This is the first page", "info")

    def _lesson_action(self, name: str) -> None:
        sess = self.session
        if sess is None:
            return
        if name == "next":
            self._lesson_go(lambda s: s.next())
        elif name == "prev":
            self._lesson_go(lambda s: s.previous())
        elif name == "first":
            self._lesson_go(lambda s: s.go(0))
        elif name == "last":
            self._lesson_go(lambda s: s.go(s.count - 1))
        elif name == "clear":
            self.canvas.cancel_in_progress()
            self.engine.set_ink(None)
            self.engine.clear_history()
            sess.store_ink(self.engine.ink)
            self._sync_history()
            self.canvas.update()
            self.message.emit("Notes on this page erased", "info")
        elif name == "exit":
            self.exit_lesson()
            self.lessonExited.emit()

    def exit_lesson(self) -> None:
        """Leave the lesson: the board goes back to a blank page."""
        if self.session is None:
            return
        self._run(self.interaction.release_all())
        self.canvas.cancel_in_progress()
        self.session = None
        self._page_cache.clear()
        self.menu.set_lesson_active(False)
        self.canvas.lesson_label = None
        self.engine.reset()
        self.canvas.fit_view()
        self._sync_history()
        self._sync_menu()
        self.canvas.update()

    # -- menu ---------------------------------------------------------------------------------------------------
    def toggle_menu(self) -> None:
        self.menu.toggle()
        self._kbd_focus = False
        self._sync_menu()

    def close_menu(self) -> bool:
        """Close the menu if it is open (Esc). Returns True when it was open."""
        if self.menu.is_open:
            self.menu.close()
            self._sync_menu()
            return True
        return False

    def _menu_back(self) -> None:
        if self.menu.is_open:
            self.menu.back()
        else:
            self.menu.open()
        self._sync_menu()

    def _on_menu_mouse(self, item_id: str) -> None:
        if item_id:
            self._menu_activate(item_id)

    def _menu_key_move(self, delta: int) -> None:
        if not self.menu.is_open:
            return
        self._kbd_focus = True
        self.menu.move_focus(delta)
        self.canvas.menu_focus = self.menu.focused_id()
        self.canvas.update()

    def _menu_key_activate(self) -> None:
        if self.menu.is_open and (fid := self.menu.focused_id()):
            self._menu_activate(fid)

    def _menu_activate(self, item_id: str) -> None:
        if item_id in ("lesson.prev", "lesson.next"):                 # the always-visible page controls
            self.execute_action("lesson:" + item_id.split(".")[1])
            self.interaction.dwell.reset()
            self._sync_menu()
            return
        kind, action = self.menu.activate(item_id)
        if kind == "action" and action:
            self.execute_action(action)
        self.interaction.dwell.reset()
        self._sync_menu()

    def _refresh_flags(self) -> None:
        c = self.canvas
        f = {f"tool:{c.tool.value}": True, f"color:{c.color.name().upper()}": True,
             f"thickness:{c.thickness}": True, f"mode:{self.interaction.mode.value}": True,
             "tracking": self.tracking_enabled, "pan_mode": c.pan_mode, "pointer_visible": c.pointer_visible, "fullscreen": self._fullscreen}
        self.menu.flags = f

    def _sync_menu(self) -> None:
        self._refresh_flags()
        if self._kbd_focus and self.menu.is_open:
            n = len(self.menu.entries())
            self.menu.focus = min(self.menu.focus, max(n - 1, 0))
            self.canvas.menu_focus = self.menu.focused_id()
        else:
            self.canvas.menu_focus = None
        self.canvas.update()

    _CLOSE_AFTER = ("image.open", "board.", "nav:", "window.fullscreen", "mode:", "lesson:exit", "lesson:clear")

    def execute_action(self, action: str) -> None:
        """Run a menu action id (see core/menu_model.py)."""
        c = self.canvas
        if action == "menu.back":
            self.menu.back()
        elif action == "menu.close":
            self.menu.close()
        elif action.startswith("tool:"):
            self.select_tool(action[5:])
        elif action.startswith("color:"):
            color = QColor(action[6:])
            self.style_bar.set_color(color)
            c.set_color(color)
        elif action.startswith("thickness:"):
            arg = action[10:]
            value = c.thickness + (1 if arg == "+" else -1) * 2 if arg in ("+", "-") else int(arg)
            self.style_bar.set_thickness(max(1, min(40, value)))
            c.set_thickness(max(1, min(40, value)))
        elif action.startswith("lesson:"):
            self._lesson_action(action[7:])
        elif action.startswith("view:"):
            arg = action[5:]
            if arg == "in":
                c.zoom_in()
            elif arg == "out":
                c.zoom_out()
            elif arg == "fit":
                c.fit_view()
            elif arg == "pan":
                self.set_pan_mode(not c.pan_mode)
            else:
                c.move_view(*{"left": (-0.25, 0), "right": (0.25, 0), "up": (0, -0.25), "down": (0, 0.25)}[arg])
        elif action == "undo":
            self.undo()
        elif action == "redo":
            self.redo()
        elif action == "board.clear":
            c.cancel_in_progress()
            self.engine.clear_ink()
            c.update()
            self._sync_history()
            self.message.emit("Board cleared (Undo restores the drawing)", "info")
        elif action == "board.reset":
            self.reset()
            self.message.emit("Whiteboard reset", "info")
        elif action in ("image.open", "image.remove") and self.session is not None:
            self.message.emit("Leave the lesson first - its page is the board's image", "warn")
        elif action == "image.open":
            self.menu.close()
            self.open_image_dialog()
        elif action == "image.remove":
            if self.engine.has_background:
                self.engine.set_background(None)
                c.update()
                self.message.emit("Image removed", "info")
            else:
                self.message.emit("There is no image on the board", "info")
        elif action == "board.save":
            self.menu.close()
            self.save_png_dialog()
        elif action == "window.fullscreen":
            self.fullscreenRequested.emit()
        elif action == "pointer.toggle":
            self.set_pointer_visible(not c.pointer_visible)
            self.settings.set("pointer.visible", c.pointer_visible)
        elif action == "track.toggle":
            self.action_bar.track_btn.toggle()
        elif action.startswith("mode:"):
            self.set_mode(action[5:])
        elif action.startswith("nav:"):
            self.menu.close()
            self.navigateRequested.emit(action[4:])
        if action.startswith(self._CLOSE_AFTER):
            self.menu.close()

    # -------------------------------------------------------------------- history
    def _sync_history(self) -> None:
        self.action_bar.set_history_state(self.engine.can_undo, self.engine.can_redo)

    def undo(self) -> None:
        self.canvas.cancel_in_progress()
        if self.engine.undo() is not None:
            self.canvas.update()
        self._sync_history()

    def redo(self) -> None:
        self.canvas.cancel_in_progress()
        if self.engine.redo() is not None:
            self.canvas.update()
        self._sync_history()

    # ------------------------------------------------------------------ operations
    def _add_text(self, x: float, y: float) -> None:
        text, ok = QInputDialog.getMultiLineText(self, "Text annotation", "Text to place on the board:")
        if ok and text.strip():
            size = 14 + self.canvas.thickness * 3
            self.engine.draw_text((x, y), text, self.canvas.color_bgr(), size)
            self.canvas.update()
            self._sync_history()

    def confirm_clear(self) -> None:
        if not self.engine.has_ink and not self.engine.has_background:
            self.message.emit("The board is already empty", "info")
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Clear the board")
        box.setText("Clear the board?")
        box.setInformativeText("Drawings can be restored with Undo. A removed background image cannot.")
        clear_btn = box.addButton("Clear drawing", QMessageBox.ButtonRole.AcceptRole)
        all_btn = box.addButton("Clear drawing and image", QMessageBox.ButtonRole.DestructiveRole) \
            if self.engine.has_background else None
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(clear_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is clear_btn or (all_btn is not None and clicked is all_btn):
            self.canvas.cancel_in_progress()
            self.engine.clear_ink()
            if clicked is all_btn:
                self.engine.set_background(None)
            self.canvas.update()
            self._sync_history()
            self.message.emit("Board cleared", "info")

    def confirm_reset(self) -> None:
        answer = QMessageBox.question(
            self, "Reset whiteboard",
            "Reset the whiteboard to a blank state?\nDrawing, image and undo history will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            self.reset()
            self.message.emit("Whiteboard reset", "info")

    def reset(self) -> None:
        self.canvas.cancel_in_progress()
        if self.session is not None:
            self.exit_lesson()
        self.engine.reset()
        self.canvas.fit_view()
        self.canvas.set_pan_mode(False)
        self.canvas.update()
        self._sync_history()

    def open_image_dialog(self) -> bool:
        start = str(Path(self.settings.recent_files()[0]).parent) if self.settings.recent_files() else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Open an image or saved drawing", start, IMAGE_FILTER)
        return self.open_path(path) if path else False

    def open_path(self, path: str) -> bool:
        """Show an image behind the drawing layer. Reports problems instead of raising."""
        p = Path(path)
        if p.suffix.lower() not in IMAGE_EXTENSIONS:
            QMessageBox.warning(self, "Unsupported file",
                                f"'{p.name}' is not supported.\nUse PNG, JPG, JPEG or BMP.")
            return False
        img = imread_unicode(p)
        if img is None:
            QMessageBox.warning(self, "Cannot open image",
                                f"'{p.name}' could not be read.\nThe file is missing, empty or corrupted.")
            return False
        self.canvas.cancel_in_progress()
        self.engine.set_background(img)
        self.canvas.fit_view()                      # a new image always starts fully visible
        self.canvas.update()
        self.settings.add_recent(p)
        self.recentChanged.emit()
        self.message.emit(f"Opened {p.name}", "success")
        return True

    def save_png_dialog(self) -> bool:
        folder = DATA_DIR / "saved_drawings"
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            folder = Path.home()
        default = folder / f"board_{datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(self, "Save the board as PNG", str(default), "PNG image (*.png)")
        if not path:
            return False
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            self.engine.export_png(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Save failed", f"The drawing could not be saved:\n{exc}")
            return False
        self.settings.add_recent(path)
        self.recentChanged.emit()
        self.message.emit(f"Saved {Path(path).name}", "success")
        return True
