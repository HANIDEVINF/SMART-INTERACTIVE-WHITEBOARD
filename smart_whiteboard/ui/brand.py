"""LuminaBoard logo: a violet-to-teal rounded square with a hand-drawn stroke and a pointer dot."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


def logo_pixmap(size: int = 64) -> QPixmap:
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(scale, scale)

    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#7C6CF2"))
    grad.setColorAt(1.0, QColor("#12B5A6"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), size * 0.28, size * 0.28)

    # the "ink" swoosh
    path = QPainterPath(QPointF(size * 0.22, size * 0.66))
    path.cubicTo(size * 0.34, size * 0.30, size * 0.46, size * 0.86, size * 0.60, size * 0.50)
    p.setPen(QPen(QColor("white"), size * 0.095, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)

    # the tracked pointer
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("white"))
    p.drawEllipse(QPointF(size * 0.75, size * 0.30), size * 0.075, size * 0.075)
    p.setBrush(QColor(255, 255, 255, 70))
    p.drawEllipse(QPointF(size * 0.75, size * 0.30), size * 0.14, size * 0.14)
    p.end()
    pm.setDevicePixelRatio(scale)
    return pm


def app_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(logo_pixmap(s))
    return ic
