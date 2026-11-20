"""SCREEN: pointer test - shows the tracked trajectory and measures accuracy.

  * a ruler grid in board pixels, cross-hair lines and a big X / Y readout;
  * the last 4 seconds of the trajectory, drawn as a fading polyline;
  * five targets: aim at each, press NEXT; the distance between the click
    position and the target centre (board px) is the accuracy measure.
"""
from __future__ import annotations

import math
import time
from collections import deque

import numpy as np

from ..events import ClickEvent, LEFT
from ..graphics import theme
from ..graphics.panels import panel
from ..graphics.widgets import hit
from .base import Screen


class PointerTestScreen(Screen):
    title = "Pointer test"

    def on_enter(self, ctx):
        self.trail = deque()                 # (t, x, y)
        self.k = 0
        self.errors = []
        self.targets = [(0.5, 0.5), (0.12, 0.2), (0.88, 0.2), (0.88, 0.82), (0.12, 0.82)]
        self.layout(ctx)

    def layout(self, ctx):
        self.buttons = []
        self.make_button(ctx, (ctx.sc(30), ctx.h - ctx.sc(100), ctx.sc(270), ctx.h - ctx.sc(30)), "Menu",
                         lambda c: c.nav.back(), icon="back", accent=theme.SLATE, font=0.7 * ctx.scale)
        self.make_button(ctx, (ctx.sc(290), ctx.h - ctx.sc(100), ctx.sc(560), ctx.h - ctx.sc(30)), "Restart",
                         lambda c: self.on_enter(c), icon="reset", accent=theme.AMBER, font=0.7 * ctx.scale)

    def _tpos(self, ctx, i):
        fx, fy = self.targets[i]
        return ctx.w * fx, ctx.top + (ctx.h - ctx.top) * fy

    def update(self, ctx, pos, dt):
        now = time.perf_counter()
        if pos is not None and ctx.pointer.tracked:
            self.trail.append((now, pos[0], pos[1]))
        while self.trail and now - self.trail[0][0] > 4.0:
            self.trail.popleft()

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        if ev.button == LEFT:
            b = hit(self.buttons, ev.pos)
            if b is not None:
                b.activate(ctx)
            elif self.k < len(self.targets):
                tx, ty = self._tpos(ctx, self.k)
                self.errors.append(float(math.hypot(ev.pos[0] - tx, ev.pos[1] - ty)))
                self.k += 1
                if self.k == len(self.targets):
                    ctx.toast("Mean error %.1f px" % np.mean(self.errors), 4.0)
            return True
        ctx.nav.back()
        return True

    def status(self, ctx):
        if self.k < len(self.targets):
            return f"Aim at target {self.k + 1}/{len(self.targets)} and press NEXT"
        return "Done - Restart to measure again"

    def render(self, ctx, canvas, pos):
        s = ctx.scale
        canvas.clear()
        step = max(60, int(100 * s))
        for x in range(0, ctx.w, step):                       # ruler grid
            canvas.rect(x, ctx.top, x + 1, ctx.h, theme.LINE, 0.35)
            canvas.text(str(int(x / 1)), x + 4, ctx.top + 4, 13 * s, theme.TEXT_DIM, False, "lt")
        for y in range(ctx.top, ctx.h, step):
            canvas.rect(0, y, ctx.w, y + 1, theme.LINE, 0.35)
            canvas.text(str(int(y)), 4, y + 4, 13 * s, theme.TEXT_DIM, False, "lt")
        now = time.perf_counter()
        pts = [(t, x, y) for t, x, y in self.trail]
        for (t0, x0, y0), (t1, x1, y1) in zip(pts[:-1], pts[1:]):
            age = (now - t1) / 4.0
            canvas.line((x0, y0), (x1, y1), theme.lerp(theme.CYAN, theme.VIOLET, min(1, age)), 5 * s, 1 - 0.85 * age)
        for i in range(len(self.targets)):
            tx, ty = self._tpos(ctx, i)
            if i < self.k:
                col = theme.GOOD
                canvas.ring((tx, ty), 26 * s, 3, col, 0.9)
                canvas.text("%.0f px" % self.errors[i], tx, ty + 52 * s, 22 * s, col, True, "cm")
            elif i == self.k:
                p = 1 + 0.12 * math.sin(now * 5)
                canvas.ring((tx, ty), 40 * s * p, 4, theme.WHITE, 0.95)
                canvas.ring((tx, ty), 16 * s, 3, theme.AMBER, 1)
                canvas.line((tx - 60 * s, ty), (tx + 60 * s, ty), theme.WHITE, 2, 0.6)
                canvas.line((tx, ty - 60 * s), (tx, ty + 60 * s), theme.WHITE, 2, 0.6)
            else:
                canvas.ring((tx, ty), 20 * s, 2, theme.PANEL_LIGHT)
        if pos is not None:                                    # cross-hair + coordinates
            canvas.line((pos[0], ctx.top), (pos[0], ctx.h), theme.CYAN, 1.5, 0.35)
            canvas.line((0, pos[1]), (ctx.w, pos[1]), theme.CYAN, 1.5, 0.35)
        panel(canvas, ctx.w - 470 * s, ctx.top + 24 * s, ctx.w - 24 * s, ctx.top + 220 * s, 22 * s, theme.CYAN)
        px = "%4d, %4d" % pos if pos else "-"
        canvas.text("POINTER (board px)", ctx.w - 447 * s, ctx.top + 56 * s, 16 * s, theme.TEXT_DIM, True, "lm")
        canvas.text(px, ctx.w - 447 * s, ctx.top + 112 * s, 52 * s, theme.TEXT, True, "lm")
        src = ctx.source
        canvas.text("camera %.0f fps   pipeline %.1f ms" % (getattr(src, "fps", 0.0), getattr(src, "latency_ms", 0.0)),
                    ctx.w - 447 * s, ctx.top + 170 * s, 20 * s, theme.TEXT_DIM, False, "lm")
        if self.errors:
            canvas.text("mean error %.1f px" % np.mean(self.errors), ctx.w - 447 * s, ctx.top + 198 * s, 20 * s,
                        theme.GOOD, True, "lm")
        panel(canvas, ctx.sc(14), ctx.h - ctx.sc(112), ctx.sc(580), ctx.h - ctx.sc(14), ctx.sc(22), shadow=False)
        self.draw_buttons(canvas, pos)
