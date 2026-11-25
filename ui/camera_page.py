"""Camera Diagnostics page: live feed with detection overlay, resolution, FPS and status."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from core.vision_engine import VisionController, VisionResult
from ui import icons
from ui.video_view import VideoView, draw_detection
from ui.widgets import StatusRow


class CameraPage(QWidget):
    def __init__(self, controller: VisionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self.ctl = controller
        self._last_result: VisionResult | None = None
        self._last_stats = 0.0

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)

        # ---- left: live feed --------------------------------------------------------
        left = QVBoxLayout()
        left.setSpacing(12)
        title = QLabel("Camera Diagnostics")
        title.setObjectName("h2")
        sub = QLabel("Live feed with pointer detection. Green = tracking, amber = held / searching.")
        sub.setObjectName("muted")
        left.addWidget(title)
        left.addWidget(sub)
        self.view = VideoView("Camera is not running.\nPress Start camera.")
        self.view.set_overlay(self._overlay)
        left.addWidget(self.view, 1)
        root.addLayout(left, 1)

        # ---- right: controls + status ------------------------------------------------
        side = QVBoxLayout()
        side.setSpacing(14)
        side_frame = QWidget()
        side_frame.setFixedWidth(360)
        side_frame.setLayout(side)
        root.addWidget(side_frame)

        controls = self._panel("Camera")
        self.combo = QComboBox()
        self.combo.setToolTip("Camera to use. Press Refresh to look for connected cameras.")
        self.combo.addItem(f"Camera {self.ctl.camera_index}", self.ctl.camera_index)
        self.combo.currentIndexChanged.connect(self._on_combo)
        refresh = QPushButton("Refresh")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self._scan)
        row = QHBoxLayout()
        row.addWidget(self.combo, 1)
        row.addWidget(refresh)
        controls.layout().addLayout(row)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("primary")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._toggle)
        self.restart_btn = QPushButton("  Restart")
        self.restart_btn.setIcon(icons.icon("undo", "#1B2140", 18))
        self.restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restart_btn.clicked.connect(self.ctl.restart)
        row = QHBoxLayout()
        row.addWidget(self.toggle_btn, 1)
        row.addWidget(self.restart_btn)
        controls.layout().addLayout(row)

        self.mirror_box = QCheckBox("Mirror image (selfie view)")
        self.mirror_box.setChecked(self.ctl.mirror)
        self.mirror_box.setToolTip("Flip the image horizontally. Changing it requires a new calibration.")
        self.mirror_box.toggled.connect(self.ctl.set_mirror)
        controls.layout().addWidget(self.mirror_box)
        side.addWidget(controls)

        stats = self._panel("Status")
        self.r_conn = StatusRow("Connection")
        self.r_res = StatusRow("Resolution")
        self.r_cam_fps = StatusRow("Camera FPS")
        self.r_trk_fps = StatusRow("Tracking FPS")
        self.r_det = StatusRow("Detection")
        self.r_pos = StatusRow("Pointer (camera px)")
        self.r_board = StatusRow("Pointer (board)")
        self.r_calib = StatusRow("Calibration")
        for r in (self.r_conn, self.r_res, self.r_cam_fps, self.r_trk_fps, self.r_det, self.r_pos,
                  self.r_board, self.r_calib):
            stats.layout().addWidget(r)
        side.addWidget(stats)

        self.message = QLabel("")
        self.message.setWordWrap(True)
        self.message.setObjectName("muted")
        side.addWidget(self.message)
        side.addStretch(1)

        # ---- wiring ---------------------------------------------------------------------
        self.ctl.resultReady.connect(self._on_result)
        self.ctl.signalLost.connect(self._on_signal_lost)
        self.ctl.cameraStatusChanged.connect(self._on_camera_status)
        self.ctl.cameraOpened.connect(self._on_opened)
        self.ctl.cameraFpsChanged.connect(self._on_fps)
        self.ctl.camerasFound.connect(self._on_cameras)
        self.ctl.calibrationChanged.connect(self._refresh_calibration)
        self._refresh_all()

    @staticmethod
    def _panel(title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        label = QLabel(title)
        label.setObjectName("panelTitle")
        lay.addWidget(label)
        return frame

    # ------------------------------------------------------------------ actions
    def _toggle(self) -> None:
        if self.ctl.running:
            self.ctl.stop()
        else:
            self.ctl.start()
        self._refresh_all()

    def _scan(self) -> None:
        self.message.setText("Looking for cameras...")
        self.ctl.scan_cameras()

    def _on_combo(self, _index: int) -> None:
        idx = self.combo.currentData()
        if idx is not None and idx != self.ctl.camera_index:
            self.ctl.start(idx)
            self._refresh_all()

    def _on_cameras(self, cams: list) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        for index, label in cams:
            self.combo.addItem(label, index)
        if not cams:
            self.combo.addItem(f"Camera {self.ctl.camera_index}", self.ctl.camera_index)
            self.message.setText("No camera found. Plug one in or close apps that are using it, then press Refresh.")
        else:
            self.message.setText(f"{len(cams)} camera(s) found.")
            i = self.combo.findData(self.ctl.camera_index)
            self.combo.setCurrentIndex(max(i, 0))
        self.combo.blockSignals(False)

    # ------------------------------------------------------------------ updates
    def _refresh_all(self) -> None:
        running = self.ctl.running
        self.toggle_btn.setText("  Stop camera" if running else "  Start camera")
        self.toggle_btn.setIcon(icons.icon("camera", "#FFFFFF", 18))
        self.restart_btn.setEnabled(running)
        self._on_camera_status(*self.ctl.camera_state)
        self._refresh_calibration()

    def _on_camera_status(self, state: str, text: str) -> None:
        self.r_conn.set_state(state, {"ok": "Connected", "warn": "Waiting...", "error": "Not available",
                                      "off": "Stopped"}.get(state, text))
        if state == "error":
            self.message.setText(text)
        elif state == "warn":
            self.message.setText(text)
        else:
            self.message.setText("")
        if state != "ok":
            self.r_res.set_state("off", "-")
            self.r_cam_fps.set_state("off", "-")
            self.r_trk_fps.set_state("off", "-")
            self.r_det.set_state("off", "-")
            self.r_pos.set_state("off", "-")
            self.r_board.set_state("off", "-")
            if state == "off":
                self.view.set_frame(None)
                self.view.set_placeholder("Camera is not running.\nPress Start camera.")
            elif not self.view.has_frame:
                self.view.set_placeholder("Waiting for the camera...")
        self.toggle_btn.setText("  Stop camera" if self.ctl.running else "  Start camera")
        self.restart_btn.setEnabled(self.ctl.running)

    def _on_opened(self, w: int, h: int) -> None:
        self.r_res.set_state("ok", f"{w} x {h}")

    def _on_fps(self, fps: float) -> None:
        self.r_cam_fps.set_state("ok" if fps >= 15 else "warn" if fps > 0 else "off", f"{fps:.1f}")

    def _refresh_calibration(self) -> None:
        self.r_calib.set_state(*self.ctl.state.calibration)

    def _on_signal_lost(self) -> None:
        self._last_result = None

    def _on_result(self, res: VisionResult) -> None:
        if not self.isVisible():
            return
        self._last_result = res
        self.view.set_frame(res.frame)                      # repaint includes the overlay
        now = time.perf_counter()
        if now - self._last_stats < 0.1:                    # text updates at 10 Hz are plenty
            return
        self._last_stats = now
        self.r_res.set_state("ok", f"{res.frame_size[0]} x {res.frame_size[1]}")
        self.r_trk_fps.set_state("ok" if res.tracking_fps >= 15 else "warn", f"{res.tracking_fps:.1f}  ({res.process_ms:.1f} ms)")
        det = res.detection
        self.r_det.set_state("ok" if det.detection else "warn", "Marker found" if det.detection else "Not found")
        self.message.setText("" if det.detection else det.message)
        pos = res.track.position
        self.r_pos.set_state({"tracking": "ok", "holding": "warn"}.get(res.track.state, "error"),
                             f"{pos[0]:.0f}, {pos[1]:.0f}" if pos else "lost")
        if res.calib_state == "none":
            self.r_board.set_state("off", "not calibrated")
        elif res.calib_state == "mismatch":
            self.r_board.set_state("error", "recalibrate")
            self.message.setText(res.calib_message)
        elif res.board:
            self.r_board.set_state("ok", f"{res.board.x:.0f}, {res.board.y:.0f}")
        else:
            self.r_board.set_state("warn", "outside board" if pos else "-")

    def _overlay(self, painter, view) -> None:
        if self._last_result is not None:
            draw_detection(painter, view, self._last_result)
