"""SCREEN: calibration (camera image -> board coordinates).

Procedure (shown on screen):
  1. Targets (a 3x3 grid, or the 4 corners) appear at known board positions.
  2. Point the red dot at the centre of each target and press NEXT (left click)
     - or just hold the dot still for ~1 s: it is captured automatically.
     The camera position of the dot is stored.  (Alternative: click the
     dot in the operator's camera window with the mouse.)
  3. The homography H (camera -> board) and, with 9 points, the lens
     distortion k1 are estimated.
  4. Validation: a few NEW targets appear; point again.  The mean error in
     board pixels is displayed.  LEFT = accept & save, RIGHT = redo.
"""
from __future__ import annotations

import math
import time

import numpy as np

from ..events import ClickEvent, LEFT, RIGHT
from ..graphics import theme
from ..graphics.panels import panel
from ..vision.calibration import calibration_targets
from .base import Screen

COLLECT, VALIDATE, RESULT = "collect", "validate", "result"
CORNER_NAMES = ["top-left", "top-centre", "top-right", "middle-left", "centre", "middle-right",
                "bottom-left", "bottom-centre", "bottom-right"]
CORNER_NAMES_4 = ["top-left", "top-right", "bottom-right", "bottom-left"]


class CalibrationScreen(Screen):
    title = "Calibration"
    show_bar = False

    def on_enter(self, ctx):
        self.state = COLLECT
        n = 9 if ctx.cfg.calibration.points >= 9 else 4
        self.names = CORNER_NAMES if n == 9 else CORNER_NAMES_4
        self.targets = calibration_targets(ctx.w, ctx.h, ctx.cfg.calibration.target_margin, n)
        self.cam_pts = []
        self.val_targets = self._validation_targets(ctx)
        self.val_errors = []
        self.mean_err = 0.0
        self.buttons = []
        self._dwell = 0.0
        self._anchor = None

    def _validation_targets(self, ctx):
        pts = [(0.35, 0.35), (0.65, 0.65), (0.25, 0.7), (0.75, 0.3), (0.5, 0.2)]
        n = max(1, min(len(pts), ctx.cfg.calibration.validation_points))
        return np.array([[ctx.w * x, ctx.h * y] for x, y in pts[:n]], float)

    # ---- actions -------------------------------------------------------------------------------------
    def _capture_cam(self, ctx):
        p = ctx.pointer
        return p.cam if (p.tracked and p.cam is not None) else None

    def update(self, ctx, pos, dt):
        if self.state == COLLECT and ctx.manual_cam_click is not None:
            pt, ctx.manual_cam_click = ctx.manual_cam_click, None
            self._add_cam_point(ctx, pt)
            return
        cfg = ctx.cfg.calibration
        if cfg.dwell_s <= 0 or self.state == RESULT:
            return
        # dwell capture: the dot stays within dwell_px of where it was for dwell_s seconds
        p = ctx.pointer
        cur = p.cam if (p.tracked and p.cam is not None) else None
        if cur is None:
            self._dwell, self._anchor = 0.0, None
            return
        if self._anchor is None or math.hypot(cur[0] - self._anchor[0], cur[1] - self._anchor[1]) > cfg.dwell_px:
            self._anchor, self._dwell = cur, 0.0
        else:
            self._dwell += dt
            if self._dwell >= cfg.dwell_s:
                self._dwell, self._anchor = -1.0, None          # -1: wait for the dot to move before the next capture
                self._capture(ctx)
        if self._dwell < 0 and self._anchor is None:
            self._anchor = cur

    def _capture(self, ctx):
        if self.state == COLLECT:
            pt = self._capture_cam(ctx)
            if pt is not None:
                self._add_cam_point(ctx, pt)
        elif self.state == VALIDATE and ctx.pointer.board is not None and ctx.pointer.tracked:
            self._add_validation(ctx)

    def _add_cam_point(self, ctx, pt):
        self.cam_pts.append(tuple(pt))
        if len(self.cam_pts) == len(self.targets):
            ctx.calib.fit(self.cam_pts, self.targets, ctx.cfg.calibration.estimate_distortion)
            ctx.source.refresh_roi()
            self.state = VALIDATE
            k = ctx.calib.k1
            ctx.toast("Calibration computed" + (f" (lens k1 = {k:+.3f})" if k else "") + " - now validate", 3.5)

    def _add_validation(self, ctx):
        tgt = self.val_targets[len(self.val_errors)]
        bx, by = ctx.pointer.board
        self.val_errors.append(float(np.hypot(bx - tgt[0], by - tgt[1])))
        if len(self.val_errors) == len(self.val_targets):
            self.mean_err = float(np.mean(self.val_errors))
            self.state = RESULT

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        if self.state == COLLECT:
            if ev.button == LEFT:
                pt = self._capture_cam(ctx)
                if pt is None:
                    ctx.toast(ctx.pointer_name.capitalize() + " not detected - aim at the target", 2.0)
                else:
                    self._add_cam_point(ctx, pt)
            elif self.cam_pts:
                self.cam_pts.pop()                   # RIGHT = undo the last point
            elif ctx.calib.calibrated:
                ctx.nav.back()                       # keep the previous calibration
            return True

        if self.state == VALIDATE:
            if ev.button == RIGHT:
                self.on_enter(ctx)                   # restart from scratch
                return True
            if ctx.pointer.board is None or not ctx.pointer.tracked:
                ctx.toast(ctx.pointer_name.capitalize() + " not detected", 2.0)
                return True
            self._add_validation(ctx)
            return True

        # RESULT
        if ev.button == LEFT:
            ctx.calib.save(ctx.calib_path)
            ctx.toast("Calibration saved", 2.0)
            ctx.nav.back()
        else:
            self.on_enter(ctx)
        return True

    # ---- drawing ---------------------------------------------------------------------------------------
    def status(self, ctx):
        return ""

    def _target(self, ctx, canvas, p, color, label="", dwell=0.0):
        s = ctx.scale
        now = time.perf_counter()
        pulse = 1.0 + 0.12 * math.sin(now * 5)
        canvas.glow(p, 90 * s, color, 0.25)
        canvas.ring(p, 34 * s * pulse, max(2.5, 4 * s), color)
        canvas.ring(p, 13 * s, max(2, 3 * s), color)
        canvas.line((p[0] - 54 * s, p[1]), (p[0] + 54 * s, p[1]), color, max(2, 2 * s), 0.8)
        canvas.line((p[0], p[1] - 54 * s), (p[0], p[1] + 54 * s), color, max(2, 2 * s), 0.8)
        if dwell > 0:                                         # filling ring = auto-capture progress
            n = 40
            k = min(1.0, dwell)
            pts = [(p[0] + 46 * s * math.cos(-math.pi / 2 + 2 * math.pi * k * i / n),
                    p[1] + 46 * s * math.sin(-math.pi / 2 + 2 * math.pi * k * i / n)) for i in range(n + 1)]
            for a, b in zip(pts[:-1], pts[1:]):
                canvas.line(a, b, theme.GOOD, 7 * s)
        if label:
            canvas.text(label, p[0], p[1] + 84 * s, 22 * s, color, True, "cm")

    def _card(self, ctx, canvas, tgt, title, lines, color=theme.CYAN):
        """Instruction card, placed in the half of the screen away from the current target."""
        s = ctx.scale
        cw, ch = 980 * s, 210 * s
        cy = ctx.h * 0.74 if (tgt is None or tgt[1] < ctx.h * 0.5) else ctx.h * 0.26
        x0, y0 = (ctx.w - cw) / 2, cy - ch / 2
        panel(canvas, x0, y0, x0 + cw, y0 + ch, 26 * s, color)
        canvas.text(title, ctx.w / 2, y0 + 52 * s, 38 * s, color, True, "cm")
        for i, (txt, col) in enumerate(lines):
            canvas.text(txt, ctx.w / 2, y0 + (108 + 40 * i) * s, 24 * s, col, i == 0, "cm")

    def render(self, ctx, canvas, pos):
        s, cx, cy = ctx.scale, ctx.w / 2, ctx.h / 2
        canvas.clear()
        t = max(2, int(6 * s))                                # frame = outline of the projected area
        for r in ((0, 0, ctx.w, t), (0, ctx.h - t, ctx.w, ctx.h), (0, 0, t, ctx.h), (ctx.w - t, 0, ctx.w, ctx.h)):
            canvas.rect(*r, theme.CYAN, 0.9)
        tracked = ctx.pointer.tracked
        dwell = max(0.0, self._dwell) / max(ctx.cfg.calibration.dwell_s, 1e-3) if ctx.cfg.calibration.dwell_s > 0 else 0.0

        if self.state == COLLECT:
            k = len(self.cam_pts)
            for i, tp in enumerate(self.targets):
                if i < k:
                    self._target(ctx, canvas, tp, theme.GOOD, "OK")
                elif i == k:
                    self._target(ctx, canvas, tp, theme.WHITE, f"{i + 1}/{len(self.targets)}  {self.names[i]}", dwell)
                else:
                    canvas.ring(tp, 20 * s, 2, theme.PANEL_LIGHT)
            self._card(ctx, canvas, self.targets[min(k, len(self.targets) - 1)],
                       f"CALIBRATION   {k + 1}/{len(self.targets)}",
                       [(f"Point your {ctx.pointer_name} at the target and press NEXT  (or hold still for 1 s)", theme.TEXT),
                        ("PREV = undo last point      or click the pointer in the camera window", theme.TEXT_DIM),
                        (f"{ctx.pointer_name} detected" if tracked else f"{ctx.pointer_name} NOT detected", theme.GOOD if tracked else theme.WARN)])
        elif self.state == VALIDATE:
            k = len(self.val_errors)
            for i, tp in enumerate(self.val_targets):
                if i < k:
                    self._target(ctx, canvas, tp, theme.GOOD, f"{self.val_errors[i]:.0f} px")
                elif i == k:
                    self._target(ctx, canvas, tp, theme.WHITE, f"check {i + 1}/{len(self.val_targets)}", dwell)
            self._card(ctx, canvas, self.val_targets[min(k, len(self.val_targets) - 1)], "VALIDATION",
                       [("Point at the new target and press NEXT   (PREV = redo calibration)", theme.TEXT),
                        ("the error of each check is shown in board pixels", theme.TEXT_DIM)])
        else:
            ok = self.mean_err <= ctx.cfg.calibration.ok_error_px
            col = theme.GOOD if ok else theme.WARN
            k1 = ctx.calib.k1
            self._card(ctx, canvas, None, "CALIBRATION RESULT",
                       [(f"mean error {self.mean_err:.1f} px  -  {'good' if ok else 'poor, consider redoing'}"
                         + (f"   -   lens k1 {k1:+.3f}" if k1 else ""), col),
                        ("NEXT = accept and save        PREV = redo", theme.TEXT)], col)
