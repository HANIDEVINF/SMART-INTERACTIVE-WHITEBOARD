"""SCREEN: image display + zoom (uses features/image_viewer.py)."""
from __future__ import annotations

from ..events import ClickEvent, LEFT
from ..graphics import theme
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
        self.bar_h = ctx.sc(100)
        y0, y1 = ctx.h - self.bar_h + ctx.sc(14), ctx.h - ctx.sc(14)
        specs = [("Zoom -", lambda c: v.zoom_out()), ("Zoom +", lambda c: v.zoom_in()),
                 ("Reset view", lambda c: (v.reset_view(), c.toast("Original view"))),
                 ("< Prev", lambda c: v.next(-1)), ("Next >", lambda c: v.next(1)),
                 ("< Menu", lambda c: c.nav.back())]
        gap = ctx.sc(14)
        bw = (ctx.w - gap * (len(specs) + 1)) // len(specs)
        for i, (lab, act) in enumerate(specs):
            x = gap + i * (bw + gap)
            self.make_button(ctx, (x, y0, x + bw, y1), lab, act)

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
        return f"{v.name}   zoom x{v.zoom:.2f}{'   [PANNING]' if v.panning else ''}"

    def render(self, ctx, canvas, pos):
        v = ctx.viewer
        canvas.clear(theme.BG)
        vh = ctx.h - ctx.top - self.bar_h
        if v.img is None:
            canvas.text("No images found in assets/images", ctx.w / 2, ctx.h / 2, 1.0 * ctx.scale,
                        theme.TEXT_DIM, 2, "cm")
        else:
            view = v.render(ctx.w, vh, theme.BG, fast=v.panning)
            canvas.blit(view, 0, ctx.top)
        canvas.rect(0, ctx.h - self.bar_h, ctx.w, ctx.h, theme.PANEL)
        self.draw_buttons(canvas, pos)
