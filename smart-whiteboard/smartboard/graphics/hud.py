"""Always-visible overlay, independent from the screens:
  * glass top bar: logo, screen title + hint, live X/Y readout, remote-button
    indicators (PREV / NEXT light up when pressed), tracking status, Home / Reset;
  * pointer cursor: glow + ring + comet trail, expanding ripple on every click;
  * toast messages.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Deque, Optional, Tuple

from . import icons, theme
from .anim import clamp01, ease_out
from .sprite import render_sprite
from .widgets import Button, hit


class Hud:
    def __init__(self, w: int, h: int, scale: float, on_home, on_reset):
        self.w, self.h, self.s = w, h, scale
        self.bar_h = int(86 * scale)
        bw, bh, pad = int(170 * scale), int(56 * scale), int(14 * scale)
        top = (self.bar_h - bh) // 2
        self.btn_reset = Button((w - pad - bw, top, w - pad, top + bh), "Reset", on_reset,
                                icon="reset", accent=theme.AMBER, kind="pill", font=0.72 * scale)
        self.btn_home = Button((w - 2 * pad - 2 * bw, top, w - 2 * pad - bw, top + bh), "Home", on_home,
                               icon="home", accent=theme.CYAN, kind="pill", font=0.72 * scale)
        self.buttons = [self.btn_home, self.btn_reset]
        self.toast_text, self.toast_ttl, self.toast_total = "", 0.0, 1.0
        self.trail: Deque[Tuple[float, float]] = deque(maxlen=22)
        self.click_flash = []                       # [x, y, age, colour]
        self.key_flash = {"left": 9.0, "right": 9.0}  # seconds since the last press (large = idle)
        self._bar = None
        self._t = 0.0
        self.dwell = 0.0                            # 0..1 progress of a hold-to-click

    # -- messages ------------------------------------------------------------------
    def toast(self, msg: str, seconds: float = 2.5):
        self.toast_text, self.toast_ttl, self.toast_total = msg, seconds, seconds

    def flash_click(self, pos, left: bool):
        self.click_flash.append([pos[0], pos[1], 0.0, theme.GOOD if left else theme.AMBER])

    def flash_key(self, button: str):
        self.key_flash[button] = 0.0

    def update(self, dt: float):
        self._t += dt
        self.toast_ttl = max(0.0, self.toast_ttl - dt)
        for f in self.click_flash:
            f[2] += dt
        self.click_flash = [f for f in self.click_flash if f[2] < 0.6]
        for k in self.key_flash:
            self.key_flash[k] += dt

    def hit(self, pos) -> Optional[Button]:
        return hit(self.buttons, pos)

    # -- top bar -----------------------------------------------------------------------
    def _bar_sprite(self):
        if self._bar is None:
            w, h = self.w, self.bar_h

            def draw(cv, ox, oy):
                cv.gradient_rect(ox, oy, ox + w, oy + h, theme.rgb(18, 26, 56), theme.rgb(12, 18, 40))
                cv.rect(ox, oy + h - 2, ox + w, oy + h, theme.LINE, 0.9)
                cv.rrect(ox + 22 * self.s, oy + 20 * self.s, ox + 68 * self.s, oy + 66 * self.s, 14 * self.s,
                         theme.CYAN, 1.0, theme.VIOLET)
                icons.draw(cv, "pen", ox + 45 * self.s, oy + 43 * self.s, 28 * self.s, theme.BG)
            self._bar = render_sprite(w, h, draw, 0)
        return self._bar

    def draw_bar(self, canvas, title: str, pointer_pos, status: str = "", sample=None, fps: float = 0.0):
        s = self.s
        canvas.sprite(self._bar_sprite(), 0, 0)
        canvas.text(title, 88 * s, self.bar_h * 0.40, 30 * s, theme.TEXT, True, "lm")
        if status:
            canvas.text_fit(status, 88 * s, self.bar_h * 0.74, 17 * s, self.w * 0.34, theme.TEXT_DIM, False, "lm")
        self._draw_readout(canvas, pointer_pos, sample, fps)
        over = self.hit(pointer_pos)
        for b in self.buttons:
            b.draw(canvas, hovered=(b is over))

    def _draw_readout(self, canvas, pos, sample, fps):
        """Centre of the bar: tracking dot, X / Y of the pointer, PREV / NEXT key lights."""
        s = self.s
        cx = self.w * 0.50
        cy = self.bar_h / 2
        tracked = bool(sample and sample.tracked)
        col = theme.GOOD if tracked else (theme.WARN if pos else theme.SLATE)
        # X / Y chip
        cw, ch = 330 * s, 52 * s
        canvas.rrect(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2, ch / 2, theme.PANEL, 1.0, None)
        canvas.rrect(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2, ch / 2, col, 0.7, None, 1.6)
        canvas.circle((cx - cw / 2 + 26 * s, cy), 6 * s, col)
        if tracked:
            canvas.ring((cx - cw / 2 + 26 * s, cy), (9 + 4 * abs(((self._t * 2) % 2) - 1)) * s, 1.5, col, 0.6)
        if pos:
            canvas.text("X", cx - 100 * s, cy, 15 * s, theme.TEXT_DIM, True, "rm")
            canvas.text("%4d" % pos[0], cx - 88 * s, cy, 24 * s, theme.TEXT, True, "lm")
            canvas.text("Y", cx + 28 * s, cy, 15 * s, theme.TEXT_DIM, True, "rm")
            canvas.text("%4d" % pos[1], cx + 40 * s, cy, 24 * s, theme.TEXT, True, "lm")
        else:
            canvas.text("no pointer", cx + 14 * s, cy, 20 * s, theme.TEXT_DIM, False, "cm")
        # PREV (right click)  /  NEXT (left click) lights
        for name, side, colr, lab in (("right", -1, theme.AMBER, "PREV"), ("left", +1, theme.GOOD, "NEXT")):
            age = self.key_flash[name]
            k = 1.0 - clamp01(age / 0.5)
            bx = cx + side * (cw / 2 + 74 * s)
            bw2, bh2 = 112 * s, 40 * s
            canvas.rrect(bx - bw2 / 2, cy - bh2 / 2, bx + bw2 / 2, cy + bh2 / 2, bh2 / 2,
                         theme.lerp(theme.PANEL, colr, 0.85 * k), 1.0)
            canvas.rrect(bx - bw2 / 2, cy - bh2 / 2, bx + bw2 / 2, cy + bh2 / 2, bh2 / 2, colr, 0.75, None, 1.5)
            canvas.text(lab, bx, cy, 16 * s, theme.BG if k > 0.5 else colr, True, "cm")

    # -- toast ---------------------------------------------------------------------------
    def draw_toast(self, canvas):
        if self.toast_ttl <= 0 or not self.toast_text:
            return
        s = self.s
        age = self.toast_total - self.toast_ttl
        k = min(ease_out(age / 0.18), clamp01(self.toast_ttl / 0.25))       # fade in / out
        w, _ = canvas.text_size(self.toast_text, 26 * s, True)
        cx, cy = self.w / 2, self.h - 110 * s + (1 - k) * 24 * s
        x0, x1, h2 = cx - w / 2 - 44 * s, cx + w / 2 + 44 * s, 32 * s
        canvas.shadow(x0, cy - h2, x1, cy + h2, h2, 18, 8, 0.4 * k)
        canvas.rrect(x0, cy - h2, x1, cy + h2, h2, theme.rgb(30, 42, 88), k, theme.rgb(20, 28, 62))
        canvas.rrect(x0, cy - h2, x1, cy + h2, h2, theme.CYAN, 0.8 * k, None, 1.6)
        canvas.circle((x0 + 28 * s, cy), 6 * s, theme.CYAN, k)
        canvas.text(self.toast_text, cx + 10 * s, cy, 26 * s, theme.TEXT, True, "cm", alpha=k)

    # -- cursor ----------------------------------------------------------------------------
    def draw_cursor(self, canvas, sample, show_trail: bool):
        """Pointer: soft glow + ring + dot + fading comet trail (green = tracked, amber = held)."""
        if sample.board is None:
            return
        x, y = sample.board
        s = self.s
        col = theme.CYAN if sample.tracked else theme.WARN
        if sample.tracked:
            if not self.trail or (x - self.trail[-1][0]) ** 2 + (y - self.trail[-1][1]) ** 2 > 4:
                self.trail.append((x, y))
        else:
            self.trail.clear()
        if show_trail and len(self.trail) > 1:
            pts = list(self.trail)
            n = len(pts)
            for i in range(1, n):
                k = i / n
                canvas.line(pts[i - 1], pts[i], col, (2 + 9 * k) * s, 0.10 + 0.45 * k)
        canvas.glow((x, y), 60 * s, col, 0.55)
        canvas.ring((x, y), 24 * s, max(2.5, 4 * s), theme.WHITE, 0.95)
        canvas.ring((x, y), 24 * s + 4, 2, col, 0.9)
        canvas.circle((x, y), max(3.5, 6 * s), col)
        canvas.circle((x, y), max(1.5, 2.5 * s), theme.WHITE)
        if self.dwell > 0.02:                          # hold-to-click progress ring
            import math
            n = 36
            pts = [(x + 38 * s * math.cos(-math.pi / 2 + 2 * math.pi * self.dwell * i / n),
                    y + 38 * s * math.sin(-math.pi / 2 + 2 * math.pi * self.dwell * i / n)) for i in range(n + 1)]
            for a, b in zip(pts[:-1], pts[1:]):
                canvas.line(a, b, theme.GOOD, 7 * s)
        for fx, fy, age, c in self.click_flash:       # expanding ripple on every click
            k = ease_out(age / 0.6)
            canvas.ring((fx, fy), (22 + k * 120) * s, max(2.0, 6 * s * (1 - k)), c, 1 - k)
            canvas.ring((fx, fy), (14 + k * 70) * s, max(1.5, 4 * s * (1 - k)), theme.WHITE, 0.7 * (1 - k))
