"""Cached glass panels (toolbars, instruction cards): drawn once as sprites."""
from __future__ import annotations

from . import theme
from .sprite import render_sprite

_CACHE = {}


def panel(canvas, x0, y0, x1, y1, r=22, accent=None, shadow=True):
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    w, h = x1 - x0, y1 - y0
    if w < 4 or h < 4:
        return
    key = (w, h, int(r), accent, shadow)
    spr = _CACHE.get(key)
    if spr is None:
        if len(_CACHE) > 60:
            _CACHE.clear()

        def draw(cv, ox, oy):
            if shadow:
                cv.shadow(ox, oy, ox + w, oy + h, r, 20, 12, 0.35)
            cv.rrect(ox, oy, ox + w, oy + h, r, theme.rgb(26, 36, 78), 1.0, theme.rgb(14, 20, 46))
            cv.rrect(ox, oy, ox + w, oy + h, r, accent or theme.LINE, 0.85, None, 1.6)
        spr = _CACHE[key] = render_sprite(w, h, draw, 32 if shadow else 4)
    canvas.sprite(spr, x0, y0)


def label(canvas, text, x, y, size, color=theme.TEXT_DIM):
    """Small caps-like section label."""
    canvas.text(text.upper(), x, y, size, color, True, "lm")
