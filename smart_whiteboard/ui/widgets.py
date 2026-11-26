"""Reusable widgets: action cards, status indicators and toast notifications."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
                               QWidget)

from ui import icons
from ui.styles import STATE_COLORS, ROSE, GREEN, AMBER, ON_NAVY_MUTED, MUTED, TEXT


class ActionCard(QFrame):
    """Large clickable card used on the dashboard. Reachable and activatable with the keyboard."""

    clicked = Signal()

    def __init__(self, icon_name: str, title: str, text: str, accent: str,
                 badge: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(104)

        chip = QLabel()
        chip.setFixedSize(50, 50)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setPixmap(icons.pixmap(icon_name, "#FFFFFF", 24))
        chip.setStyleSheet(f"background: {accent}; border-radius: 15px;")

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addWidget(title_label)
        title_row.addStretch(1)
        if badge:  # roadmap badge sits on the title line so it never squeezes the description
            b = QLabel(badge)
            b.setObjectName("soonBadge")
            title_row.addWidget(b)
        text_label = QLabel(text)
        text_label.setObjectName("cardText")
        text_label.setWordWrap(True)
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addStretch(1)
        col.addLayout(title_row)
        col.addWidget(text_label)
        col.addStretch(1)

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 14, 16, 14)
        row.setSpacing(16)
        row.addWidget(chip)
        row.addLayout(col, 1)

        for child in self.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class StatusRow(QWidget):
    """A coloured dot + title + value, e.g. ``● Camera   Not started``."""

    def __init__(self, title: str, dark: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dot = QLabel()
        self._dot.setFixedSize(10, 10)
        self._title = QLabel(title)
        self._value = QLabel("-")
        self._value.setWordWrap(False)
        title_color = ON_NAVY_MUTED if dark else MUTED
        value_color = "#FFFFFF" if dark else TEXT
        self._title.setStyleSheet(f"color: {title_color}; font-size: 12px;")
        self._value.setStyleSheet(f"color: {value_color}; font-size: 12px; font-weight: 600;")
        # the value takes the remaining width (right-aligned) and elides with "..." instead of being clipped
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._full_text = "-"
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(9)
        row.addWidget(self._dot)
        row.addWidget(self._title)
        row.addWidget(self._value, 1)
        self.set_state("off", "-")

    def set_state(self, state: str, text: str) -> None:
        color = STATE_COLORS.get(state, STATE_COLORS["off"])
        self._dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        self._full_text = text
        self._value.setToolTip(text)
        self._apply_elision()

    def _apply_elision(self) -> None:
        width = self._value.width()
        fm = self._value.fontMetrics()
        # while the widget has not been laid out yet (width 1-ish) show the full text
        shown = self._full_text if width < 30 else fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        self._value.setText(shown)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_elision()


class Toast(QLabel):
    """Short non-blocking message shown at the bottom centre of its parent widget."""

    _COLORS = {"info": "#0E1330", "success": GREEN, "warn": AMBER, "error": ROSE}

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._effect.setOpacity(0.0)
        self.hide()

    def show_message(self, text: str, kind: str = "info", msec: int = 2600) -> None:
        self.setStyleSheet(f"background: {self._COLORS.get(kind, self._COLORS['info'])};")
        self.setText(text)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setDuration(160)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(msec)

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setDuration(380)
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()
        QTimer.singleShot(400, lambda: self.hide() if self._effect.opacity() < 0.05 else None)

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 28)


class ParamSlider(QWidget):
    """Label + slider + live value, used by the detection tuning panel.

    `scale` lets integer sliders represent decimals (scale=100 -> 0.05 steps); `fmt` formats the value.
    """

    valueChanged = Signal(float)

    def __init__(self, label: str, lo: float, hi: float, value: float, scale: int = 1,
                 fmt: str = "{:.0f}", tooltip: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QSlider
        self._scale, self._fmt = scale, fmt
        self._label = QLabel(label)
        self._label.setFixedWidth(118)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(int(round(lo * scale)), int(round(hi * scale)))
        self._slider.setMinimumHeight(24)
        self._value = QLabel()
        self._value.setFixedWidth(58)
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._value.setStyleSheet(f"color: {TEXT}; font-weight: 700;")
        if tooltip:
            for w in (self, self._label, self._slider):
                w.setToolTip(tooltip)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self._label)
        row.addWidget(self._slider, 1)
        row.addWidget(self._value)
        self._slider.valueChanged.connect(self._on_changed)
        self.set_value(value)

    def _on_changed(self, raw: int) -> None:
        self._value.setText(self._fmt.format(raw / self._scale))
        self.valueChanged.emit(raw / self._scale)

    def value(self) -> float:
        return self._slider.value() / self._scale

    def set_value(self, value: float) -> None:
        """Set the value without emitting valueChanged (used when the model changes)."""
        self._slider.blockSignals(True)
        self._slider.setValue(int(round(value * self._scale)))
        self._slider.blockSignals(False)
        self._value.setText(self._fmt.format(self._slider.value() / self._scale))
