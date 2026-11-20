"""SCREEN: calibration (camera image -> board coordinates).

Procedure (shown on screen):
  1. Four targets appear at known board positions (TL, TR, BR, BL).
  2. Point the red dot at the centre of each target, press NEXT (left click).
     The camera position of the dot is stored.  (Alternative: click the
     target's dot directly in the operator's camera window with the mouse.)
  3. The homography H (camera -> board) is estimated from the 4 pairs.
  4. Validation: a few NEW targets appear; point and click again.  The mean
     error in board pixels is displayed.  LEFT = accept & save, RIGHT = redo.
"""
from __future__ import annotations

import time

import numpy as np

from ..events import ClickEvent, LEFT, RIGHT
from ..graphics import theme
from ..vision.calibration import calibration_targets
from .base import Screen

COLLECT, VALIDATE, RESULT = "collect", "validate", "result"
CORNER_NAMES = ["top-left", "top-right", "bottom-right", "bottom-left"]


class CalibrationScreen(Screen):
    title = "Calibration"
    show_bar = False

    def on_enter(self, ctx):
        self.state = COLLECT
        self.targets = calibration_targets(ctx.w, ctx.h, ctx.cfg.calibration.target_margin)
        self.cam_pts = []
        self.val_targets = self._validation_targets(ctx)
        self.val_errors = []
        self.mean_err = 0.0
        self.buttons = []

    def _validation_targets(self, ctx):
        pts = [(0.5, 0.5), (0.3, 0.7), (0.7, 0.3), (0.25, 0.3), (0.75, 0.7)]
        n = max(1, min(len(pts), ctx.cfg.calibration.validation_points))
        return np.array([[ctx.w * x, ctx.h * y] for x, y in pts[:n]], float)

    # ---- actions -------------------------------------------------------------------------------------
    def _capture_cam(self, ctx, manual=None):
        if manual is not None:
            return manual
        p = ctx.pointer
        if p.tracked and p.cam is not None:
            return p.cam
        return None

    def update(self, ctx, pos, dt):
        if self.state == COLLECT and ctx.manual_cam_click is not None:
            pt, ctx.manual_cam_click = ctx.manual_cam_click, None
            self._add_cam_point(ctx, pt)

    def _add_cam_point(self, ctx, pt):
        self.cam_pts.append(tuple(pt))
        if len(self.cam_pts) == 4:
            ctx.calib.fit(self.cam_pts, self.targets)
            ctx.source.refresh_roi()
            self.state = VALIDATE
            ctx.toast("Calibration computed - now validate", 3.0)

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        if self.state == COLLECT:
            if ev.button == LEFT:
                pt = self._capture_cam(ctx)
                if pt is None:
                    ctx.toast("Red dot not detected - aim at the target", 2.0)
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
                ctx.toast("Red dot not detected", 2.0)
                return True
            tgt = self.val_targets[len(self.val_errors)]
            bx, by = ctx.pointer.board
            self.val_errors.append(float(np.hypot(bx - tgt[0], by - tgt[1])))
            if len(self.val_errors) == len(self.val_targets):
                self.mean_err = float(np.mean(self.val_errors))
                self.state = RESULT
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

    def _target(self, ctx, canvas, p, color, label=""):
        s = ctx.scale
        pulse = 1.0 + 0.15 * np.sin(time.perf_counter() * 5)
        canvas.ring(p, 34 * s * pulse, max(2, 4 * s), color)
        canvas.ring(p, 14 * s, max(2, 3 * s), color)
        canvas.line((p[0] - 50 * s, p[1]), (p[0] + 50 * s, p[1]), color, max(2, 2 * s))
        canvas.line((p[0], p[1] - 50 * s), (p[0], p[1] + 50 * s), color, max(2, 2 * s))
        if label:
            canvas.text(label, p[0], p[1] + 80 * s, 0.7 * s, color, 2, "cm")

    def render(self, ctx, canvas, pos):
        s, cx, cy = ctx.scale, ctx.w / 2, ctx.h / 2
        canvas.clear(theme.BG)
        canvas.rect(0, 0, ctx.w, ctx.sc(6), theme.ACCENT)           # outline of the projected area
        canvas.rect(0, ctx.h - ctx.sc(6), ctx.w, ctx.h, theme.ACCENT)
        canvas.rect(0, 0, ctx.sc(6), ctx.h, theme.ACCENT)
        canvas.rect(ctx.w - ctx.sc(6), 0, ctx.w, ctx.h, theme.ACCENT)

        if self.state == COLLECT:
            for i, t in enumerate(self.targets):
                if i < len(self.cam_pts):
                    self._target(ctx, canvas, t, theme.GOOD, "OK")
                elif i == len(self.cam_pts):
                    self._target(ctx, canvas, t, theme.WHITE, f"{i + 1}/4  {CORNER_NAMES[i]}")
                else:
                    canvas.ring(t, 20 * s, 2, theme.PANEL_LIGHT)
            canvas.text("CALIBRATION", cx, cy - 90 * s, 1.4 * s, theme.ACCENT, 3, "cm")
            canvas.text(f"Point the red dot at the target {len(self.cam_pts) + 1}/4 and press NEXT (left click)",
                        cx, cy - 20 * s, 0.9 * s, theme.TEXT, 2, "cm")
            canvas.text("RIGHT click = undo last point   |   or click the dot in the camera window",
                        cx, cy + 30 * s, 0.65 * s, theme.TEXT_DIM, 1, "cm")
            if not ctx.pointer.tracked:
                canvas.text("red dot not detected", cx, cy + 90 * s, 0.8 * s, theme.WARN, 2, "cm")

        elif self.state == VALIDATE:
            k = len(self.val_errors)
            for i, t in enumerate(self.val_targets):
                if i < k:
                    self._target(ctx, canvas, t, theme.GOOD, f"{self.val_errors[i]:.0f} px")
                elif i == k:
                    self._target(ctx, canvas, t, theme.WHITE, f"check {i + 1}/{len(self.val_targets)}")
            canvas.text("VALIDATION", cx, cy - 190 * s, 1.2 * s, theme.ACCENT, 3, "cm")
            canvas.text("Point at the target and press NEXT   (RIGHT = redo calibration)",
                        cx, cy - 140 * s, 0.7 * s, theme.TEXT, 2, "cm")
        else:
            ok = self.mean_err <= ctx.cfg.calibration.ok_error_px
            col = theme.GOOD if ok else theme.WARN
            canvas.text("CALIBRATION RESULT", cx, cy - 100 * s, 1.3 * s, theme.ACCENT, 3, "cm")
            canvas.text(f"mean error: {self.mean_err:.1f} px  ({'good' if ok else 'poor - consider redoing'})",
                        cx, cy - 30 * s, 1.0 * s, col, 2, "cm")
            canvas.text("LEFT click = accept and save      RIGHT click = redo", cx, cy + 40 * s,
                        0.8 * s, theme.TEXT, 2, "cm")

        # pointer feedback is drawn by the HUD cursor (board coords exist once calibrated)
