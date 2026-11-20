"""Reusable UI widgets: Button (+ hit-testing helper)."""
from __future__ import annotations

from typing import Callable, Optional, Sequence, Tuple, Union

from . import theme

Label = Union[str, Callable[[], str]]


class Button:
    """Rectangle that can be selected with a left click.

    label    : text or a function returning the text (for toggles)
    action   : callable(ctx) executed on selection
    selected : optional predicate -> highlight (current colour / size ...)
    swatch   : fill colour (colour pickers)
    """

    def __init__(self, rect: Tuple[int, int, int, int], label: Label = "",
                 action: Optional[Callable] = None, selected: Optional[Callable[[], bool]] = None,
                 swatch=None, font: float = 0.8, enabled: Optional[Callable[[], bool]] = None):
        self.rect = rect
        self.label = label
        self.action = action
        self.selected = selected
        self.swatch = swatch
        self.font = font
        self.enabled = enabled

    def text(self) -> str:
        return self.label() if callable(self.label) else self.label

    def contains(self, x: float, y: float) -> bool:
        x0, y0, x1, y1 = self.rect
        return x0 <= x < x1 and y0 <= y < y1

    def is_enabled(self) -> bool:
        return self.enabled is None or self.enabled()

    def activate(self, ctx) -> None:
        if self.action and self.is_enabled():
            self.action(ctx)

    def draw(self, canvas, hovered: bool = False) -> None:
        x0, y0, x1, y1 = self.rect
        sel = self.selected() if self.selected else False
        if self.swatch is not None:
            canvas.rrect(x0, y0, x1, y1, 12, theme.PANEL_LIGHT)
            canvas.rrect(x0 + 6, y0 + 6, x1 - 6, y1 - 6, 8, self.swatch)
        else:
            col = theme.BUTTON_ACTIVE if sel else (theme.BUTTON_HOVER if hovered else theme.BUTTON)
            if not self.is_enabled():
                col = theme.PANEL
            canvas.rrect(x0, y0, x1, y1, 14, col)
            txt_col = theme.TEXT if self.is_enabled() else theme.TEXT_DIM
            canvas.text(self.text(), (x0 + x1) / 2, (y0 + y1) / 2, self.font, txt_col, 2, "cm")
        if hovered and self.is_enabled():
            canvas.outline(x0, y0, x1, y1, theme.WHITE, 3)
        elif sel and self.swatch is not None:
            canvas.outline(x0, y0, x1, y1, theme.ACCENT, 4)


def hit(buttons: Sequence[Button], pos) -> Optional[Button]:
    if pos is None:
        return None
    for b in reversed(buttons):
        if b.contains(*pos):
            return b
    return None
