"""Settings screen: adjust every configurable value.

Two columns of grouped rows.  Each row shows a label, the current value
and [-] / [+] buttons: numeric settings step up/down, choice settings
cycle through their options.  Changes are saved immediately to
config/settings.json.  Settings marked with (R) are read at start-up and
need *Restart app* to take effect; everything else applies live.
"""

from __future__ import annotations

import pygame

from config.settings import save_settings
from interface.components import (Button, COLORS, FONT_MB, FONT_S, PAD, Screen)

DISPLAY_PRESETS = [(1280, 720), (1600, 900), (1920, 1080)]


class SettingRow:
    """One configurable row: label + value + [-] [+] buttons."""

    def __init__(self, rect, label, get_value, apply_value, step=None,
                 options=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.get_value = get_value
        self.apply_value = apply_value
        self.step = step                # numeric step (None -> cycle options)
        self.options = options          # list of values for cycling
        h = self.rect.h - 6
        bw = max(40, min(64, h * 2))
        self.btn_plus = Button(self.rect.right - bw - 4, self.rect.y + 3, bw, h,
                               "+", on_click=lambda: self._change(+1),
                               font=FONT_MB, style="secondary")
        self.btn_minus = Button(self.rect.right - 2 * bw - 12, self.rect.y + 3,
                                bw, h, "-", on_click=lambda: self._change(-1),
                                font=FONT_MB, style="secondary")
        self.value_right = self.btn_minus.rect.left - 12

    def _change(self, direction: int) -> None:
        if self.options is not None:
            opts = self.options
            cur = self.get_value()
            idx = opts.index(cur) if cur in opts else 0
            self.apply_value(opts[(idx + direction) % len(opts)])
        else:
            self.apply_value(self.get_value() + direction * self.step)

    @property
    def buttons(self):
        return [self.btn_minus, self.btn_plus]

    def draw(self, surface):
        pygame.draw.rect(surface, COLORS["panel"], self.rect, border_radius=10)
        surface.blit(FONT_S.render(self.label, True, COLORS["text"]),
                     (self.rect.x + 14,
                      self.rect.centery - FONT_S.get_height() // 2))
        value = self.get_value()
        text = f"{value:.2f}" if isinstance(value, float) else str(value)
        v = FONT_S.render(text, True, COLORS["accent"])
        surface.blit(v, (self.value_right - v.get_width(),
                         self.rect.centery - v.get_height() // 2))


class SettingsScreen(Screen):
    title = "Settings"
    subtitle = "(R) = needs Restart app"
    has_toolbar = True

    def __init__(self, app):
        super().__init__(app)
        self.settings = app.settings
        s = self.settings

        def num(key, step, lo, hi):
            def get():
                return s[key]

            def apply(v):
                v = max(lo, min(hi, v))
                s[key] = round(v, 4) if isinstance(v, float) else int(v)
                self._persist()
            return get, apply, step

        def cyc(key, options):
            def get():
                return s[key]

            def apply(v):
                s[key] = v
                self._persist()
            return get, apply, options

        def hsv(key, step, lo, hi):
            def get():
                return s["marker_hsv"][key]

            def apply(v):
                s["marker_hsv"][key] = round(max(lo, min(hi, v)), 4)
                self._persist()
                self.app.detector.update_ranges(s["marker_hsv"])
            return get, apply, step

        def preset():
            opts = [f"{w}x{h}" for w, h in DISPLAY_PRESETS]

            def get():
                cur = f"{s['display_width']}x{s['display_height']}"
                return cur if cur in opts else opts[0]

            def apply(v):
                w, h = v.split("x")
                s["display_width"], s["display_height"] = int(w), int(h)
                self._persist()
            return get, apply, opts

        def fullscreen():
            def get():
                return "On" if s.get("fullscreen") else "Off"

            def apply(v):
                s["fullscreen"] = (v == "On")
                self._persist()
            return get, apply, ["Off", "On"]

        # (group title, [(label, getter, setter, step-or-options)])
        left = [
            ("Camera and pointer", [
                ("Camera source (R)", *cyc("camera_source", ["real", "simulated"])),
                ("Camera index (R)", *num("camera_index", 1, 0, 4)),
                ("Pointer mode", *cyc("pointer_mode", ["auto", "camera", "mouse"])),
                ("Remote mode (R)", *cyc("remote_mode",
                                         ["auto", "physical", "keyboard"])),
            ]),
            ("Tracking", [
                ("Smoothing (alpha)", *num("tracking_alpha", 0.05, 0.1, 0.95)),
                ("Max jump (px)", *num("tracking_max_jump", 25, 20, 1000)),
                ("Loss timeout (s)", *num("tracking_loss_timeout", 0.25, 0.2, 5.0)),
                ("Marker min area (px2)", *num("marker_min_area", 50, 20, 5000)),
            ]),
        ]
        right = [
            ("Marker colour (HSV)", [
                ("Hue min (deg)", *hsv("h_min", 5, 0, 360)),
                ("Hue max (deg)", *hsv("h_max", 5, 0, 360)),
                ("Saturation min", *hsv("s_min", 0.05, 0, 1)),
                ("Saturation max", *hsv("s_max", 0.05, 0, 1)),
                ("Value min", *hsv("v_min", 0.05, 0, 1)),
                ("Value max", *hsv("v_max", 0.05, 0, 1)),
            ]),
            ("Display", [
                ("Window size (R)", *preset()),
                ("Fullscreen (R)", *fullscreen()),
            ]),
        ]
        # One shared row height so both columns line up; sized so the tallest
        # column (headers + rows) exactly fits between header and toolbar.
        entries = max(sum(1 + len(items) for _, items in g)
                      for g in (left, right))
        self.unit = max(26, min(54, (self.body_rect.h - 8) // entries))
        self.columns = [self._build_column(0, left), self._build_column(1, right)]
        self.rows = [r for col in self.columns for r in col["rows"]]

        # Toolbar: shortcuts + restart.
        tb = self.toolbar_row_rect()
        bw = min(250, (tb.w - 2 * 16) // 3)
        self.btn_hsv = Button(tb.x, tb.y, bw, tb.h, "Marker colour...",
                              on_click=lambda: app.go_to("hsv_calib"),
                              style="secondary", font=FONT_S)
        self.btn_board = Button(tb.x + bw + 16, tb.y, bw, tb.h,
                                "Board calibration...",
                                on_click=lambda: app.go_to("calibration"),
                                style="secondary", font=FONT_S)
        self.btn_restart = Button(tb.right - bw, tb.y, bw, tb.h, "Restart app",
                                  on_click=app.request_restart,
                                  style="danger", font=FONT_S)
        self.buttons = [self.btn_hsv, self.btn_board, self.btn_restart]
        for r in self.rows:
            self.buttons.extend(r.buttons)

    # -- layout ------------------------------------------------------------

    def _build_column(self, col, groups):
        body = self.body_rect
        gap = 16
        col_w = (self.w - 2 * PAD - gap) // 2
        x = PAD + col * (col_w + gap)
        unit = self.unit
        y = body.y + 6
        rows, headers = [], []
        for title, items in groups:
            headers.append((title, pygame.Rect(x + 4, y, col_w, unit)))
            y += unit
            for label, get, apply, step_or_opts in items:
                rect = pygame.Rect(x, y, col_w, unit - 2)
                if isinstance(step_or_opts, list):
                    rows.append(SettingRow(rect, label, get, apply,
                                           options=step_or_opts))
                else:
                    rows.append(SettingRow(rect, label, get, apply,
                                           step=step_or_opts))
                y += unit
        return {"rows": rows, "headers": headers}

    def _persist(self):
        # Apply tracking parameters live.
        self.app.tracker.configure(
            alpha=self.settings.get("tracking_alpha"),
            max_jump=self.settings.get("tracking_max_jump"),
            loss_timeout=self.settings.get("tracking_loss_timeout"))
        self.app.detector.min_area = int(self.settings.get("marker_min_area", 400))
        save_settings(self.settings)

    # -- rendering ---------------------------------------------------------

    def draw_body(self, s):
        for col in self.columns:
            for title, rect in col["headers"]:
                s.blit(FONT_MB.render(title, True, COLORS["warn"]),
                       (rect.x, rect.centery - FONT_MB.get_height() // 2))
            for row in col["rows"]:
                row.draw(s)
