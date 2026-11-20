"""Always-visible overlay: top bar (title, Home, Reset), toast messages and
the pointer cursor.  Independent from the screens."""
from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Tuple

from . import theme
from .widgets import Button, hit

class Hud:
    def __init__(self, w: int, h: int, scale: float, on_home, on_reset):
        self.w, self.h, self.s = w, h, scale
        self.bar_h = int(72 * scale)
        bw, bh, pad, top = int(150 * scale), int(52 * scale), int(14 * scale), int(10 * scale)
        self.btn_reset = Button((w - pad - bw, top, w - pad, top + bh), "Reset", on_reset, font=0.8 * scale)
        self.btn_home = Button((w - 2 * (pad + bw), top, w - pad - bw - pad, top + bh), "Home", on_home,
                               font=0.8 * scale)
        self.buttons = [self.btn_home, self.btn_reset]
        self.toast_text = ""
        self.toast_ttl = 0.0
        self.trail: Deque[Tuple[float, float]] = deque(maxlen=14)
        self.click_flash = []   # [x, y, age, color]

    # -- messages ------------------------------------------------------------------
    def toast(self, msg: str, seconds: float = 2.5):
        self.toast_text, self.toast_ttl = msg, seconds

    def flash_click(self, pos, left: bool):
        self.click_flash.append([pos[0], pos[1], 0.0, theme.GOOD if left else theme.WARN])

    def update(self, dt: float):
        self.toast_ttl = max(0.0, self.toast_ttl - dt)
        for f in self.click_flash:
            f[2] += dt
        self.click_flash = [f for f in self.click_flash if f[2] < 0.45]

    def hit(self, pos) -> Optional[Button]:
        return hit(self.buttons, pos)

    # -- drawing ---------------------------------------------------------------------
    def draw_bar(self, canvas, title: str, pointer_pos, status: str = ""):
        s = self.s
        canvas.rect(0, 0, self.w, self.bar_h, theme.PANEL)
        canvas.text(title, 24 * s, self.bar_h / 2, 1.0 * s, theme.TEXT, 2, "lm")
        if status:
            canvas.text(status, self.w * 0.52, self.bar_h / 2, 0.6 * s, theme.TEXT_DIM, 1, "cm")
        over = self.hit(pointer_pos)
        for b in self.buttons:
            b.draw(canvas, hovered=(b is over))

    def draw_toast(self, canvas):
        if self.toast_ttl > 0 and self.toast_text:
            s = self.s
            w, h = canvas.text_size(self.toast_text, 0.9 * s, 2)
            cx, cy = self.w / 2, self.h - 120 * s
            canvas.rrect(cx - w / 2 - 24 * s, cy - 28 * s, cx + w / 2 + 24 * s, cy + 28 * s, 18, theme.PANEL_LIGHT)
            canvas.text(self.toast_text, cx, cy, 0.9 * s, theme.TEXT, 2, "cm")

    def draw_cursor(self, canvas, sample, show_trail: bool):
        """Visible pointer: ring + dot (green = tracked, orange = holding last position)."""
        if sample.board is None:
            return
        x, y = sample.board
        col = theme.GOOD if sample.tracked else theme.WARN
        if show_trail and sample.tracked:
            self.trail.append((x, y))
            for i, (tx, ty) in enumerate(self.trail):
                canvas.circle((tx, ty), 2 + i * 0.25, theme.PANEL_LIGHT)
        elif not sample.tracked:
            self.trail.clear()
        s = self.s
        canvas.ring((x, y), 22 * s, max(2, 4 * s), col)
        canvas.circle((x, y), max(3, 5 * s), col)
        for fx, fy, age, c in self.click_flash:       # expanding ring on every click
            canvas.ring((fx, fy), (22 + age * 160) * s, max(2, 5 * s), c)
