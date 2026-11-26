"""Painting of the on-board menu, click ripples and the mode HUD.

Everything is drawn in *board* coordinates (the same space as the pointer), then scaled to the widget, so the menu is
exactly as large and as reachable for the camera pointer as it is for the mouse.  The geometry itself lives in
``core.menu_model`` (testable without Qt).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from core.menu_model import BACK_ID, MenuModel
from ui.styles import ACCENT, AMBER, GREEN, NAVY, NAVY_2, NAVY_3, NAVY_LINE, ON_NAVY, ON_NAVY_MUTED, ROSE, TEAL

RIPPLE_MS = 650


@dataclass
class Ripple:
    x: float
    y: float
    kind: str                    # "left" | "right"
    t0: float = field(default_factory=time.monotonic)

    def age_ms(self, now: float | None = None) -> float:
        return ((now if now is not None else time.monotonic()) - self.t0) * 1000.0

    def alive(self, now: float | None = None) -> bool:
        return self.age_ms(now) < RIPPLE_MS


def _font(px: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPixelSize(px)
    f.setBold(bold)
    return f


def paint_menu(p: QPainter, model: MenuModel, board_w: float, board_h: float, hover: str | None,
               focus_id: str | None, dwell_target: str | None, dwell_progress: float) -> None:
    """Draw the current menu level. The painter must already be in board coordinates."""
    if not model.is_open:
        return
    panel = model.panel_rect(board_w, board_h)
    if panel is None:
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # panel
    p.setPen(QPen(QColor(NAVY_LINE), 2))
    p.setBrush(QColor(14, 19, 48, 236))
    p.drawRoundedRect(QRectF(*panel), 26, 26)

    for slot in model.layout(board_w, board_h):
        r = QRectF(*slot.rect)
        if slot.kind == "title":
            p.setPen(QColor(ON_NAVY))
            p.setFont(_font(30, True))
            p.drawText(r.adjusted(18, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, slot.label)
            continue
        item = slot.item
        is_hover = slot.id == hover
        is_focus = slot.id == focus_id
        danger = bool(item and item.danger and not item.is_submenu)
        fill = QColor(ACCENT) if is_hover else QColor(NAVY_3 if is_focus else NAVY_2)
        if danger and not is_hover:
            fill = QColor(120, 28, 52)
        p.setBrush(fill)
        p.setPen(QPen(QColor(255, 255, 255, 190), 3) if is_focus else Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, 18, 18)

        left = r.x() + 22
        if item is not None and item.swatch:
            p.setPen(QPen(QColor(255, 255, 255, 220), 3))
            p.setBrush(QColor(item.swatch))
            p.drawEllipse(QPointF(left + 17, r.center().y()), 17, 17)
            left += 46
        checked = bool(item and item.flag and model.flags.get(item.flag, False))
        if checked:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(GREEN))
            c = QPointF(r.right() - 30, r.center().y())
            p.drawEllipse(c, 15, 15)
            p.setPen(QPen(QColor("white"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline([QPointF(c.x() - 7, c.y()), QPointF(c.x() - 2, c.y() + 6), QPointF(c.x() + 8, c.y() - 6)])

        label = ("<  " + slot.label) if slot.kind == "back" else slot.label
        p.setPen(QColor("white"))
        p.setFont(_font(31, True))
        text_rect = QRectF(left, r.y(), r.right() - left - 56, r.height())
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        if item is not None and item.hint and not item.is_submenu:
            p.setPen(QColor(255, 255, 255, 150 if is_hover else 110))
            p.setFont(_font(20))
            p.drawText(QRectF(r.x(), r.y(), r.width() - (66 if checked else 24), r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, item.hint)
        if item is not None and item.is_submenu:
            p.setPen(QPen(QColor(255, 255, 255, 220), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.RoundJoin))
            cx, cy = r.right() - 32, r.center().y()
            p.drawPolyline([QPointF(cx - 6, cy - 12), QPointF(cx + 6, cy), QPointF(cx - 6, cy + 12)])

        if dwell_target == slot.id and dwell_progress > 0.0:      # dwell ring (selection mode)
            c = QPointF(r.right() - 32, r.center().y())
            rr = QRectF(c.x() - 20, c.y() - 20, 40, 40)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 70), 6))
            p.drawEllipse(rr)
            p.setPen(QPen(QColor(AMBER), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(rr, 90 * 16, int(-360 * 16 * dwell_progress))
    p.restore()


def paint_ripples(p: QPainter, ripples: list[Ripple], now: float | None = None) -> None:
    """Expanding ring + label at every remote click (left = violet, right = teal). Board coordinates."""
    for rp in ripples:
        age = rp.age_ms(now)
        if age >= RIPPLE_MS:
            continue
        t = age / RIPPLE_MS
        color = QColor(ACCENT if rp.kind == "left" else TEAL)
        alpha = int(255 * (1 - t) ** 1.5)
        radius = 22 + 62 * (1 - (1 - t) ** 2)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), alpha), 8))
        p.setBrush(QColor(color.red(), color.green(), color.blue(), int(alpha * 0.18)))
        p.drawEllipse(QPointF(rp.x, rp.y), radius, radius)
        label = "Left click" if rp.kind == "left" else "Right click"
        p.setFont(_font(26, True))
        w = 150
        tag = QRectF(rp.x - w / 2, rp.y - radius - 52, w, 40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color.red(), color.green(), color.blue(), alpha))
        p.drawRoundedRect(tag, 20, 20)
        p.setPen(QColor(255, 255, 255, alpha))
        p.drawText(tag, Qt.AlignmentFlag.AlignCenter, label)
        p.restore()


def paint_hud(p: QPainter, rect: QRectF, mode_label: str, pen_down: bool, pointer_source: str,
              extra: str = "") -> None:
    """Pill at the bottom-left of the board: mode, pen state, where the pointer comes from. Widget coordinates."""
    text = f"{mode_label}   |   {'PEN DOWN' if pen_down else 'pen up'}   |   pointer: {pointer_source}"
    if extra:
        text += f"   |   {extra}"
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    f = QFont()
    f.setPixelSize(13)
    f.setBold(True)
    p.setFont(f)
    w = p.fontMetrics().horizontalAdvance(text) + 30
    pill = QRectF(rect.right() - w - 14, rect.y() + 14, w, 28)        # top-right: clear of the menu and page controls
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(ROSE if pen_down else NAVY).lighter(100) if pen_down else QColor(36, 44, 94, 235))
    p.drawRoundedRect(pill, 14, 14)
    p.setPen(QColor("white"))
    p.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
    p.restore()


def paint_lesson_bar(p: QPainter, slots, label: str, hover: str | None, dwell_target: str | None,
                     dwell_progress: float, can_prev: bool, can_next: bool) -> None:
    """Previous / page indicator / Next strip at the bottom of the board (board coordinates)."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for s in slots:
        r = QRectF(*s.rect)
        if s.kind == "title":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(14, 19, 48, 215))
            p.drawRoundedRect(r, 20, 20)
            p.setPen(QColor("white"))
            p.setFont(_font(32, True))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
            continue
        enabled = can_prev if s.id == "lesson.prev" else can_next
        is_hover = s.id == hover and enabled
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ACCENT) if is_hover else QColor(14, 19, 48, 215 if enabled else 110))
        p.drawRoundedRect(r, 20, 20)
        p.setPen(QColor(255, 255, 255, 255 if enabled else 110))
        p.setFont(_font(32, True))
        text = "<   Previous" if s.id == "lesson.prev" else "Next   >"
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        if dwell_target == s.id and dwell_progress > 0.0 and enabled:
            ring = QRectF(r.center().x() - 20, r.y() + 6, 40, 40) if False else QRectF(r.right() - 52, r.y() + 8, 36, 36)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 70), 6))
            p.drawEllipse(ring)
            p.setPen(QPen(QColor(AMBER), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(ring, 90 * 16, int(-360 * 16 * dwell_progress))
    p.restore()
