"""SCREEN: object drag & drop (uses features/objects.py)."""
from __future__ import annotations

import time

from ..events import ClickEvent, LEFT
from ..graphics import theme
from ..graphics.panels import panel
from ..graphics.widgets import hit
from .base import Screen


class ObjectsScreen(Screen):
    title = "Drag & drop - sort the shapes"

    def layout(self, ctx):
        self.buttons = []
        bar = ctx.sc(110)
        y0, y1 = ctx.h - bar + ctx.sc(16), ctx.h - ctx.sc(16)
        gap, bw = ctx.sc(20), ctx.sc(320)
        self.make_button(ctx, (gap, y0, gap + bw, y1), "Reset objects", lambda c: c.scene.reset(), icon="reset",
                         accent=theme.AMBER)
        self.make_button(ctx, (2 * gap + bw, y0, 2 * gap + 2 * bw, y1), "Menu", lambda c: c.nav.back(), icon="back",
                         accent=theme.SLATE)
        self.bar = bar

    def on_exit(self, ctx):
        ctx.scene.grabbed = None

    def update(self, ctx, pos, dt):
        ctx.scene.move(pos)

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        if ev.button == LEFT:
            b = hit(self.buttons, ev.pos)
            if b is not None:
                b.activate(ctx)
                return True
            msg = ctx.scene.click(ev.pos)
            if msg:
                ctx.toast(msg, 1.8)
            if ctx.scene.solved():
                ctx.toast("All shapes sorted - well done!", 3.0)
            return True
        if ctx.scene.grabbed is not None:        # RIGHT: cancel the grab
            s = ctx.scene.grabbed
            s.x, s.y = s.home
            ctx.scene.grabbed = None
            return True
        ctx.nav.back()
        return True

    def status(self, ctx):
        return "NEXT = grab / drop      PREV = cancel / back"

    def render(self, ctx, canvas, pos):
        sc, s = ctx.scene, ctx.scale
        canvas.clear()
        g = sc.grabbed
        for z in sc.zones:
            x0, y0, x1, y1 = z.rect
            over = g is not None and x0 <= g.x < x1 and y0 <= g.y < y1
            done = any(o is not g and o.kind == z.kind and x0 <= o.x < x1 and y0 <= o.y < y1 for o in sc.shapes)
            acc = theme.GOOD if done else (theme.CYAN if over else None)
            panel(canvas, x0, y0, x1, y1, 22 * s, acc, shadow=False)
            canvas.text(z.label, (x0 + x1) / 2, y1 - 30 * s, 26 * s, theme.GOOD if done else theme.TEXT_DIM, True, "cm")
        canvas.text("Drop each shape in the box with its name", ctx.w / 2, ctx.top + 44 * s, 28 * s, theme.TEXT_DIM, False, "cm")
        for sh in sc.shapes:
            sh.draw(canvas.img, grabbed=(sh is g), scale=1.0 if sh is not g else 1.08)
        panel(canvas, ctx.sc(14), ctx.h - self.bar + ctx.sc(2), ctx.w - ctx.sc(14), ctx.h - ctx.sc(8), ctx.sc(26),
              shadow=False)
        self.draw_buttons(canvas, pos)
