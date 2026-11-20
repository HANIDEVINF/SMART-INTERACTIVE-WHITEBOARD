"""SCREEN: object drag & drop (uses features/objects.py)."""
from __future__ import annotations

from ..events import ClickEvent, LEFT
from ..graphics import theme
from ..graphics.widgets import hit
from .base import Screen


class ObjectsScreen(Screen):
    title = "Drag & drop - sort the shapes"

    def layout(self, ctx):
        self.buttons = []
        bar = ctx.sc(90)
        y0, y1 = ctx.h - bar + ctx.sc(12), ctx.h - ctx.sc(12)
        gap, bw = ctx.sc(16), ctx.sc(300)
        self.make_button(ctx, (gap, y0, gap + bw, y1), "Reset objects", lambda c: c.scene.reset())
        self.make_button(ctx, (2 * gap + bw, y0, 2 * gap + 2 * bw, y1), "< Menu", lambda c: c.nav.back())
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
        return "LEFT = grab / drop    RIGHT = cancel / back"

    def render(self, ctx, canvas, pos):
        sc = ctx.scene
        canvas.clear(theme.BG)
        for z in sc.zones:
            x0, y0, x1, y1 = z.rect
            canvas.rrect(x0, y0, x1, y1, 16, theme.PANEL)
            canvas.outline(x0, y0, x1, y1, theme.PANEL_LIGHT, 3)
            canvas.text(z.label, (x0 + x1) / 2, y1 - ctx.sc(26), 0.8 * ctx.scale, theme.TEXT_DIM, 2, "cm")
        for s in sc.shapes:
            s.draw(canvas.img, grabbed=(s is sc.grabbed))
        canvas.rect(0, ctx.h - self.bar, ctx.w, ctx.h, theme.PANEL)
        self.draw_buttons(canvas, pos)
