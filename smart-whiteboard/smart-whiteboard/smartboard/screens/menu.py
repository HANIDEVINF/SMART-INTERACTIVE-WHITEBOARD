"""FEATURE: interactive menus + submenus (generic, driven by a MenuItem tree)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Union

from ..events import ClickEvent, LEFT, RIGHT
from ..graphics import theme
from .base import Screen

Label = Union[str, Callable[[], str]]


@dataclass
class MenuItem:
    label: Label
    action: Optional[Callable] = None            # action(ctx) for a leaf
    children: Optional[List["MenuItem"]] = None  # submenu
    hint: str = ""

    def text(self, ctx=None) -> str:
        """Labels may be functions of the context (toggles show ON/OFF)."""
        return self.label(ctx) if callable(self.label) else self.label


class MenuScreen(Screen):
    def __init__(self, root: MenuItem):
        super().__init__()
        self.root = root
        self.path: List[MenuItem] = []
        self.title = "Main menu"
        self._hints = {}

    @property
    def node(self) -> MenuItem:
        return self.path[-1] if self.path else self.root

    def go_root(self, ctx):
        self.path = []
        self.layout(ctx)

    # ---- layout: a centred grid of big cards -------------------------------------------------
    def layout(self, ctx):
        self.buttons, self._hints = [], {}
        items = list(self.node.children or [])
        if self.path:
            items.append(MenuItem("< Back", action=lambda c: self.up(c)))
        n = len(items)
        cols = 3 if n > 4 else max(1, n)
        rows = (n + cols - 1) // cols
        gap = ctx.sc(36)
        cw = min(ctx.sc(480), (ctx.w - gap * (cols + 1)) // cols)
        area_top, area_h = ctx.top, ctx.h - ctx.top
        ch = min(ctx.sc(240), (area_h - gap * (rows + 1) - ctx.sc(80)) // rows)
        total_w = cols * cw + (cols - 1) * gap
        total_h = rows * ch + (rows - 1) * gap
        x0 = (ctx.w - total_w) // 2
        y0 = area_top + ctx.sc(60) + (area_h - ctx.sc(60) - total_h) // 2
        for i, it in enumerate(items):
            r, c = divmod(i, cols)
            x, y = x0 + c * (cw + gap), y0 + r * (ch + gap)
            lab = (lambda it=it: it.text(ctx) + ("  >" if it.children else ""))
            b = self.make_button(ctx, (x, y, x + cw, y + ch), lab,
                                 lambda c_, it=it: self.select(c_, it), font=1.1 * ctx.scale)
            self._hints[id(b)] = it.hint
        self.title = "  >  ".join(["Main menu"] + [p.text(ctx) for p in self.path])

    # ---- navigation -------------------------------------------------------------------------------
    def select(self, ctx, item: MenuItem):
        if item.children:
            self.path.append(item)
        elif item.action:
            item.action(ctx)
        if ctx.nav.current is self:           # an action may have pushed another screen
            self.layout(ctx)

    def up(self, ctx):
        if self.path:
            self.path.pop()
            self.layout(ctx)
        else:
            ctx.toast("Already at the main menu")

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        if ev.button == RIGHT:                # RIGHT click = back one level
            self.up(ctx)
            return True
        return super().on_click(ctx, ev)

    def on_enter(self, ctx):
        self.layout(ctx)                      # labels (ON/OFF) may have changed

    def status(self, ctx):
        return "LEFT click = select    RIGHT click = back"

    # ---- drawing ------------------------------------------------------------------------------------
    def render(self, ctx, canvas, pos):
        canvas.clear(theme.BG)
        self.draw_buttons(canvas, pos)
        for b in self.buttons:
            h = self._hints.get(id(b))
            if h:
                x0, y0, x1, y1 = b.rect
                canvas.text(h, (x0 + x1) / 2, y1 - ctx.sc(34), 0.55 * ctx.scale, theme.TEXT_DIM, 1, "cm")
