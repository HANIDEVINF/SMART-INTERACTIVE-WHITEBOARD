"""SCREEN: free drawing (uses features/drawing.py)."""
from __future__ import annotations

from ..events import ClickEvent, LEFT, RIGHT
from ..graphics import theme
from ..graphics.widgets import hit
from .base import Screen


class DrawScreen(Screen):
    title = "Free drawing"

    def layout(self, ctx):
        self.buttons = []
        d, s = ctx.drawing, ctx.scale
        x0, y = ctx.sc(12), ctx.top + ctx.sc(14)
        bw, bh, gap = ctx.sc(80), ctx.sc(56), ctx.sc(8)
        full = 2 * bw + gap
        for i, (name, col) in enumerate(theme.PEN_COLORS):
            cx, cy = x0 + (i % 2) * (bw + gap), y + (i // 2) * (bh + gap)
            self.make_button(ctx, (cx, cy, cx + bw, cy + bh), name, lambda c, i=i: d.set_color(i),
                             selected=lambda i=i: d.color_idx == i and not d.eraser, swatch=col)
        y += 3 * (bh + gap) + gap
        for i, (name, _) in enumerate(theme.PEN_SIZES):
            self.make_button(ctx, (x0, y, x0 + full, y + bh), name, lambda c, i=i: d.set_size(i),
                             selected=lambda i=i: d.size_idx == i)
            y += bh + gap
        y += gap
        self.make_button(ctx, (x0, y, x0 + full, y + bh), "Eraser", lambda c: d.set_eraser(not d.eraser),
                         selected=lambda: d.eraser)
        y += bh + gap
        self.make_button(ctx, (x0, y, x0 + full, y + bh), "Undo", lambda c: d.undo())
        y += bh + gap
        self.make_button(ctx, (x0, y, x0 + full, y + bh), "Clear", lambda c: (d.clear(), c.toast("Drawing cleared")))
        y += bh + gap
        self.make_button(ctx, (x0, y, x0 + full, y + bh), "< Menu", lambda c: c.nav.back())
        self.tb_w = x0 * 2 + full

    def on_exit(self, ctx):
        ctx.drawing.lift()

    def _on_canvas(self, ctx, pos) -> bool:
        return pos is not None and pos[0] > self.tb_w and pos[1] > ctx.top

    def update(self, ctx, pos, dt):
        d = ctx.drawing
        if d.pen_down and not self._on_canvas(ctx, pos):
            d.lift()                       # pointer left the drawing area: lift the pen
        elif d.pen_down:
            d.move(pos)

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        d = ctx.drawing
        if ev.button == LEFT:
            b = hit(self.buttons, ev.pos)
            if b is not None:
                b.activate(ctx)
            elif self._on_canvas(ctx, ev.pos):
                d.toggle_pen(ev.pos)
                ctx.toast("Pen DOWN - move to draw" if d.pen_down else "Pen UP", 1.2)
            return True
        # RIGHT: lift the pen if drawing, otherwise leave
        if d.pen_down:
            d.lift()
            ctx.toast("Pen UP", 1.0)
        else:
            ctx.nav.back()
        return True

    def status(self, ctx):
        d = ctx.drawing
        return f"Pen {'DOWN' if d.pen_down else 'UP'}  |  LEFT = pen down/up   RIGHT = lift / back"

    def render(self, ctx, canvas, pos):
        d = ctx.drawing
        canvas.clear(theme.BG)
        d.render_onto(canvas.img, ctx.top)
        canvas.rect(0, ctx.top, self.tb_w, ctx.h, theme.PANEL)
        self.draw_buttons(canvas, pos)
        if self._on_canvas(ctx, pos):          # pen preview under the pointer
            col = theme.WHITE if d.eraser else d.color
            if d.pen_down:
                canvas.circle(pos, d.radius, col)
            else:
                canvas.ring(pos, d.radius + 2, 2, col)
