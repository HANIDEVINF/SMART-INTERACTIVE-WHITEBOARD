"""Whiteboard chrome: tool rail (left), action bar (top) and style bar (bottom)."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QButtonGroup, QColorDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QSlider, QToolButton, QVBoxLayout, QWidget)

from tools.drawing import Tool
from ui import icons
from ui.styles import ACCENT, INK_COLORS, TEXT


class ToolRail(QFrame):
    """Vertical dark palette with one checkable button per drawing tool."""

    toolSelected = Signal(str)

    _TOOLS = [
        (Tool.PEN, "pen", "Pen (P)"),
        (Tool.ERASER, "eraser", "Eraser (E)"),
        (Tool.LINE, "line", "Line (L)"),
        (Tool.RECT, "rect", "Rectangle (R)"),
        (Tool.CIRCLE, "circle", "Circle (C) - drag from the centre"),
        (Tool.TEXT, "text", "Text annotation (T)"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolRail")
        self.setFixedWidth(68)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QToolButton] = {}
        col = QVBoxLayout(self)
        col.setContentsMargins(10, 12, 10, 12)
        col.setSpacing(6)
        for tool, icon_name, tip in self._TOOLS:
            btn = QToolButton()
            btn.setObjectName("tool")
            btn.setCheckable(True)
            btn.setIcon(icons.icon(icon_name, "#C9CFEE", 24, on_color="#FFFFFF"))
            btn.setIconSize(QSize(24, 24))
            btn.setFixedSize(48, 48)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, t=tool: self.toolSelected.emit(t.value))
            self._group.addButton(btn)
            self._buttons[tool.value] = btn
            col.addWidget(btn)
        col.addStretch(1)

    def set_tool(self, tool: str) -> None:
        if tool in self._buttons:
            self._buttons[tool].setChecked(True)


class ActionBar(QFrame):
    """Top bar: navigation + undo/redo/clear + file operations + fullscreen."""

    homeClicked = Signal()
    undoClicked = Signal()
    redoClicked = Signal()
    clearClicked = Signal()
    openClicked = Signal()
    saveClicked = Signal()
    fullscreenClicked = Signal()
    trackToggled = Signal(bool)
    modeSelected = Signal(str)       # navigation | drawing | selection
    menuClicked = Signal()

    _CHIP_COLORS = {"ok": "#16A34A", "warn": "#D97706", "error": "#E11D48"}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("actionBar")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(2)

        self.home_btn = self._button("home", "Home", "Back to the home menu (Ctrl+H)", self.homeClicked)
        row.addWidget(self.home_btn)
        row.addWidget(self._separator())

        title = QLabel("Whiteboard")
        title.setObjectName("boardTitle")
        self.info = QLabel("")
        self.info.setObjectName("boardInfo")
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(title)
        titles.addWidget(self.info)
        row.addSpacing(8)
        row.addLayout(titles)
        row.addStretch(1)

        # interaction mode (segmented) + on-board menu button
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self.mode_buttons: dict[str, QToolButton] = {}
        for mode, text, tip in (("navigation", "Navigate", "Navigation mode (1): move the pointer, Next = click"),
                                ("drawing", "Draw", "Drawing mode (2): Next puts the pen down / up at the pointer"),
                                ("selection", "Select", "Selection mode (3): rest on a menu item to confirm it")):
            b = QToolButton()
            b.setObjectName("bar")
            b.setCheckable(True)
            b.setText(text)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, m=mode: self.modeSelected.emit(m))
            self._mode_group.addButton(b)
            self.mode_buttons[mode] = b
            row.addWidget(b)
        self.mode_buttons["navigation"].setChecked(True)
        self.menu_btn = self._button("menu", "Menu", "Open the on-board menu (M)", self.menuClicked)
        row.addWidget(self.menu_btn)
        row.addWidget(self._separator())

        # camera pointer tracking: toggle button + live status chip (hidden while tracking is off)
        self.track_chip = QLabel("")
        self.track_chip.setVisible(False)
        row.addWidget(self.track_chip)
        row.addSpacing(6)
        self.track_btn = QToolButton()
        self.track_btn.setObjectName("bar")
        self.track_btn.setCheckable(True)
        self.track_btn.setIcon(icons.icon("pointer", TEXT, 20, on_color=ACCENT))
        self.track_btn.setIconSize(QSize(20, 20))
        self.track_btn.setText("Track")
        self.track_btn.setToolTip("Show the camera-tracked pointer on the board (K)")
        self.track_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.track_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.track_btn.toggled.connect(self.trackToggled)
        self.track_btn.toggled.connect(lambda on: self.track_chip.setVisible(on))
        row.addWidget(self.track_btn)
        row.addWidget(self._separator())

        self.undo_btn = self._button("undo", "Undo", "Undo (Ctrl+Z)", self.undoClicked)
        self.redo_btn = self._button("redo", "Redo", "Redo (Ctrl+Y)", self.redoClicked)
        self.clear_btn = self._button("trash", "Clear", "Clear the board (Ctrl+Del)", self.clearClicked)
        self.open_btn = self._button("image", "Open image", "Open an image or saved drawing (Ctrl+O)",
                                     self.openClicked)
        self.save_btn = self._button("save", "Save PNG", "Save the board as PNG (Ctrl+S)", self.saveClicked)
        self.fs_btn = self._button("fullscreen", "", "Fullscreen (F11)", self.fullscreenClicked)
        for w in (self.undo_btn, self.redo_btn, self._separator(), self.clear_btn, self._separator(),
                  self.open_btn, self.save_btn, self._separator(), self.fs_btn):
            row.addWidget(w)

    def _button(self, icon_name: str, text: str, tip: str, signal: Signal) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("bar")
        btn.setIcon(icons.icon(icon_name, TEXT, 20, on_color=ACCENT))
        btn.setIconSize(QSize(20, 20))
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if text
                               else Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn.clicked.connect(signal)
        return btn

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setObjectName("vsep")
        sep.setFixedHeight(22)
        return sep

    def set_track_status(self, state: str, text: str) -> None:
        color = self._CHIP_COLORS.get(state, "#6B7194")
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        self.track_chip.setText(text)
        # NB: Qt style sheets read 8-digit hex as #AARRGGBB, so the tint is written as rgba()
        self.track_chip.setStyleSheet(
            f"background: rgba({r}, {g}, {b}, 0.12); color: {color}; border-radius: 10px; padding: 4px 11px; "
            f"font-size: 12px; font-weight: 700;")

    _LABELLED = ("menu_btn", "track_btn", "undo_btn", "redo_btn", "clear_btn", "open_btn", "save_btn")
    _COMPACT_BELOW = 1200

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Collapse labelled buttons to icon-only on narrow windows so nothing is clipped."""
        super().resizeEvent(event)
        compact = self.width() < self._COMPACT_BELOW
        style = (Qt.ToolButtonStyle.ToolButtonIconOnly if compact
                 else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for name in self._LABELLED:
            getattr(self, name).setToolButtonStyle(style)
        self.info.setVisible(not compact)

    def set_mode(self, mode: str) -> None:
        if mode in self.mode_buttons:
            self.mode_buttons[mode].setChecked(True)

    def set_history_state(self, can_undo: bool, can_redo: bool) -> None:
        self.undo_btn.setEnabled(can_undo)
        self.redo_btn.setEnabled(can_redo)

    def set_fullscreen(self, on: bool) -> None:
        self.fs_btn.setIcon(icons.icon("exitfs" if on else "fullscreen", TEXT, 20))
        self.fs_btn.setToolTip("Exit fullscreen (F11 / Esc)" if on else "Fullscreen (F11)")


class _BrushPreview(QWidget):
    """Small live preview of the current colour and thickness."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(54, 40)
        self._color = QColor(INK_COLORS[0])
        self._width = 6

    def set_style(self, color: QColor, width: int) -> None:
        self._color, self._width = color, width
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(self._color, min(self._width, 30), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawPoint(self.width() // 2, self.height() // 2)


class StyleBar(QFrame):
    """Bottom bar: pen colours, thickness slider/presets, live coordinates."""

    colorChanged = Signal(QColor)
    thicknessChanged = Signal(int)
    zoomInClicked = Signal()
    zoomOutClicked = Signal()
    fitClicked = Signal()
    panToggled = Signal(bool)

    PRESETS = (("Thin", 2), ("Medium", 6), ("Thick", 14))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("styleBar")
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(6)

        self._color_group = QButtonGroup(self)
        self._color_group.setExclusive(True)
        self._swatches: dict[str, QPushButton] = {}
        for hex_color in INK_COLORS:
            row.addWidget(self._make_swatch(hex_color))
        self.custom_btn = QToolButton()
        self.custom_btn.setObjectName("bar")
        self.custom_btn.setIcon(icons.icon("plus", TEXT, 18))
        self.custom_btn.setToolTip("Custom colour...")
        self.custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_btn.clicked.connect(self._pick_custom)
        row.addWidget(self.custom_btn)
        row.addSpacing(8)
        sep = QFrame()
        sep.setObjectName("vsep")
        sep.setFixedHeight(22)
        row.addWidget(sep)
        row.addSpacing(8)

        self._preview = _BrushPreview()
        row.addWidget(self._preview)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 40)
        self.slider.setFixedWidth(170)
        self.slider.setMinimumHeight(26)
        self.slider.setToolTip("Thickness ( [ and ] )")
        self.slider.valueChanged.connect(self._on_slider)
        row.addWidget(self.slider)
        self.value_label = QLabel("6 px")
        self.value_label.setFixedWidth(44)
        row.addWidget(self.value_label)

        self._preset_group = QButtonGroup(self)
        self._preset_group.setExclusive(True)
        self._preset_buttons: list[tuple[QPushButton, int]] = []
        for name, value in self.PRESETS:
            btn = QPushButton(name)
            btn.setObjectName("preset")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, v=value: self.slider.setValue(v))
            self._preset_group.addButton(btn)
            self._preset_buttons.append((btn, value))
            row.addWidget(btn)

        row.addStretch(1)
        # image viewer controls: zoom out / percentage / zoom in / fit / pan
        self.view_box = QWidget()
        vrow = QHBoxLayout(self.view_box)
        vrow.setContentsMargins(0, 0, 0, 0)
        vrow.setSpacing(2)
        self.zoom_out_btn = self._view_button("-", "Zoom out  ( - or mouse wheel )", self.zoomOutClicked)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(46)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setStyleSheet("font-weight: 700;")
        self.zoom_in_btn = self._view_button("+", "Zoom in  ( + or mouse wheel )", self.zoomInClicked)
        self.fit_btn = self._view_button("Fit", "Back to the whole board  ( 0 )", self.fitClicked)
        self.pan_btn = self._view_button("Pan", "Drag the view with the mouse or the pointer "
                                         "(middle mouse button always pans)", None)
        self.pan_btn.setCheckable(True)
        self.pan_btn.toggled.connect(self.panToggled)
        for w in (self.zoom_out_btn, self.zoom_label, self.zoom_in_btn, self.fit_btn, self.pan_btn):
            vrow.addWidget(w)
        row.addWidget(self.view_box)
        row.addSpacing(10)
        self.coords = QLabel("")
        self.coords.setObjectName("boardInfo")
        row.addWidget(self.coords)

        self._color = QColor(INK_COLORS[0])

    def _view_button(self, text: str, tip: str, signal) -> QToolButton:
        b = QToolButton()
        b.setObjectName("bar")
        b.setText(text)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if signal is not None:
            b.clicked.connect(signal)
        return b

    def set_zoom_text(self, text: str) -> None:
        self.zoom_label.setText(text)

    def set_pan_checked(self, on: bool) -> None:
        self.pan_btn.blockSignals(True)
        self.pan_btn.setChecked(on)
        self.pan_btn.blockSignals(False)

    _COMPACT_BELOW = 1180        # below this width the optional extras (preview, presets, coordinates) are hidden

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Hide the optional extras (preview, presets, coordinates) on narrow windows."""
        super().resizeEvent(event)
        wide = self.width() >= self._COMPACT_BELOW
        self._preview.setVisible(wide)
        self.coords.setVisible(wide)
        for btn, _ in self._preset_buttons:
            btn.setVisible(wide)

    # ---------------------------------------------------------------- colours
    def _make_swatch(self, hex_color: str) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("swatch")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(hex_color.upper())
        btn.setStyleSheet(f"QPushButton#swatch {{ background: {hex_color}; }}")
        btn.clicked.connect(lambda _=False, c=hex_color: self._choose(QColor(c)))
        self._color_group.addButton(btn)
        self._swatches[hex_color.lower()] = btn
        return btn

    def _choose(self, color: QColor) -> None:
        self._color = color
        self._preview.set_style(color, self.slider.value())
        self.colorChanged.emit(color)

    def _pick_custom(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Pen colour")
        if color.isValid():
            self.set_color(color)
            self.colorChanged.emit(color)

    def set_color(self, color: QColor) -> None:
        self._color = color
        btn = self._swatches.get(color.name().lower())
        if btn is not None:
            btn.setChecked(True)
        else:  # custom colour: no swatch is highlighted
            self._color_group.setExclusive(False)
            for b in self._swatches.values():
                b.setChecked(False)
            self._color_group.setExclusive(True)
        self._preview.set_style(color, self.slider.value())

    # -------------------------------------------------------------- thickness
    def _on_slider(self, value: int) -> None:
        self.value_label.setText(f"{value} px")
        self._preview.set_style(self._color, value)
        self._sync_presets(value)
        self.thicknessChanged.emit(value)

    def _sync_presets(self, value: int) -> None:
        for btn, preset in self._preset_buttons:
            btn.setChecked(preset == value)

    def set_thickness(self, value: int) -> None:
        self.slider.setValue(int(value))

    def set_coords_text(self, text: str) -> None:
        self.coords.setText(text)
