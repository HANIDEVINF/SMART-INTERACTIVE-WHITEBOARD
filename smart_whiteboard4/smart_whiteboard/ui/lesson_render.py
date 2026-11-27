"""Draws one lesson page as an image (shown as the board background, so it can be annotated and zoomed).

Rendered at 2x the board size (3200x1800) so that text and pictures stay sharp when the viewer zooms in.
Layout (in board units, 1600x900): title band at the top, content area above y = 770 (the bottom strip is kept free
for the on-board Previous / Next controls), text on the left and the picture on the right when there is one.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPen

from core.lesson import Lesson, LessonPage
from tools.image_tools import imread_unicode
from ui.styles import ACCENT, ACCENT_SOFT, MUTED, NAVY, TEXT

BOARD_W, BOARD_H = 1600, 900
SCALE = 2
CONTENT_BOTTOM = 770


def _font(px: float, bold: bool = False, mono: bool = False) -> QFont:
    f = QFont()
    f.setFamilies(["Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Courier New"] if mono else
                  ["Segoe UI Variable", "Segoe UI", "Inter", "Helvetica Neue", "Arial", "DejaVu Sans"])
    f.setStyleHint(QFont.StyleHint.Monospace if mono else QFont.StyleHint.SansSerif)
    f.setPixelSize(int(px))
    f.setBold(bold)
    return f


def _bgr_to_qimage(img: np.ndarray) -> QImage:
    img = np.ascontiguousarray(img)
    h, w = img.shape[:2]
    return QImage(img.data, w, h, img.strides[0], QImage.Format.Format_BGR888).copy()


def render_page(lesson: Lesson, index: int, width: int = BOARD_W * SCALE, height: int = BOARD_H * SCALE) -> np.ndarray:
    """Return the page as a (height, width, 3) BGR uint8 array."""
    page = lesson.pages[index]
    qimg = QImage(width, height, QImage.Format.Format_RGB888)
    qimg.fill(QColor("#FAF9F6"))
    p = QPainter(qimg)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing |
                     QPainter.RenderHint.SmoothPixmapTransform)
    p.scale(width / BOARD_W, height / BOARD_H)
    _paint(p, lesson, page, index)
    p.end()
    ptr = qimg.constBits()
    stride = qimg.bytesPerLine()
    arr = np.frombuffer(ptr, dtype=np.uint8, count=stride * height).reshape(height, stride)[:, :width * 3]
    rgb = arr.reshape(height, width, 3)
    return np.ascontiguousarray(rgb[..., ::-1])            # RGB -> BGR


def _paint(p: QPainter, lesson: Lesson, page: LessonPage, index: int) -> None:
    # title band
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(NAVY))
    p.drawRect(QRectF(0, 0, BOARD_W, 118))
    p.setBrush(QColor(ACCENT))
    p.drawRect(QRectF(0, 118, BOARD_W, 8))
    p.setPen(QColor("white"))
    p.setFont(_font(54, True))
    fm = QFontMetricsF(p.font())
    title = fm.elidedText(page.title, Qt.TextElideMode.ElideRight, BOARD_W - 150)
    p.drawText(QRectF(70, 0, BOARD_W - 140, 118), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)

    # picture (right) -------------------------------------------------------------------------------------------------
    img_path = lesson.image_path(page)
    picture = imread_unicode(img_path) if img_path is not None and img_path.exists() else None
    text_w = BOARD_W - 140
    if page.image:
        text_w = 640 if picture is not None else text_w
        area = QRectF(760, 170, 770, CONTENT_BOTTOM - 170)
        if picture is not None:
            q = _bgr_to_qimage(picture)
            s = min(area.width() / q.width(), area.height() / q.height())
            w, h = q.width() * s, q.height() * s
            r = QRectF(area.center().x() - w / 2, area.center().y() - h / 2, w, h)
            p.setPen(QPen(QColor("#D9D6CC"), 2))
            p.setBrush(QColor("white"))
            p.drawRoundedRect(r.adjusted(-8, -8, 8, 8), 10, 10)
            p.drawImage(r, q)
        else:
            _placeholder(p, area, f"Image not found:\n{Path(page.image).name}")

    # text (left) -----------------------------------------------------------------------------------------------------
    y = 168.0
    for raw in page.text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            y += 22
            continue
        if line.startswith("- "):
            font, text, indent, color = _font(37), line[2:], 46, QColor(TEXT)
        elif line.startswith("> "):
            font, text, indent, color = _font(31, True, True), line[2:], 20, QColor(ACCENT)
        else:
            font, text, indent, color = _font(37), line, 0, QColor(TEXT)
        p.setFont(font)
        rect = QRectF(70 + indent, y, text_w - indent, CONTENT_BOTTOM - y)
        flags = int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        need = p.boundingRect(rect, flags, text)
        if need.bottom() > CONTENT_BOTTOM + 4:            # never run into the navigation strip
            p.setPen(QColor(MUTED))
            p.setFont(_font(28))
            p.drawText(QRectF(70, CONTENT_BOTTOM - 40, text_w, 36), Qt.AlignmentFlag.AlignLeft, "...")
            break
        if line.startswith("> "):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENT_SOFT))
            p.drawRoundedRect(QRectF(70, y - 6, text_w, need.height() + 14), 12, 12)
        elif line.startswith("- "):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ACCENT))
            p.drawEllipse(QRectF(74, y + 17, 15, 15))
        p.setPen(color)
        p.setFont(font)
        p.drawText(rect, flags, text)
        y = need.bottom() + (24 if line.startswith(("- ", "> ")) else 20)

    # footer
    p.setPen(QColor(MUTED))
    p.setFont(_font(22))
    p.drawText(QRectF(40, BOARD_H - 44, 520, 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
               lesson.title)


def _placeholder(p: QPainter, area: QRectF, text: str) -> None:
    p.setPen(QPen(QColor("#C9C6BA"), 3, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(area, 16, 16)
    p.setPen(QColor(MUTED))
    p.setFont(_font(30))
    p.drawText(area, Qt.AlignmentFlag.AlignCenter, text)
