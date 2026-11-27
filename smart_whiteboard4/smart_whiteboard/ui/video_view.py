"""VideoView: shows camera frames (or masks) aspect-correct, with an overlay hook and mouse mapping.

All mouse events are reported in *frame pixel coordinates* (camera space), never widget pixels -
this is the one place where widget <-> camera coordinates are converted, so pages cannot mix them up.
"""
from __future__ import annotations

import math
import time
from typing import Callable

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ui.styles import AMBER, GREEN, NAVY, ROSE

Overlay = Callable[[QPainter, "VideoView"], None]


class VideoView(QWidget):
    pressed = Signal(float, float, int)      # frame x, y, Qt.MouseButton value
    moved = Signal(float, float)
    released = Signal(float, float, int)
    clicked = Signal(float, float, int)      # press + release without dragging

    STALE_SECONDS = 1.5

    def __init__(self, placeholder: str = "No camera signal", smooth: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._frame: np.ndarray | None = None
        self._image: QImage | None = None
        self._placeholder = placeholder
        self._smooth = smooth
        self._overlay: Overlay | None = None
        self._last_t = 0.0
        self._press_pos: QPointF | None = None
        self._dragging = False
        self.setMinimumSize(320, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._stale_timer = QTimer(self)
        self._stale_timer.setInterval(500)
        self._stale_timer.timeout.connect(self._check_stale)
        self._stale_timer.start()

    # ------------------------------------------------------------------ content
    def set_frame(self, frame: np.ndarray | None) -> None:
        """BGR (H, W, 3) or single-channel (H, W) uint8 array. None clears the view."""
        if frame is None:
            self._frame, self._image = None, None
        else:
            frame = np.ascontiguousarray(frame)
            h, w = frame.shape[:2]
            fmt = QImage.Format.Format_Grayscale8 if frame.ndim == 2 else QImage.Format.Format_BGR888
            self._frame = frame                       # keep the buffer alive while QImage points to it
            self._image = QImage(frame.data, w, h, frame.strides[0], fmt)
            self._last_t = time.perf_counter()
        self.update()

    def set_overlay(self, overlay: Overlay | None) -> None:
        self._overlay = overlay
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self.update()

    @property
    def has_frame(self) -> bool:
        return self._image is not None

    @property
    def frame_size(self) -> tuple[int, int] | None:
        return None if self._frame is None else (self._frame.shape[1], self._frame.shape[0])

    def _check_stale(self) -> None:
        if self._image is not None and time.perf_counter() - self._last_t > self.STALE_SECONDS:
            self.update()

    def is_stale(self) -> bool:
        return self._image is not None and time.perf_counter() - self._last_t > self.STALE_SECONDS

    # ------------------------------------------------------------------ geometry
    def frame_rect(self) -> QRectF:
        """Where the frame is drawn inside the widget (aspect ratio preserved, centred)."""
        size = self.frame_size
        pad = 0.0
        if size is None:
            return QRectF(pad, pad, self.width() - 2 * pad, self.height() - 2 * pad)
        w, h = size
        scale = min((self.width() - 2 * pad) / w, (self.height() - 2 * pad) / h)
        rw, rh = w * scale, h * scale
        return QRectF((self.width() - rw) / 2, (self.height() - rh) / 2, rw, rh)

    def scale_factor(self) -> float:
        size = self.frame_size
        return self.frame_rect().width() / size[0] if size else 1.0

    def frame_to_widget(self, x: float, y: float) -> QPointF:
        r, s = self.frame_rect(), self.scale_factor()
        # pixel (i, j) has its centre at (i, j); the image edge is at -0.5, hence the +0.5
        return QPointF(r.x() + (x + 0.5) * s, r.y() + (y + 0.5) * s)

    def widget_to_frame(self, pos: QPointF) -> tuple[float, float]:
        r, s = self.frame_rect(), self.scale_factor()
        return (pos.x() - r.x()) / s - 0.5, (pos.y() - r.y()) / s - 0.5

    def _inside_frame(self, pos: QPointF) -> bool:
        return self._image is not None and self.frame_rect().contains(pos)

    def _clamped_frame_point(self, pos: QPointF) -> tuple[float, float]:
        x, y = self.widget_to_frame(pos)
        w, h = self.frame_size
        return min(max(x, 0.0), w - 1.0), min(max(y, 0.0), h - 1.0)

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if self._inside_frame(e.position()):
            self._press_pos, self._dragging = e.position(), False
            self.pressed.emit(*self._clamped_frame_point(e.position()), e.button().value)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._press_pos is not None:
            if math.dist((e.position().x(), e.position().y()), (self._press_pos.x(), self._press_pos.y())) > 4:
                self._dragging = True
            if self._image is not None:
                self.moved.emit(*self._clamped_frame_point(e.position()))

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if self._press_pos is None or self._image is None:
            return
        fx, fy = self._clamped_frame_point(e.position())
        self.released.emit(fx, fy, e.button().value)
        if not self._dragging:
            self.clicked.emit(fx, fy, e.button().value)
        self._press_pos, self._dragging = None, False

    # ------------------------------------------------------------------ painting
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self._smooth)
        outer = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(outer, 14, 14)
        p.setClipPath(clip)
        p.fillRect(outer, QColor("#0B0F26"))

        if self._image is None:
            p.setPen(QColor("#8E97C8"))
            f = QFont(self.font())
            f.setPointSize(11)
            f.setBold(True)
            p.setFont(f)
            p.drawText(outer, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._placeholder)
            return

        rect = self.frame_rect()
        p.drawImage(rect, self._image)
        p.save()
        p.setClipRect(rect)
        if self._overlay is not None:
            self._overlay(p, self)
        p.restore()
        if self.is_stale():
            p.fillRect(outer, QColor(11, 15, 38, 190))
            p.setPen(QColor("#FFFFFF"))
            f = QFont(self.font())
            f.setPointSize(12)
            f.setBold(True)
            p.setFont(f)
            p.drawText(outer, Qt.AlignmentFlag.AlignCenter, "Camera signal lost")


# ----------------------------------------------------------------------------- shared overlays
def draw_crosshair(p: QPainter, c: QPointF, color: QColor, radius: float = 14.0, label: str | None = None) -> None:
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(0, 0, 0, 150), 4.5))
    p.drawEllipse(c, radius, radius)
    p.setPen(QPen(color, 2.2))
    p.drawEllipse(c, radius, radius)
    p.drawLine(QPointF(c.x() - radius - 6, c.y()), QPointF(c.x() + radius + 6, c.y()))
    p.drawLine(QPointF(c.x(), c.y() - radius - 6), QPointF(c.x(), c.y() + radius + 6))
    if label:
        f = QFont(p.font())
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(0, 0, 0, 170))
        p.drawText(QPointF(c.x() + radius + 9, c.y() - radius + 1), label)
        p.setPen(color)
        p.drawText(QPointF(c.x() + radius + 8, c.y() - radius), label)


