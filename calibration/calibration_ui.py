"""Calibration screens (Pygame).

Two screens live here:

* ``BoardCalibrationScreen`` -- the teacher clicks the four corners of the
  physical whiteboard on the live camera image; the app computes and saves
  the camera->board homography.
* ``HSVCalibrationScreen`` -- the teacher places the marker in front of
  the camera and the app samples its colour to auto-tune the HSV
  thresholds.

Both screens display the live camera feed inside a panel.  Clicks on the
panel are converted back to camera pixel coordinates using the panel's
scale factor, so the calibration points are in the same coordinate system
as the detector output.

These screens accept the *real mouse* regardless of the pointer mode
(``raw_mouse``): calibration is an operator task done on the laptop, and
it must work even when the camera pointer is already active.
"""

from __future__ import annotations

import logging

import numpy as np
import pygame

from detection.color_detector import ColorDetector
from interface.components import (Button, COLORS, FONT_MB, FONT_S, PAD, Screen,
                                  fit_surface, layout_row)
from utils.image_processing import bgr_to_hsv

logger = logging.getLogger(__name__)

CORNER_LABELS = ["1 Top-left", "2 Top-right", "3 Bottom-right", "4 Bottom-left"]


def _frame_to_surface(frame: np.ndarray) -> pygame.Surface:
    """BGR NumPy frame -> Pygame surface (RGB), scaled by caller."""
    rgb = cv2_bgr_to_rgb(frame)
    return pygame.image.frombuffer(rgb.tobytes(), rgb.shape[1::-1], "RGB")


def cv2_bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    return frame[:, :, ::-1].copy()


class _CameraPanelScreen(Screen):
    """Base class: shows the camera feed fitted into a panel rect."""

    has_toolbar = True
    raw_mouse = True

    def __init__(self, app):
        super().__init__(app)
        body = self.body_rect
        self.strip = pygame.Rect(PAD, body.y + 8, self.w - 2 * PAD, 40)
        self.panel = pygame.Rect(PAD, self.strip.bottom + 8, self.w - 2 * PAD,
                                 body.bottom - self.strip.bottom - 16)
        self._cam_surf: pygame.Surface | None = None
        self._img_rect = pygame.Rect(0, 0, 0, 0)   # where the image is drawn
        self._cam_scale = 1.0
        self._shown_id = -1
        self._frame_shape = None                    # (h, w) of the camera

    # -- camera frame handling --------------------------------------------

    def _update_camera_surface(self):
        frame, frame_id = self.app.camera.read_latest()
        if frame is None:
            self._cam_surf = None
            return
        if frame_id == self._shown_id and self._cam_surf is not None:
            return                              # nothing new to convert
        self._shown_id = frame_id
        surf = _frame_to_surface(frame)
        pw, ph = self.panel.w - 8, self.panel.h - 8
        scale = min(pw / surf.get_width(), ph / surf.get_height())
        size = (max(1, int(surf.get_width() * scale)),
                max(1, int(surf.get_height() * scale)))
        self._cam_surf = pygame.transform.smoothscale(surf, size)
        self._cam_scale = scale
        self._img_rect = self._cam_surf.get_rect(center=self.panel.center)
        self._frame_shape = frame.shape[:2]

    def _panel_to_camera(self, pos):
        """Convert a click inside the image to camera pixel coordinates."""
        if self._cam_surf is None or not self._img_rect.collidepoint(pos):
            return None
        return ((pos[0] - self._img_rect.x) / self._cam_scale,
                (pos[1] - self._img_rect.y) / self._cam_scale)

    def _camera_to_panel(self, x, y):
        return (self._img_rect.x + x * self._cam_scale,
                self._img_rect.y + y * self._cam_scale)

    def _draw_camera_panel(self, s):
        pygame.draw.rect(s, COLORS["panel"], self.panel, border_radius=10)
        if self._cam_surf is None:
            msg = FONT_MB.render("No camera frame available", True,
                                 COLORS["text_dim"])
            s.blit(msg, msg.get_rect(center=self.panel.center))
        else:
            s.blit(self._cam_surf, self._img_rect)
        pygame.draw.rect(s, COLORS["border"], self.panel, 2, border_radius=10)

    def _draw_detection(self, s, det, color, radius=16):
        if det is None or self._cam_surf is None:
            return
        px, py = self._camera_to_panel(det.x, det.y)
        pygame.draw.circle(s, (10, 12, 20), (int(px), int(py)), radius + 2, 5)
        pygame.draw.circle(s, color, (int(px), int(py)), radius, 3)

    def update(self, dt):
        super().update(dt)
        self._update_camera_surface()


