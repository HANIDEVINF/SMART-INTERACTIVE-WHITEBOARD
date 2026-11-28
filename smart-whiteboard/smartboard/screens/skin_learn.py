"""SCREEN: learn the skin colour (hand mode).

The teacher covers the lit square with the open hand and presses NEXT.  The camera pixels behind the
square are used to fit the Cr / Cb skin ranges (vision/skin.py: percentiles), so the detector works
with this person's skin under this projector's light.
"""
from __future__ import annotations

import numpy as np

from ..config import save_config
from ..events import ClickEvent, LEFT
from ..graphics import theme
from ..graphics.panels import panel
from ..vision import skin
from .base import Screen


class SkinLearnScreen(Screen):
    title = "Learn skin colour"

    def layout(self, ctx):
        self.buttons = []
        self.make_button(ctx, (ctx.sc(30), ctx.h - ctx.sc(100), ctx.sc(270), ctx.h - ctx.sc(30)), "Cancel",
                         lambda c: c.nav.back(), icon="back", accent=theme.SLATE, font=0.7 * ctx.scale)

    def _box(self, ctx):
        cx, cy, hw, hh = ctx.w / 2, ctx.h / 2, ctx.w * 0.10, ctx.h * 0.17
        return cx - hw, cy - hh, cx + hw, cy + hh

    def _cam_box(self, ctx):
        x0, y0, x1, y1 = self._box(ctx)
        pts = np.array([ctx.calib.board_to_cam(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])
        c = pts.mean(axis=0)
        pts = c + (pts - c) * 0.7                       # stay well inside the hand
        return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()

    def learn(self, ctx):
        frame = getattr(ctx.source, "last_frame", None)
        if frame is None:
            ctx.toast("No camera image", 2.0)
            return
        res = skin.learn_skin(frame, self._cam_box(ctx))
        if res is None:
            ctx.toast("Not enough hand pixels - cover the whole square", 3.0)
            return
        for k, v in res.items():
            setattr(ctx.cfg.detection, k, v)
        if ctx.cfg_path:
            save_config(ctx.cfg, ctx.cfg_path)
        ctx.toast("Skin colour learned (Cr %.0f-%.0f, Cb %.0f-%.0f)" % (res["skin_cr_min"], res["skin_cr_max"],
                                                                     res["skin_cb_min"], res["skin_cb_max"]), 4.0)
        ctx.nav.back()

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        if ev.button == LEFT:
            for b in self.buttons:
                if b.contains(ev.pos[0], ev.pos[1], 10):
                    b.activate(ctx)
                    return True
            self.learn(ctx)
        else:
            ctx.nav.back()
        return True

    def status(self, ctx):
        return "Cover the square with your open hand, then press NEXT"

    def render(self, ctx, canvas, pos):
        s = ctx.scale
        canvas.clear()
        x0, y0, x1, y1 = self._box(ctx)
        canvas.glow(((x0 + x1) / 2, (y0 + y1) / 2), 420 * s, theme.SKY, 0.35)
        canvas.rrect(x0, y0, x1, y1, 30 * s, theme.rgb(150, 160, 190))      # mid-grey light, like the usual UI
        canvas.rrect(x0 - 8, y0 - 8, x1 + 8, y1 + 8, 34 * s, theme.CYAN, 0.9, None, 4)
        canvas.text("Open hand here", (x0 + x1) / 2, y0 - 44 * s, 34 * s, theme.TEXT, True, "cm")
        panel(canvas, ctx.w / 2 - 520 * s, y1 + 70 * s, ctx.w / 2 + 520 * s, y1 + 200 * s, 24 * s, theme.CYAN)
        canvas.text("Cover the whole square with your open hand, fingers together", ctx.w / 2, y1 + 112 * s, 28 * s,
                    theme.TEXT, True, "cm")
        canvas.text("then press NEXT   -   PREV = cancel", ctx.w / 2, y1 + 160 * s, 24 * s, theme.TEXT_DIM, False, "cm")
        self.draw_buttons(canvas, pos)