def draw_detection(p: QPainter, view: VideoView, result, show_raw: bool = True) -> None:
    """Draw bounding box, raw detection and the filtered pointer of a VisionResult on a VideoView."""
    det = result.detection.detection
    pts = getattr(result.detection, "landmarks", None)
    if pts:                                                       # hand skeleton (MediaPipe backend)
        from core.hand_tracker import HAND_CONNECTIONS
        w = [view.frame_to_widget(x, y) for x, y in pts]
        p.setPen(QPen(QColor(255, 255, 255, 190), 2))
        for i, j in HAND_CONNECTIONS:
            p.drawLine(w[i], w[j])
        pinch = getattr(result.detection, "gesture_state", "")
        p.setPen(Qt.PenStyle.NoPen)
        for k, pt in enumerate(w):
            hot = (k == 8) or (pinch == "next" and k in (4, 12)) or (pinch == "previous" and k in (4, 16))
            p.setBrush(QColor(AMBER if hot else GREEN))
            p.drawEllipse(pt, 5 if k == 8 else 3, 5 if k == 8 else 3)
    if det is not None and not pts:
        a, b = view.frame_to_widget(det.bbox[0] - 0.5, det.bbox[1] - 0.5), view.frame_to_widget(det.bbox[2] - 0.5, det.bbox[3] - 0.5)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(GREEN), 1.6, Qt.PenStyle.DashLine))
        p.drawRect(QRectF(a, b).normalized())
        if show_raw:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 200))
            p.drawEllipse(view.frame_to_widget(det.x, det.y), 2.5, 2.5)
    pos = result.track.position
    if pos is not None:
        color = QColor(GREEN if result.track.state == "tracking" else AMBER)
        draw_crosshair(p, view.frame_to_widget(*pos), color,
                       label=f"{pos[0]:.0f}, {pos[1]:.0f}" + ("" if result.track.state == "tracking" else "  (held)"))
