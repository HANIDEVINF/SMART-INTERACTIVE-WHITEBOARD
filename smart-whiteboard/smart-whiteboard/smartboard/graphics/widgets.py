"""Reusable UI widgets: Button (+ hit-testing helper).

Every look of a button (normal / hover / selected / disabled) is rendered
once into a sprite (graphics/sprite.py) and cached, so drawing a whole
screen of buttons costs a few blits.  Hovering glides smoothly (anim.Glide).
"""
from __future__ import annotations

import time
from typing import Callable, Dict, Optional, Sequence, Tuple, Union

from . import icons, theme
from .anim import Glide
from .sprite import Sprite, render_sprite
from .text import get_text

Label = Union[str, Callable[[], str]]
HIT_MARGIN = 10          # px: forgiving hit-test (a hand-held dot is never perfectly steady)

_SPRITES: Dict[tuple, Sprite] = {}


def _sprite(key, w, h, pad, draw) -> Sprite:
    s = _SPRITES.get(key)
    if s is None:
        if len(_SPRITES) > 400:
            _SPRITES.clear()
        s = _SPRITES[key] = render_sprite(w, h, draw, pad)
    return s


class Button:
    """Rectangle that can be selected with a left click.

    kind     : "card" (big menu tile) | "tool" (icon + label) | "pill" | "swatch" | "icon"
    label    : text or a function returning the text (for toggles)
    action   : callable(ctx) executed on selection
    selected : optional predicate -> highlighted (current colour / tool ...)
    swatch   : fill colour (colour pickers)
    """

    def __init__(self, rect: Tuple[int, int, int, int], label: Label = "",
                 action: Optional[Callable] = None, selected: Optional[Callable[[], bool]] = None,
                 swatch=None, font: float = 0.8, enabled: Optional[Callable[[], bool]] = None,
                 icon: Optional[str] = None, accent=None, kind: str = "tool", hint: str = ""):
        self.rect = tuple(int(v) for v in rect)
        self.label = label
        self.action = action
        self.selected = selected
        self.swatch = swatch
        self.font = font
        self.enabled = enabled
        self.icon = icon
        self.accent = accent or theme.ACCENT
        self.kind = "swatch" if swatch is not None and kind == "tool" else kind
        self.hint = hint
        self._glide = Glide(0.0, 16.0)
        self._t = time.perf_counter()

    # ---- behaviour ------------------------------------------------------------------------
    def text(self) -> str:
        return self.label() if callable(self.label) else self.label

    def contains(self, x: float, y: float, margin: int = 0) -> bool:
        x0, y0, x1, y1 = self.rect
        return x0 - margin <= x < x1 + margin and y0 - margin <= y < y1 + margin

    def is_enabled(self) -> bool:
        return self.enabled is None or self.enabled()

    def activate(self, ctx) -> None:
        if self.action and self.is_enabled():
            self.action(ctx)

    # ---- look -----------------------------------------------------------------------------
    def _look(self, state: str):
        """Return (sprite, pad) for the current state."""
        x0, y0, x1, y1 = self.rect
        w, h = x1 - x0, y1 - y0
        txt, ic, k = self.text(), self.icon, self.kind
        fs = max(12, int(self.font * 30))
        acc, sw = self.accent, self.swatch
        key = (k, w, h, state, txt, ic, acc, sw, fs, self.hint)
        pad = 26 if k == "card" else 10
        hov, sel, dis = state == "hover", state == "selected", state == "disabled"

        def draw(cv, ox, oy):
            r = min(h / 2.0, 26 if k == "card" else 14)
            if k == "swatch":
                cv.rrect(ox, oy, ox + w, oy + h, 14, theme.PANEL_LIGHT)
                cv.rrect(ox + 6, oy + 6, ox + w - 6, oy + h - 6, 9, sw)
                if sel:
                    cv.rrect(ox - 3, oy - 3, ox + w + 3, oy + h + 3, 16, theme.WHITE, 1.0, None, 3)
                elif hov:
                    cv.rrect(ox, oy, ox + w, oy + h, 14, theme.WHITE, 1.0, None, 2)
                return
            if k == "card":
                cv.shadow(ox, oy, ox + w, oy + h, r, 12, 10, 0.34)
            top, bot = (theme.CARD_HOVER_TOP, theme.CARD_HOVER_BOT) if hov else (theme.CARD_TOP, theme.CARD_BOT)
            if sel:
                top, bot = theme.lerp(theme.PANEL, acc, 0.85), theme.lerp(theme.PANEL, acc, 0.55)
            if dis:
                top, bot = theme.PANEL, theme.PANEL
            cv.rrect(ox, oy, ox + w, oy + h, r, top, 1.0, bot)
            cv.rrect(ox, oy, ox + w, oy + h, r, acc if (hov or sel) else theme.LINE, 0.9 if (hov or sel) else 0.8,
                     None, 2.5 if hov else 1.6)
            fg = theme.TEXT_DIM if dis else (theme.BG if sel else theme.TEXT)
            if k == "card":
                chip = int(min(w, h) * 0.34)
                cx, cy = ox + 34 + chip // 2, oy + 30 + chip // 2
                cv.circle((cx, cy), chip / 2, acc, 0.22 if not hov else 0.38)
                cv.ring((cx, cy), chip / 2, 2, acc, 0.9)
                if ic:
                    icons.draw(cv, ic, cx, cy, chip * 0.52, acc if not hov else theme.WHITE)
                cv.text_fit(txt, ox + 34, oy + h - 36 - (fs if self.hint else 0) * 0.9, fs * 1.35, w - 68,
                            theme.TEXT, True, "lb")
                if self.hint:
                    cv.text_fit(self.hint, ox + 34, oy + h - 26, fs * 0.72, w - 68, theme.TEXT_DIM, False, "lb")
                return
            # tool / pill / icon : [icon] label
            tw = cv.text_size(txt, fs, True)[0] if txt else 0
            isz = int(min(h * 0.52, 44)) if ic else 0
            gap = int(h * 0.18) if (ic and txt) else 0
            total = isz + gap + tw
            sx = ox + (w - total) / 2.0
            if ic:
                icons.draw(cv, ic, sx + isz / 2, oy + h / 2, isz, theme.BG if sel else (acc if not dis else fg))
            if txt:
                cv.text_fit(txt, sx + isz + gap, oy + h / 2, fs, w - isz - gap - 14, fg, True, "lm")

        spr = _sprite(key, w, h, pad, draw)
        return spr, pad

    def draw(self, canvas, hovered: bool = False) -> None:
        now = time.perf_counter()
        dt, self._t = min(now - self._t, 0.1), now
        en = self.is_enabled()
        sel = bool(self.selected()) if self.selected else False
        self._glide.target = 1.0 if (hovered and en) else 0.0
        g = self._glide.update(dt)
        x0, y0, _, _ = self.rect
        lift = -int(round(5 * g)) if self.kind == "card" else 0
        base = "disabled" if not en else ("selected" if sel else "normal")
        spr, _ = self._look(base)
        canvas.sprite(spr, x0, y0 + lift)
        if g > 0.02 and en and not sel:
            hov, _ = self._look("hover")
            canvas.sprite(hov, x0, y0 + lift, min(1.0, g))


def hit(buttons: Sequence[Button], pos, margin: int = HIT_MARGIN) -> Optional[Button]:
    """Button under ``pos``.  Exact containment wins; otherwise the nearest button within
    ``margin`` px (so that a jittery hand-held dot still selects what it is aiming at)."""
    if pos is None:
        return None
    for b in reversed(buttons):
        if b.contains(pos[0], pos[1]):
            return b
    best, bd = None, 1e9
    for b in buttons:
        if b.contains(pos[0], pos[1], margin):
            x0, y0, x1, y1 = b.rect
            d = ((x0 + x1) / 2 - pos[0]) ** 2 + ((y0 + y1) / 2 - pos[1]) ** 2
            if d < bd:
                best, bd = b, d
    return best
