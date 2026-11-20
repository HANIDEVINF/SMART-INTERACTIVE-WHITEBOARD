"""FEATURE: interactive menus + submenus (generic, driven by a MenuItem tree)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Union

from ..events import ClickEvent, LEFT, RIGHT
from ..graphics import theme
from .base import Screen

Label = Union[str, Callable[[], str]]
ORBS = ((0.12, 0.25, 0.55, theme.SKY), (0.9, 0.8, 0.6, theme.VIOLET), (0.6, 0.05, 0.35, theme.CYAN))


@dataclass
class MenuItem:
    label: Label
    action: Optional[Callable] = None            # action(ctx) for a leaf
    children: Optional[List["MenuItem"]] = None  # submenu
    hint: str = ""
    icon: str = "star"

    def text(self, ctx=None) -> str:
        """Labels may be functions of the context (toggles show ON/OFF)."""
        return self.label(ctx) if callable(self.label) else self.label


class MenuScreen(Screen):
    def __init__(self, root: MenuItem):
        super().__init__()
        self.root = root
        self.path: List[MenuItem] = []
        self.title = "Main menu"

    @property
    def node(self) -> MenuItem:
        return self.path[-1] if self.path else self.root

    def go_root(self, ctx):
        self.path = []
        self.layout(ctx)

    # ---- layout: a centred grid of big cards -------------------------------------------------
    def layout(self, ctx):
        self.buttons = []
        items = list(self.node.children or [])
        if self.path:
            items.append(MenuItem("Back", action=lambda c: self.up(c), hint="previous menu", icon="back"))
        n = len(items)
        cols = 3 if n > 4 else max(1, n)
        rows = (n + cols - 1) // cols
        gap = ctx.sc(40)
        head = ctx.sc(150)                                   # room for the hero title
        cw = min(ctx.sc(540), (ctx.w - gap * (cols + 1)) // cols)
        area_h = ctx.h - ctx.top - head
        ch = min(ctx.sc(270), (area_h - gap * (rows + 1)) // rows)
        total_w = cols * cw + (cols - 1) * gap
        total_h = rows * ch + (rows - 1) * gap
        x0 = (ctx.w - total_w) // 2
        y0 = ctx.top + head + (area_h - total_h) // 2
        for i, it in enumerate(items):
            r, c = divmod(i, cols)
            x, y = x0 + c * (cw + gap), y0 + r * (ch + gap)
            acc = theme.CARD_ACCENTS[i % len(theme.CARD_ACCENTS)] if not (self.path and i == n - 1) else theme.SLATE
            lab = (lambda it=it: it.text(ctx))
            self.make_button(ctx, (x, y, x + cw, y + ch), lab, lambda c_, it=it: self.select(c_, it),
                             icon=("chevron" if False else it.icon), accent=acc, kind="card",
                             hint=it.hint + ("   >" if it.children else ""), font=0.9 * ctx.scale)
        self.title = "  >  ".join(["Main menu"] + [p.text(ctx) for p in self.path])
        self._head_y = ctx.top + ctx.sc(86)

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
        return "NEXT = select      PREV = back one level"

    # ---- drawing ------------------------------------------------------------------------------------
    def render(self, ctx, canvas, pos):
        canvas.clear(orbs=ORBS)
        s = ctx.scale
        if self.path:
            canvas.text(self.path[-1].text(ctx), ctx.w / 2, self._head_y - 16 * s, 58 * s, theme.TEXT, True, "cm")
            canvas.text("Choose an option", ctx.w / 2, self._head_y + 36 * s, 24 * s, theme.TEXT_DIM, False, "cm")
        else:
            canvas.text("Smart Interactive Whiteboard", ctx.w / 2, self._head_y - 16 * s, 58 * s, theme.TEXT, True, "cm")
            canvas.text("Point with the red dot   -   NEXT button = click   -   PREV button = back",
                        ctx.w / 2, self._head_y + 36 * s, 24 * s, theme.TEXT_DIM, False, "cm")
        self.draw_buttons(canvas, pos)
