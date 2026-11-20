"""SCREEN: image display + zoom (uses features/image_viewer.py)."""
from __future__ import annotations

from ..events import ClickEvent, LEFT
from ..graphics import theme
from ..graphics.panels import panel
from ..graphics.widgets import hit
from .base import Screen


class ImageScreen(Screen):
    title = "Images"

    def __init__(self):
        super().__init__()
        self._last = None

    def layout(self, ctx):
        self.buttons = []
        v = ctx.viewer
        self.bar_h = ctx.sc(112)
        y0, y1 = ctx.h - self.bar_h + ctx.sc(18), ctx.h - ctx.sc(18)
        specs = [("Zoom -", "minus", lambda c: v.zoom_out()), ("Zoom +", "plus", lambda c: v.zoom_in()),
                 ("Original", "reset", lambda c: (v.reset_view(), c.toast("Original view"))),
                 ("Prev", "left", lambda c: v.next(-1)), ("Next", "right", lambda c: v.next(1)),
                 ("Menu", "back", lambda c: c.nav.back())]
        gap = ctx.sc(16)
        bw = (ctx.w - gap * (len(specs) + 1) - ctx.sc(40)) // len(specs)
        for i, (lab, ic, act) in enumerate(specs):
            x = ctx.sc(20) + gap + i * (bw + gap)
            self.make_button(ctx, (x, y0, x + bw, y1), lab, act, icon=ic, font=0.7 * ctx.scale,
                             accent=theme.SLATE if lab == "Menu" else theme.SKY)

    def _in_view(self, ctx, pos):
        return pos is not None and ctx.top <= pos[1] < ctx.h - self.bar_h

    def update(self, ctx, pos, dt):
        v = ctx.viewer
        if v.panning and self._in_view(ctx, pos):
            if self._last is not None:
                v.pan_by(pos[0] - self._last[0], pos[1] - self._last[1], ctx.w, ctx.h - ctx.top - self.bar_h)
            self._last = pos
        else:
            self._last = None

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        v = ctx.viewer
        if ev.button == LEFT:
            b = hit(self.buttons, ev.pos)
            if b is not None:
                b.activate(ctx)
            elif self._in_view(ctx, ev.pos) and v.img is not None:
                v.panning = not v.panning       # click toggles "grab the image"
                self._last = ev.pos if v.panning else None
                ctx.toast("Move the pointer to pan - click to release" if v.panning else "Released", 1.5)
            return True
        if v.panning:
            v.panning = False
            return True
        ctx.nav.back()
        return True

    def status(self, ctx):
        v = ctx.viewer
        return f"{v.name}   -   zoom x{v.zoom:.2f}{'   -   PANNING (NEXT = release)' if v.panning else '   -   NEXT on the image = grab and pan'}"

    def render(self, ctx, canvas, pos):
        v = ctx.viewer
        canvas.clear()
        vh = ctx.h - ctx.top - self.bar_h
        if v.img is None:
            canvas.text("No images found in assets/images", ctx.w / 2, ctx.h / 2, 36 * ctx.scale,
                        theme.TEXT_DIM, False, "cm")
        else:
            view = v.render(ctx.w, vh, theme.rgb(10, 14, 32), fast=v.panning)
            canvas.blit(view, 0, ctx.top)
            if v.panning:
                canvas.rrect(ctx.sc(6), ctx.top + ctx.sc(6), ctx.w - ctx.sc(6), ctx.h - self.bar_h - ctx.sc(6),
                             ctx.sc(14), theme.CYAN, 0.9, None, 3)
            # zoom badge
            s = ctx.scale
            canvas.rrect(ctx.w - 210 * s, ctx.top + 22 * s, ctx.w - 26 * s, ctx.top + 76 * s, 27 * s, theme.PANEL, 0.92)
            canvas.text("x%.2f" % v.zoom, ctx.w - 118 * s, ctx.top + 49 * s, 28 * s, theme.CYAN, True, "cm")
        panel(canvas, ctx.sc(14), ctx.h - self.bar_h + ctx.sc(4), ctx.w - ctx.sc(14), ctx.h - ctx.sc(8),
              ctx.sc(26), shadow=False)
        self.draw_buttons(canvas, pos)