class BoardCalibrationScreen(_CameraPanelScreen):
    """Four-corner board calibration."""

    title = "Board calibration"
    subtitle = "Click the 4 corners of the whiteboard on the camera image"

    def __init__(self, app):
        super().__init__(app)
        self.calib = app.calibration
        self._H = None
        self._result = ""
        self._result_ok = True

        rects = layout_row(self.toolbar_row_rect(), [170, 170, 190], gap=18,
                           align="right")
        self.btn_undo = Button(*rects[0], "Undo point", on_click=self._undo,
                               style="secondary", font=FONT_S)
        self.btn_reset = Button(*rects[1], "Reset", on_click=self._reset,
                                style="secondary", font=FONT_S)
        self.btn_save = Button(*rects[2], "Save calibration",
                               on_click=self._save, style="success",
                               font=FONT_S)
        self.buttons = [self.btn_undo, self.btn_reset, self.btn_save]

    def on_enter(self):
        # Show the saved calibration, if any.
        if self.app.calibration.mapper.is_calibrated and \
                len(self.calib.clicked_points) == 4:
            self._H = self.calib.mapper.H
            self._result, self._result_ok = "Saved calibration loaded.", True

    # -- interaction -------------------------------------------------------

    def on_body_click(self, pos):
        cam_pt = self._panel_to_camera(pos)
        if cam_pt is None:
            return False
        if len(self.calib.clicked_points) >= 4:      # a 5th click starts over
            self._reset()
        n = self.calib.add_click(cam_pt)
        if n == 4:
            self._H = self.calib.compute()
            if self._H is not None:
                self._result = "Transform computed. Press Save calibration."
                self._result_ok = True
            else:
                self._result = ("Invalid corners: " + self.calib.last_error
                                + ". Reset and retry.")
                self._result_ok = False
        return True

    def on_right_click(self, pos):
        # Right click = undo the last point; with none left, go back.
        if self.calib.clicked_points:
            self._undo()
        else:
            self.app.go_back()
        return True

    def _undo(self):
        self.calib.undo_click()
        self._H = None
        self._result = ""

    def _save(self):
        if self._H is not None and self.calib.save():
            self.app.calibration.load_saved()
            self.app.tracker.reset()
            self._result, self._result_ok = "Calibration saved.", True
            self.flash("Calibration saved")
        else:
            self._result = "Click 4 valid corners first."
            self._result_ok = False

    def _reset(self):
        self.calib.reset_clicks()
        self._H = None
        self._result = ""

    # -- frame -------------------------------------------------------------

    def update(self, dt):
        super().update(dt)
        self.btn_undo.enabled = bool(self.calib.clicked_points)
        self.btn_reset.enabled = bool(self.calib.clicked_points)
        self.btn_save.enabled = self._H is not None

    def draw_body(self, s):
        # Checklist chips.
        n = len(self.calib.clicked_points)
        chip_w = (self.strip.w - 3 * 10) // 4
        for i, label in enumerate(CORNER_LABELS):
            r = pygame.Rect(self.strip.x + i * (chip_w + 10), self.strip.y,
                            chip_w, self.strip.h)
            done, current = i < n, i == n
            fill = COLORS["accent"] if done else COLORS["panel"]
            pygame.draw.rect(s, fill, r, border_radius=10)
            pygame.draw.rect(s, COLORS["warn"] if current else COLORS["border"],
                             r, 3 if current else 2, border_radius=10)
            t = fit_surface(FONT_S.render(("OK  " if done else "") + label, True,
                                          COLORS["text"]), r.w - 10)
            s.blit(t, t.get_rect(center=r.center))

        self._draw_camera_panel(s)

        pts = self.calib.clicked_points
        px = [self._camera_to_panel(x, y) for x, y in pts]
        if len(px) >= 2:
            pygame.draw.lines(s, COLORS["accent"], len(px) == 4,
                              [(int(a), int(b)) for a, b in px], 3)
        for i, (x, y) in enumerate(px):
            pygame.draw.circle(s, (10, 12, 20), (int(x), int(y)), 14)
            pygame.draw.circle(s, COLORS["accent"], (int(x), int(y)), 12, 3)
            num = FONT_S.render(str(i + 1), True, COLORS["text"])
            s.blit(num, num.get_rect(center=(int(x), int(y))))

        # Live validation: where does the transform put the marker?
        det = self.app.last_detection
        mapper = self.calib.mapper
        if self._H is not None and det is not None and self._cam_surf is not None:
            self._draw_detection(s, det, COLORS["success"])
            bx, by = mapper.camera_to_board((det.x, det.y))
            self._caption(s, f"Marker -> board ({bx:.0f}, {by:.0f}) of "
                          f"{mapper.board_size[0]}x{mapper.board_size[1]}",
                          COLORS["success"], 0)
        if self._result:
            self._caption(s, self._result,
                          COLORS["success"] if self._result_ok else COLORS["danger"],
                          1)

    def _caption(self, s, text, color, row):
        t = fit_surface(FONT_S.render(text, True, color), self.panel.w - 32)
        box = pygame.Rect(0, 0, t.get_width() + 24, t.get_height() + 12)
        box.bottomleft = (self.panel.x + 14,
                          self.panel.bottom - 12 - row * (box.h + 6))
        pygame.draw.rect(s, (10, 12, 20), box, border_radius=10)
        s.blit(t, t.get_rect(center=box.center))


