"""Base class of every screen (one screen = one functionality)."""
from __future__ import annotations

from ..events import ClickEvent, LEFT
from ..graphics.widgets import Button, hit


class Screen:
    title = ""
    show_bar = True          # False: full-screen (calibration)

    def __init__(self):
        self.buttons = []

    # lifecycle ---------------------------------------------------------------------------
    def on_enter(self, ctx):
        self.layout(ctx)

    def on_exit(self, ctx):
        pass

    def layout(self, ctx):
        """(Re)build self.buttons - positions depend on ctx.scale."""

    # per-frame ---------------------------------------------------------------------------
    def update(self, ctx, pos, dt: float):
        """pos = pointer position in board px or None."""

    def status(self, ctx) -> str:
        return ""

    def render(self, ctx, canvas, pos):
        raise NotImplementedError

    # input -----------------------------------------------------------------------------------
    def on_click(self, ctx, ev: ClickEvent) -> bool:
        """Default: LEFT selects the button under the pointer, RIGHT goes back."""
        if ev.button == LEFT:
            b = hit(self.buttons, ev.pos)
            if b is not None:
                b.activate(ctx)
                return True
            return False
        ctx.nav.back()
        return True

    # helpers ------------------------------------------------------------------------------------
    def draw_buttons(self, canvas, pos):
        over = hit(self.buttons, pos)
        for b in self.buttons:
            b.draw(canvas, hovered=(b is over))

    def make_button(self, ctx, rect, label, action, **kw) -> Button:
        kw.setdefault("font", 0.7 * ctx.scale)
        b = Button(rect, label, action, **kw)
        self.buttons.append(b)
        return b
