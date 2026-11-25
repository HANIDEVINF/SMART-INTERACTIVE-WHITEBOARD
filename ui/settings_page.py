"""Settings page: interactive HSV tuning panel + general options.

Detection tab
    * live camera view (click the marker to pick its colour) next to the binary-mask view
    * colour presets, sensitivity, six HSV sliders, blob-size / shape filter, tracking parameters
    * every change is applied to the running vision thread immediately and saved automatically
General tab
    * camera auto-start and requested resolution, pointer visibility, detection backend info,
      delete calibration, reset all settings
"""
from __future__ import annotations

import copy
import importlib.util
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget)

from core.detector import DetectionParams, hsv_range_from_sample, median_hsv_at
from core.settings import DEFAULTS, Settings
from core.tracker import TrackerParams
from core.vision_engine import VisionController, VisionResult
from ui.styles import ACCENT, ACCENT_SOFT, MUTED, TEXT
from ui.video_view import VideoView, draw_crosshair, draw_detection
from ui.widgets import ParamSlider, StatusRow

# name -> (hsv_low, hsv_high, sample colour). Hue is 0..179 (OpenCV); red wraps (low H > high H).
PRESETS = {
    "Green": ((35, 90, 70), (85, 255, 255), (60, 200, 200)),
    "Blue": ((95, 110, 70), (130, 255, 255), (112, 200, 200)),
    "Red": ((170, 120, 70), (10, 255, 255), (0, 200, 200)),
    "Yellow": ((20, 100, 110), (35, 255, 255), (27, 190, 220)),
    "Orange": ((8, 130, 120), (20, 255, 255), (14, 200, 220)),
    "Pink": ((140, 80, 90), (170, 255, 255), (155, 150, 220)),
}

RESOLUTIONS = [("640 x 480", 640, 480), ("1280 x 720 (recommended)", 1280, 720), ("1920 x 1080", 1920, 1080)]


def _dot_icon(color: QColor, size: int = 14) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(2, 2, size * 2 - 4, size * 2 - 4)
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