class HSVCalibrationScreen(_CameraPanelScreen):
    """Auto-tune the marker HSV thresholds by sampling the camera feed."""

    title = "Marker colour"
    subtitle = "Put the marker inside the yellow box, press Sample, then Apply"
    SAMPLE_SIZE = 41  # px, odd -> centred patch

    def __init__(self, app):
        super().__init__(app)
        rects = layout_row(self.toolbar_row_rect(), [170, 170], gap=18,
                           align="right")
        self.btn_sample = Button(*rects[0], "Sample", on_click=self._sample,
                                 style="secondary", font=FONT_S)
        self.btn_apply = Button(*rects[1], "Apply", on_click=self._apply,
                                style="success", font=FONT_S)
        self.buttons = [self.btn_sample, self.btn_apply]
        self._sampled = None
        self._sample_rgb = None
        self._test_detector = None
        self._test_det = None

    def on_right_click(self, pos):
        self.app.go_back()
        return True

    @staticmethod
    def ranges_from_patch(hsv_patch: np.ndarray) -> dict:
        """Derive HSV thresholds from a patch of marker pixels.

        Hue is an angle, so its mean is the *circular* mean and the range
        wraps around 0/360 (h_min > h_max) for red markers.  Saturation and
        value use the median, which ignores a few background pixels.
        """
        hue = np.deg2rad(hsv_patch[..., 0].ravel())
        mean_h = float(np.rad2deg(np.angle(np.exp(1j * hue).mean())) % 360.0)
        mean_s = float(np.median(hsv_patch[..., 1]))
        mean_v = float(np.median(hsv_patch[..., 2]))
        return {
            "h_min": (mean_h - 12.0) % 360.0,
            "h_max": (mean_h + 12.0) % 360.0,
            "s_min": max(0.05, mean_s - 0.25),
            "s_max": min(1.0, mean_s + 0.25),
            "v_min": max(0.10, mean_v - 0.30),
            "v_max": 1.0,
        }

    def _sample(self):
        """Sample a centred patch of the current frame."""
        frame = self.app.camera.read()
        if frame is None:
            self.flash("No camera frame")
            return
        hsv = bgr_to_hsv(frame)
        h_img, w_img = hsv.shape[:2]
        r = self.SAMPLE_SIZE // 2
        cy, cx = h_img // 2, w_img // 2
        patch = hsv[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1]
        self._sampled = self.ranges_from_patch(patch)
        bgr = frame[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1]
        self._sample_rgb = tuple(int(v) for v in bgr.reshape(-1, 3).mean(0)[::-1])
        self._test_detector = ColorDetector(
            self._sampled, min_area=int(self.app.settings.get("marker_min_area", 400)),
            max_area_ratio=float(self.app.settings.get("marker_max_area_ratio", 0.25)))
        self.flash("Sampled - check the yellow ring, then Apply")

    def _apply(self):
        if self._sampled is None:
            self.flash("Press Sample first")
            return
        from config.settings import save_settings
        self.app.settings["marker_hsv"] = dict(self._sampled)
        save_settings(self.app.settings)
        self.app.detector.update_ranges(self._sampled)
        self.flash("Marker colour applied and saved")

    def update(self, dt):
        super().update(dt)
        self.btn_apply.enabled = self._sampled is not None
        if self._test_detector is not None and self._cam_surf is not None:
            frame = self.app.camera.read()
            self._test_det = self._test_detector.detect(frame) \
                if frame is not None else None

    def draw_body(self, s):
        # Info strip: sampled colour + thresholds.
        pygame.draw.rect(s, COLORS["panel"], self.strip, border_radius=10)
        x = self.strip.x + 12
        if self._sampled:
            pygame.draw.circle(s, self._sample_rgb, (x + 14, self.strip.centery), 14)
            pygame.draw.circle(s, (255, 255, 255), (x + 14, self.strip.centery), 14, 2)
            q = self._sampled
            txt = (f"Hue {q['h_min']:.0f}-{q['h_max']:.0f}   "
                   f"Sat {q['s_min']:.2f}-{q['s_max']:.2f}   "
                   f"Val {q['v_min']:.2f}-{q['v_max']:.2f}")
            color = COLORS["text"]
            x += 36
        else:
            txt, color = "Not sampled yet", COLORS["text_dim"]
        s.blit(FONT_S.render(txt, True, color),
               (x, self.strip.centery - FONT_S.get_height() // 2))

        self._draw_camera_panel(s)

        # Sampling box in the centre of the camera image.
        if self._cam_surf is not None:
            half = max(4, int(self.SAMPLE_SIZE * self._cam_scale / 2))
            c = self._img_rect.center
            pygame.draw.rect(s, COLORS["warn"],
                             (c[0] - half, c[1] - half, 2 * half, 2 * half), 2)
            # Green ring: what the CURRENT thresholds detect.
            self._draw_detection(s, self.app.last_detection, COLORS["success"])
            # Yellow ring: what the SAMPLED thresholds would detect.
            self._draw_detection(s, self._test_det, COLORS["warn"], radius=24)
