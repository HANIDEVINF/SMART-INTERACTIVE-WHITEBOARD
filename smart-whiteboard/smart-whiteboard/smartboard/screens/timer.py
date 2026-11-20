"""SCREEN: classroom countdown timer (uses features/timer.py)."""
from __future__ import annotations

import math
import time

from ..events import ClickEvent, LEFT
from ..graphics import theme
from ..graphics.panels import panel
from ..graphics.widgets import hit
from .base import Screen


class TimerScreen(Screen):
    title = "Timer"

    def layout(self, ctx):
        self.buttons = []
        T = ctx.timer
        sc = ctx.sc
        cw, ch = sc(250), sc(84)
        gap = sc(24)
        row_y = ctx.h - sc(330)
        specs = [("- 1 min", "minus", lambda c: T.add(-60), None), ("+ 1 min", "plus", lambda c: T.add(60), None),
                 (lambda: "Pause" if T.running else "Start", "pause" if False else "play", lambda c: T.toggle(), None),
                 ("Reset", "reset", lambda c: T.reset(), None)]
        total = len(specs) * cw + (len(specs) - 1) * gap
        x = (ctx.w - total) // 2
        for lab, ic, act, sel in specs:
            self.make_button(ctx, (x, row_y, x + cw, row_y + ch), lab, act, icon=ic, font=0.8 * ctx.scale,
                             accent=theme.GOOD if lab != "Reset" and callable(lab) else theme.CYAN)
            x += cw + gap
        presets = [("1 min", 60), ("5 min", 300), ("10 min", 600), ("20 min", 1200)]
        pw = sc(180)
        total = len(presets) * pw + (len(presets) - 1) * gap
        x = (ctx.w - total) // 2
        for lab, secs in presets:
            self.make_button(ctx, (x, row_y + ch + gap, x + pw, row_y + ch + gap + sc(64)), lab,
                             lambda c, secs=secs: c.timer.set(secs), font=0.65 * ctx.scale, accent=theme.VIOLET)
            x += pw + gap
        self.make_button(ctx, (sc(30), ctx.h - sc(100), sc(30) + sc(240), ctx.h - sc(30)), "Menu",
                         lambda c: c.nav.back(), icon="back", accent=theme.SLATE, font=0.7 * ctx.scale)

    def update(self, ctx, pos, dt):
        ctx.timer.tick()

    def status(self, ctx):
        return "NEXT = press a button      PREV = back"

    def render(self, ctx, canvas, pos):
        T, s = ctx.timer, ctx.scale
        canvas.clear()
        cx, cy, R = ctx.w / 2, ctx.top + 330 * s, 230 * s
        done = T.finished
        col = theme.AMBER if (done or T.fraction < 0.15) else theme.CYAN
        canvas.ring((cx, cy), R, 22 * s, theme.PANEL_LIGHT, 0.9)
        n = 120
        k = T.fraction
        pts = [(cx + R * math.cos(-math.pi / 2 + 2 * math.pi * k * i / n),
                cy + R * math.sin(-math.pi / 2 + 2 * math.pi * k * i / n)) for i in range(n + 1)]
        for a, b in zip(pts[:-1], pts[1:]):
            if k > 0:
                canvas.line(a, b, col, 22 * s)
        blink = 1.0 if not done else (0.5 + 0.5 * math.sin(time.perf_counter() * 8))
        canvas.text(T.text(), cx, cy - 8 * s, 150 * s, theme.lerp(theme.PANEL_LIGHT, theme.TEXT, blink), True, "cm")
        canvas.text("Time is up!" if done else ("running" if T.running else "paused"), cx, cy + 112 * s, 30 * s,
                    theme.AMBER if done else theme.TEXT_DIM, True, "cm")
        self.draw_buttons(canvas, pos)