def _panel(title: str, hint: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("panel")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(18, 14, 18, 14)
    lay.setSpacing(8)
    label = QLabel(title)
    label.setObjectName("panelTitle")
    lay.addWidget(label)
    if hint:
        h = QLabel(hint)
        h.setObjectName("muted")
        h.setWordWrap(True)
        lay.addWidget(h)
    return frame


class SettingsPage(QWidget):
    message = Signal(str, str)               # (text, kind) -> toast
    pointerVisibilityChanged = Signal(bool)
    resetRequested = Signal()                # the main window performs the full reset
    dwellChanged = Signal(int)               # selection-mode dwell time (ms)

    def __init__(self, settings: Settings, controller: VisionController, remote=None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self.settings, self.ctl = settings, controller
        self.remote_panel = None
        self._last: VisionResult | None = None
        self._last_text = 0.0
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(10)
        title = QLabel("Settings")
        title.setObjectName("h2")
        root.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; }}"
            f"QTabBar::tab {{ padding: 8px 20px; margin-right: 6px; border-radius: 10px; font-weight: 700;"
            f" color: {MUTED}; background: transparent; }}"
            f"QTabBar::tab:selected {{ background: {ACCENT_SOFT}; color: {ACCENT}; }}"
            f"QTabBar::tab:hover:!selected {{ color: {TEXT}; }}")
        self.tabs.addTab(self._build_detection_tab(), "Detection")
        self.tabs.addTab(self._build_general_tab(), "General")
        self.remote_tab_index = -1
        if remote is not None:
            from ui.remote_panel import RemotePanel
            self.remote_panel = RemotePanel(settings, remote)
            self.remote_panel.message.connect(self.message)
            self.remote_panel.dwellChanged.connect(self.dwellChanged)
            self.remote_tab_index = self.tabs.addTab(self.remote_panel, "Remote && Pointer")
        self.tabs.currentChanged.connect(lambda _i: self._update_mask_demand())
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

        self.ctl.resultReady.connect(self._on_result)
        self.ctl.signalLost.connect(self._on_signal_lost)
        self.ctl.calibrationChanged.connect(self._refresh_general)
        self.load_from_controller()

    # =============================================================== lifecycle
    def activate(self) -> None:
        self._update_mask_demand()

    def show_remote_tab(self) -> None:
        if self.remote_tab_index >= 0:
            self.tabs.setCurrentIndex(self.remote_tab_index)

    def _on_tab_changed(self, index: int) -> None:
        if self.remote_panel is not None and index != self.remote_tab_index:
            self.remote_panel.deactivate()

    def deactivate(self) -> None:
        if self.remote_panel is not None:
            self.remote_panel.deactivate()
        self.ctl.set_want_mask(False)
        self.settings.save()

    def _update_mask_demand(self) -> None:
        self.ctl.set_want_mask(self.isVisible() and self.tabs.currentIndex() == 0)

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self._update_mask_demand()

    def hideEvent(self, e) -> None:  # noqa: N802
        super().hideEvent(e)
        self.ctl.set_want_mask(False)

    # =============================================================== detection tab
    def _build_detection_tab(self) -> QWidget:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 8, 0, 0)
        row.setSpacing(16)

        # ---- left: live + mask ---------------------------------------------------------
        left = QVBoxLayout()
        left.setSpacing(10)
        hint = QLabel("Hold your marker in front of the camera and click it in the live view to pick its colour. "
                      "The mask (right) must show the marker as one solid white blob and little else.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        left.addWidget(hint)
        views = QHBoxLayout()
        views.setSpacing(12)
        for caption, attr in (("Live camera", "live"), ("Binary mask", "mask")):
            col = QVBoxLayout()
            col.setSpacing(4)
            cap = QLabel(caption)
            cap.setObjectName("panelTitle")
            col.addWidget(cap)
            view = VideoView("Camera is not running.\nOpen the Camera page and press Start camera."
                             if attr == "live" else "Mask appears when the camera runs.", smooth=attr == "live")
            setattr(self, f"{attr}_view", view)
            col.addWidget(view, 1)
            views.addLayout(col, 1)
        self.live_view.set_overlay(self._live_overlay)
        self.mask_view.set_overlay(self._mask_overlay)
        self.live_view.clicked.connect(self._on_pick)
        left.addLayout(views, 1)

        status = _panel("Detection status")
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        self.r_det = StatusRow("Marker")
        self.r_pos = StatusRow("Centroid (camera px)")
        self.r_area = StatusRow("Area / confidence")
        self.r_fps = StatusRow("Tracking FPS")
        grid.addWidget(self.r_det, 0, 0)
        grid.addWidget(self.r_pos, 0, 1)
        grid.addWidget(self.r_area, 1, 0)
        grid.addWidget(self.r_fps, 1, 1)
        status.layout().addLayout(grid)
        self.det_message = QLabel("")
        self.det_message.setObjectName("muted")
        self.det_message.setWordWrap(True)
        status.layout().addWidget(self.det_message)
        left.addWidget(status)
        row.addLayout(left, 1)

        # ---- right: parameters (scrollable) ----------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(430)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        side = QVBoxLayout(inner)
        side.setContentsMargins(0, 0, 8, 0)
        side.setSpacing(12)
        scroll.setWidget(inner)
        row.addWidget(scroll)

        colour = _panel("Marker colour", "Pick a preset, or click the marker in the live view.")
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (name, (_lo, _hi, sample)) in enumerate(PRESETS.items()):
            btn = QPushButton(name)
            btn.setIcon(_dot_icon(QColor.fromHsv(sample[0] * 2 % 360, sample[1], sample[2])))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, n=name: self._apply_preset(n))
            grid.addWidget(btn, i // 3, i % 3)
        colour.layout().addLayout(grid)
        self.s_sens = ParamSlider("Sensitivity", 0, 100, 50, tooltip="How wide the colour window around the picked "
                                  "colour is. Higher = tolerates lighting changes but may catch other objects.")
        self.s_sens.valueChanged.connect(self._on_sensitivity)
        colour.layout().addWidget(self.s_sens)
        self.sample_label = QLabel("")
        self.sample_label.setObjectName("muted")
        colour.layout().addWidget(self.sample_label)
        side.addWidget(colour)

        hsv = _panel("HSV thresholds", "OpenCV scale: H 0-179, S and V 0-255. If H low > H high the hue range wraps "
                     "around 0 (red).")
        self.s_hl = ParamSlider("Hue low", 0, 179, 35)
        self.s_hh = ParamSlider("Hue high", 0, 179, 85)
        self.s_sl = ParamSlider("Saturation low", 0, 255, 90)
        self.s_sh = ParamSlider("Saturation high", 0, 255, 255)
        self.s_vl = ParamSlider("Value low", 0, 255, 70)
        self.s_vh = ParamSlider("Value high", 0, 255, 255)
        for s in (self.s_hl, self.s_hh, self.s_sl, self.s_sh, self.s_vl, self.s_vh):
            s.valueChanged.connect(self._on_detection_changed)
            hsv.layout().addWidget(s)
        side.addWidget(hsv)

        blob = _panel("Blob filter", "Areas are in camera pixels, so they do not depend on the processing size.")
        self.s_min = ParamSlider("Minimum area", 10, 5000, 150, tooltip="Smaller blobs are rejected as noise.")
        self.s_max = ParamSlider("Maximum area", 500, 100000, 40000, tooltip="Larger blobs (walls, clothes) are rejected.")
        self.s_kernel = ParamSlider("Kernel size", 1, 15, 5, tooltip="Structuring element of the morphological "
                                    "opening/closing (forced odd). Larger removes more noise but erodes small markers.")
        self.s_conf = ParamSlider("Validity threshold", 0, 1, 0.35, scale=100, fmt="{:.2f}",
                                  tooltip="Minimum shape confidence (how compact and blob-like the region is).")
        for s in (self.s_min, self.s_max, self.s_kernel, self.s_conf):
            s.valueChanged.connect(self._on_detection_changed)
            blob.layout().addWidget(s)
        side.addWidget(blob)

        track = _panel("Tracking stability")
        self.s_alpha = ParamSlider("Smoothing (alpha)", 0.05, 1.0, 0.5, scale=100, fmt="{:.2f}",
                                   tooltip="p = alpha * new + (1 - alpha) * previous. 1 = raw, small = smooth but laggy.")
        self.s_lost = ParamSlider("Lost timeout (ms)", 100, 3000, 600, tooltip="How long the last position is held "
                                  "(flagged invalid) before the pointer is declared lost.")
        self.s_jump = ParamSlider("Max jump (%)", 5, 100, 25, tooltip="Largest believable move per frame, as a "
                                  "percentage of the frame diagonal. Larger jumps need confirmation.")
        self.s_confirm = ParamSlider("Confirm frames", 1, 6, 2, tooltip="Frames a far jump must persist to be accepted.")
        for s in (self.s_alpha, self.s_lost, self.s_jump, self.s_confirm):
            s.valueChanged.connect(self._on_tracker_changed)
            track.layout().addWidget(s)
        side.addWidget(track)

        reset = QPushButton("Reset detection settings")
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.clicked.connect(self._reset_detection)
        side.addWidget(reset)
        side.addStretch(1)
        return page

    # ------------------------------------------------------------------ model <-> sliders
    def load_from_controller(self) -> None:
        """Show the controller's current parameters in the sliders (no signals fired)."""
        d, t = self.ctl.detection_params, self.ctl.tracker_params
        self._loading = True
        for s, v in ((self.s_hl, d.hsv_low[0]), (self.s_sl, d.hsv_low[1]), (self.s_vl, d.hsv_low[2]),
                     (self.s_hh, d.hsv_high[0]), (self.s_sh, d.hsv_high[1]), (self.s_vh, d.hsv_high[2]),
                     (self.s_min, d.min_area), (self.s_max, d.max_area), (self.s_kernel, d.kernel_size),
                     (self.s_conf, d.confidence_min), (self.s_alpha, t.alpha), (self.s_lost, t.lost_timeout_ms),
                     (self.s_jump, t.max_jump_pct), (self.s_confirm, t.confirm_frames),
                     (self.s_sens, float(self.settings.get("detection.sensitivity", 50)))):
            s.set_value(v)
        self._loading = False
        self._update_sample_label()
        self._refresh_general()

    def _on_detection_changed(self, _v: float = 0.0) -> None:
        if self._loading:
            return
        cur = self.ctl.detection_params
        self.ctl.set_detection_params(DetectionParams(
            hsv_low=(int(self.s_hl.value()), int(self.s_sl.value()), int(self.s_vl.value())),
            hsv_high=(int(self.s_hh.value()), int(self.s_sh.value()), int(self.s_vh.value())),
            min_area=int(self.s_min.value()), max_area=int(self.s_max.value()),
            kernel_size=int(self.s_kernel.value()), confidence_min=self.s_conf.value(),
            detect_width=cur.detect_width))

    def _on_tracker_changed(self, _v: float = 0.0) -> None:
        if self._loading:
            return
        self.ctl.set_tracker_params(TrackerParams(
            alpha=self.s_alpha.value(), lost_timeout_ms=int(self.s_lost.value()),
            max_jump_pct=self.s_jump.value(), confirm_frames=int(self.s_confirm.value())))

    def _set_hsv(self, low, high) -> None:
        self._loading = True
        for s, v in ((self.s_hl, low[0]), (self.s_sl, low[1]), (self.s_vl, low[2]),
                     (self.s_hh, high[0]), (self.s_sh, high[1]), (self.s_vh, high[2])):
            s.set_value(v)
        self._loading = False
        self._on_detection_changed()

    # ------------------------------------------------------------------ colour selection
    def _apply_preset(self, name: str) -> None:
        low, high, sample = PRESETS[name]
        self.settings.set("detection.sample_hsv", list(sample))
        self._set_hsv(low, high)
        self._update_sample_label()
        self.message.emit(f"{name} marker preset applied", "info")

    def _on_sensitivity(self, value: float) -> None:
        if self._loading:
            return
        self.settings.set("detection.sensitivity", int(value))
        sample = tuple(self.settings.get("detection.sample_hsv", (60, 200, 200)))
        low, high = hsv_range_from_sample(sample, value)
        self._set_hsv(low, high)

    def _on_pick(self, fx: float, fy: float, button: int) -> None:
        if self._last is None or button != Qt.MouseButton.LeftButton.value:
            return
        try:
            sample = median_hsv_at(self._last.frame, fx, fy)
        except ValueError:
            return
        self.settings.set("detection.sample_hsv", list(sample))
        low, high = hsv_range_from_sample(sample, self.s_sens.value())
        self._set_hsv(low, high)
        self._update_sample_label()
        self.message.emit(f"Picked colour H {sample[0]}  S {sample[1]}  V {sample[2]}", "success")

    def _update_sample_label(self) -> None:
        h, s, v = (int(x) for x in self.settings.get("detection.sample_hsv", (60, 200, 200)))
        self.sample_label.setText(f"Reference colour: H {h}  S {s}  V {v}")

    def _reset_detection(self) -> None:
        defaults = copy.deepcopy(DEFAULTS["detection"])
        for key, value in defaults.items():
            self.settings.set(f"detection.{key}", value)
        self.ctl.set_detection_params(DetectionParams.from_settings(self.settings))
        self.ctl.set_tracker_params(TrackerParams.from_settings(self.settings))
        self.load_from_controller()
        self.message.emit("Detection settings restored to defaults", "info")

    # ------------------------------------------------------------------ live updates
    def _on_signal_lost(self) -> None:
        self._last = None
        self.live_view.set_frame(None)
        self.mask_view.set_frame(None)
        for r in (self.r_det, self.r_pos, self.r_area, self.r_fps):
            r.set_state("off", "-")
        self.det_message.setText("")

    def _on_result(self, res: VisionResult) -> None:
        if not self.isVisible():
            return
        self._last = res
        self.live_view.set_frame(res.frame)
        if res.mask is not None:
            self.mask_view.set_frame(res.mask)
        now = time.perf_counter()
        if now - self._last_text < 0.1:
            return
        self._last_text = now
        det = res.detection.detection
        self.r_det.set_state("ok" if det else "warn", "Found" if det else "Not found")
        self.r_pos.set_state("ok" if det else "off", f"{det.x:.0f}, {det.y:.0f}" if det else "-")
        self.r_area.set_state("ok" if det else "off", f"{det.area:.0f} px / {det.confidence:.2f}" if det else "-")
        self.r_fps.set_state("ok" if res.tracking_fps >= 15 else "warn", f"{res.tracking_fps:.1f}")
        self.det_message.setText(res.detection.message)

    def _live_overlay(self, p: QPainter, view: VideoView) -> None:
        if self._last is not None:
            draw_detection(p, view, self._last)

    def _mask_overlay(self, p: QPainter, view: VideoView) -> None:
        res = self._last
        if res is None or res.mask is None or res.detection.detection is None:
            return
        det, (fw, fh) = res.detection.detection, res.frame_size
        mh, mw = res.mask.shape[:2]
        c = view.frame_to_widget((det.x + 0.5) * mw / fw - 0.5, (det.y + 0.5) * mh / fh - 0.5)
        draw_crosshair(p, c, QColor("#12B5A6"), radius=10)

    # =============================================================== general tab
    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(12)
        cols = QHBoxLayout()
        cols.setSpacing(16)
        outer.addLayout(cols)
        left, right = QVBoxLayout(), QVBoxLayout()
        for c in (left, right):
            c.setSpacing(12)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)

        cam = _panel("Camera")
        self.autostart_box = QCheckBox("Start the camera automatically when a camera page opens")
        self.autostart_box.setChecked(bool(self.settings.get("camera.autostart", True)))
        self.autostart_box.toggled.connect(self._on_autostart)
        cam.layout().addWidget(self.autostart_box)
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Requested resolution"))
        self.res_combo = QComboBox()
        for label, w, h in RESOLUTIONS:
            self.res_combo.addItem(label, (w, h))
        cur = (int(self.settings.get("camera.width", 1280)), int(self.settings.get("camera.height", 720)))
        i = self.res_combo.findData(cur)
        if i < 0:
            self.res_combo.addItem(f"{cur[0]} x {cur[1]}", cur)
            i = self.res_combo.count() - 1
        self.res_combo.setCurrentIndex(i)
        self.res_combo.currentIndexChanged.connect(self._on_resolution)
        res_row.addWidget(self.res_combo, 1)
        cam.layout().addLayout(res_row)
        note = QLabel("Changing the resolution restarts the camera. A calibration made at another aspect ratio "
                      "will ask you to recalibrate.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        cam.layout().addWidget(note)
        left.addWidget(cam)

        ptr = _panel("Pointer")
        self.pointer_box = QCheckBox("Show the tracked pointer on the whiteboard")
        self.pointer_box.setChecked(bool(self.settings.get("pointer.visible", True)))
        self.pointer_box.toggled.connect(self._on_pointer_visible)
        ptr.layout().addWidget(self.pointer_box)
        left.addWidget(ptr)
        left.addStretch(1)

        method = _panel("Detection method")
        mp = importlib.util.find_spec("mediapipe") is not None
        active = QLabel("Active: OpenCV HSV colour marker (own NumPy implementation)")
        active.setStyleSheet("font-weight: 700;")
        method.layout().addWidget(active)
        info = QLabel(("MediaPipe is installed, but its hand-tracking backend is not integrated in this version. "
                       if mp else "MediaPipe is not installed (optional). ")
                      + "The colour marker is always used; it needs no model files and runs on any webcam.")
        info.setObjectName("muted")
        info.setWordWrap(True)
        method.layout().addWidget(info)
        right.addWidget(method)

        maint = _panel("Maintenance")
        self.cal_status = StatusRow("Calibration")
        maint.layout().addWidget(self.cal_status)
        self.del_cal_btn = QPushButton("Delete saved calibration")
        self.del_cal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_cal_btn.clicked.connect(self._delete_calibration)
        maint.layout().addWidget(self.del_cal_btn)
        reset = QPushButton("Reset all settings")
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.setToolTip("Restores factory settings (pen, detection, resolution, recent files). Camera choice, mirror and calibration are kept.")
        reset.clicked.connect(self._confirm_reset)
        maint.layout().addWidget(reset)
        right.addWidget(maint)
        right.addStretch(1)
        outer.addStretch(1)
        return page

    def _refresh_general(self) -> None:
        self.cal_status.set_state(*self.ctl.state.calibration)
        self.del_cal_btn.setEnabled(self.ctl.calibration is not None)
        self._loading = True
        self.autostart_box.setChecked(bool(self.settings.get("camera.autostart", True)))
        self.pointer_box.setChecked(bool(self.settings.get("pointer.visible", True)))
        cur = (int(self.settings.get("camera.width", 1280)), int(self.settings.get("camera.height", 720)))
        i = self.res_combo.findData(cur)
        if i >= 0:
            self.res_combo.setCurrentIndex(i)
        self._loading = False

    def _on_autostart(self, on: bool) -> None:
        if not self._loading:
            self.settings.set("camera.autostart", bool(on))
            self.settings.save()

    def _on_pointer_visible(self, on: bool) -> None:
        if not self._loading:
            self.settings.set("pointer.visible", bool(on))
            self.settings.save()
            self.pointerVisibilityChanged.emit(bool(on))

    def _on_resolution(self, _i: int) -> None:
        if self._loading:
            return
        w, h = self.res_combo.currentData()
        self.settings.set("camera.width", int(w))
        self.settings.set("camera.height", int(h))
        self.settings.save()
        if self.ctl.running:
            self.ctl.restart()
        self.message.emit(f"Camera resolution set to {w} x {h}", "info")

    def _delete_calibration(self) -> None:
        if self.ctl.calibration is None:
            return
        answer = QMessageBox.question(
            self, "Delete calibration", "Delete the saved calibration?\nThe pointer will no longer be mapped onto "
            "the board until you calibrate again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            self.ctl.clear_calibration()
            self.message.emit("Calibration deleted", "info")

    def _confirm_reset(self) -> None:
        answer = QMessageBox.question(
            self, "Reset all settings", "Restore all settings to factory defaults?\nPen, detection, resolution and the recent-files list are reset, "
            "and the whiteboard is cleared. Camera choice, mirror setting and the saved calibration are kept.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            self.resetRequested.emit()
