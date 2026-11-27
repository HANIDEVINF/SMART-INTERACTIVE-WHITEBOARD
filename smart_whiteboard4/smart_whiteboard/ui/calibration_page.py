"""Calibration wizard: mark the four board corners, compute the homography, validate, save.

Flow (modes)
    live    camera preview + instructions                    -> "Capture frame" freezes the image
    pick    frozen frame, click the four corners (drag to adjust, right-click removes the last)
    review  matrix, reprojection error, projected grid and rectified preview -> "Save calibration"
A saved calibration is always testable: the mini map shows the live pointer in board coordinates.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QKeySequence, QPainter, QPainterPath, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from core.calibration import (CORNER_NAMES, CORNER_SHORT, Calibration, CalibrationError, order_corners,
                              validate_corners)
from core.coordinate_mapping import CoordinateMapper, fit_board_in_canvas
from core.homography import apply_homography
from core.vision_engine import VisionController, VisionResult
from ui import icons
from ui.styles import ACCENT, AMBER, GREEN, MUTED, ROSE, TEXT
from ui.video_view import VideoView, draw_crosshair

HIT_RADIUS = 16.0   # widget pixels


class BoardMiniMap(QWidget):
    """The board rectangle with the live mapped pointer: the visual calibration test."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.board_size = (1600, 900)
        self.pointer: tuple[float, float] | None = None
        self.state = "lost"
        self.active = False

    def set_board_size(self, size: tuple[int, int]) -> None:
        self.board_size = size
        self.update()

    def set_pointer(self, pos: tuple[float, float] | None, state: str = "tracking") -> None:
        self.pointer, self.state = pos, state
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x, y, w, h = fit_board_in_canvas(self.board_size, (self.width(), self.height()), margin=4)
        board = QRectF(x, y, w, h)
        p.setPen(QPen(QColor("#D9D6CA"), 1.5))
        p.setBrush(QColor("#FAF9F6" if self.active else "#EFEDE5"))
        p.drawRoundedRect(board, 8, 8)
        p.setPen(QPen(QColor("#E6E3D9"), 1))
        for i in range(1, 4):
            p.drawLine(QPointF(board.x() + w * i / 4, board.y()), QPointF(board.x() + w * i / 4, board.bottom()))
        for j in range(1, 3):
            p.drawLine(QPointF(board.x(), board.y() + h * j / 3), QPointF(board.right(), board.y() + h * j / 3))
        if not self.active:
            p.setPen(QColor(MUTED))
            p.drawText(board, Qt.AlignmentFlag.AlignCenter, "Calibrate to test the mapping")
            return
        if self.pointer is None:
            p.setPen(QColor(MUTED))
            p.drawText(board, Qt.AlignmentFlag.AlignCenter, "Move the marker onto the board")
            return
        c = QPointF(board.x() + self.pointer[0] / self.board_size[0] * w,
                    board.y() + self.pointer[1] / self.board_size[1] * h)
        color = QColor(GREEN if self.state == "tracking" else AMBER)
        p.setPen(QPen(color, 2))
        p.setBrush(QColor(color.red(), color.green(), color.blue(), 60))
        p.drawEllipse(c, 11, 11)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(c, 4, 4)


class CalibrationPage(QWidget):
    homeRequested = None  # (navigation is handled by the sidebar)

    def __init__(self, settings, controller: VisionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self.settings, self.ctl = settings, controller
        self.mode = "live"
        self.points: list[tuple[float, float]] = []
        self.frozen: np.ndarray | None = None
        self.frozen_mirror = False
        self.candidate: Calibration | None = None
        self.problems: list[str] = []
        self.notice = ""
        self._drag_index: int | None = None
        self._last_result: VisionResult | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(12)
        title = QLabel("Calibration")
        title.setObjectName("h2")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("muted")
        self.subtitle.setWordWrap(True)
        left.addWidget(title)
        left.addWidget(self.subtitle)
        self.view = VideoView("No camera signal.\nStart the camera on the Camera page.")
        self.view.set_overlay(self._overlay)
        self.view.clicked.connect(self._on_click)
        self.view.pressed.connect(self._on_press)
        self.view.moved.connect(self._on_move)
        self.view.released.connect(self._on_release)
        left.addWidget(self.view, 1)
        root.addLayout(left, 1)

        # ------------------------------------------------------------ right panel (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(392)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        side = QVBoxLayout(inner)
        side.setContentsMargins(0, 0, 8, 0)
        side.setSpacing(12)
        scroll.setWidget(inner)
        root.addWidget(scroll)

        self.status_box = QFrame()
        self.status_box.setObjectName("note")
        sb = QVBoxLayout(self.status_box)
        sb.setContentsMargins(14, 10, 14, 10)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        sb.addWidget(self.status_label)
        side.addWidget(self.status_box)

        steps = self._panel("Steps")
        self.step_labels = []
        for text in ("1  Frame the whole board in the camera", "2  Capture and click the four corners",
                     "3  Review the transformation and save"):
            lab = QLabel(text)
            lab.setWordWrap(True)
            steps.layout().addWidget(lab)
            self.step_labels.append(lab)
        self.instruction = QLabel()
        self.instruction.setWordWrap(True)
        self.instruction.setObjectName("muted")
        steps.layout().addWidget(self.instruction)
        side.addWidget(steps)

        corners = self._panel("Corners")
        self.corner_labels = []
        for i, name in enumerate(CORNER_NAMES):
            lab = QLabel()
            lab.setObjectName("mono")
            corners.layout().addWidget(lab)
            self.corner_labels.append(lab)
        side.addWidget(corners)

        self.result_panel = self._panel("Transformation")
        self.matrix_label = QLabel("-")
        self.matrix_label.setObjectName("mono")
        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.problem_label = QLabel("")
        self.problem_label.setWordWrap(True)
        self.rectified = QLabel()
        self.rectified.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rectified.setMinimumHeight(0)
        for w in (self.matrix_label, self.error_label, self.problem_label, self.rectified):
            self.result_panel.layout().addWidget(w)
        side.addWidget(self.result_panel)

        test = self._panel("Test: pointer on the board")
        self.minimap = BoardMiniMap()
        self.coords_label = QLabel("-")
        self.coords_label.setObjectName("mono")
        test.layout().addWidget(self.minimap)
        test.layout().addWidget(self.coords_label)
        side.addWidget(test)

        actions = QFrame()
        al = QVBoxLayout(actions)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(8)
        self.capture_btn = self._button("  Capture frame  (Space)", "camera", primary=True)
        self.save_btn = self._button("  Save calibration  (Enter)", "check", primary=True)
        self.reset_btn = self._button("  Reset selection  (R)", "undo")
        self.live_btn = self._button("  Back to live view", "arrow-left")
        self.recal_btn = self._button("  Recalibrate", "calibrate")
        self.clear_btn = self._button("  Delete saved calibration", "trash")
        for b in (self.capture_btn, self.save_btn, self.reset_btn, self.live_btn, self.recal_btn, self.clear_btn):
            al.addWidget(b)
        side.addWidget(actions)
        side.addStretch(1)

        self.capture_btn.clicked.connect(self.capture)
        self.save_btn.clicked.connect(self.save)
        self.reset_btn.clicked.connect(self.reset_selection)
        self.live_btn.clicked.connect(self.back_to_live)
        self.recal_btn.clicked.connect(self.recalibrate)
        self.clear_btn.clicked.connect(self.delete_saved)
        for key, fn in ((Qt.Key.Key_Space, self.capture), (Qt.Key.Key_Return, self.save), (Qt.Key.Key_Enter, self.save),
                        (Qt.Key.Key_R, self.reset_selection)):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)

        self.ctl.resultReady.connect(self._on_result)
        self.ctl.signalLost.connect(self._on_signal_lost)
        self.ctl.calibrationChanged.connect(self._refresh)
        self._refresh()

    # ------------------------------------------------------------------ small builders
    @staticmethod
    def _panel(title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)
        label = QLabel(title)
        label.setObjectName("panelTitle")
        lay.addWidget(label)
        return frame

    @staticmethod
    def _button(text: str, icon_name: str, primary: bool = False) -> QPushButton:
        b = QPushButton(text)
        b.setIcon(icons.icon(icon_name, "#FFFFFF" if primary else TEXT, 18))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if primary:
            b.setObjectName("primary")
        return b

    # ------------------------------------------------------------------ workflow
    def capture(self) -> None:
        if self.mode != "live":
            return
        frame = self.ctl.latest_frame()
        if frame is None:
            self.notice = "No camera frame available. Start the camera first (Camera page)."
            self._refresh()
            return
        self.frozen, self.frozen_mirror = frame.copy(), self.ctl.mirror
        self.points, self.candidate, self.problems, self.notice = [], None, [], ""
        self.mode = "pick"
        self.view.set_frame(self.frozen)
        self._refresh()

    def reset_selection(self) -> None:
        if self.mode in ("pick", "review"):
            self.points, self.candidate, self.problems, self.notice = [], None, [], ""
            self.mode = "pick"
            self._refresh()

    def back_to_live(self) -> None:
        self.mode, self.points, self.candidate, self.problems, self.notice = "live", [], None, [], ""
        self.frozen = None
        self._refresh()

    def recalibrate(self) -> None:
        self.back_to_live()

    def delete_saved(self) -> None:
        if self.ctl.calibration is None:
            return
        answer = QMessageBox.question(self, "Delete calibration", "Delete the saved calibration?\n"
                                      "The pointer will no longer be mapped onto the board until you calibrate again.",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            self.ctl.clear_calibration()
            self.notice = "Calibration deleted."
            self._refresh()

    def save(self) -> None:
        if self.mode != "review" or self.candidate is None:
            return
        try:
            self.ctl.set_calibration(self.candidate)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", f"The calibration could not be saved:\n{exc}")
            return
        self.notice = "Calibration saved. Move the marker over the board to test it."
        self.mode, self.points, self.frozen = "live", [], None
        self.candidate, self.problems = None, []
        self._refresh()

    # ------------------------------------------------------------------ point editing
    def _hit(self, widget_pos: QPointF) -> int | None:
        for i, (x, y) in enumerate(self.points):
            c = self.view.frame_to_widget(x, y)
            if math.hypot(c.x() - widget_pos.x(), c.y() - widget_pos.y()) <= HIT_RADIUS:
                return i
        return None

    def _on_press(self, fx: float, fy: float, button: int) -> None:
        if self.mode not in ("pick", "review") or button != Qt.MouseButton.LeftButton.value:
            return
        self._drag_index = self._hit(self.view.frame_to_widget(fx, fy))

    def _on_move(self, fx: float, fy: float) -> None:
        if self._drag_index is not None and self.mode in ("pick", "review"):
            self.points[self._drag_index] = (fx, fy)
            self._recompute()
            self.view.update()

    def _on_release(self, fx: float, fy: float, button: int) -> None:
        if self._drag_index is not None:
            self._drag_index = None
            self._recompute()
            self._refresh()

    def _on_click(self, fx: float, fy: float, button: int) -> None:
        if self.mode not in ("pick", "review"):
            return
        if button == Qt.MouseButton.RightButton.value:           # right click: remove the last corner
            if self.points:
                self.points.pop()
                self.mode = "pick"
                self._recompute()
                self._refresh()
            return
        if button != Qt.MouseButton.LeftButton.value:
            return
        if self._hit(self.view.frame_to_widget(fx, fy)) is not None:   # click on an existing point: it was only selected
            return
        if len(self.points) < 4:
            self.points.append((fx, fy))
            if len(self.points) == 4:
                reordered = order_corners(self.points)
                if reordered != [tuple(map(float, p)) for p in self.points]:
                    self.notice = "The corners were re-ordered automatically (TL, TR, BR, BL)."
                else:
                    self.notice = ""
                self.points = reordered
            self._recompute()
            self._refresh()

    def _recompute(self) -> None:
        self.candidate, self.problems = None, []
        if len(self.points) < 4:
            self.mode = "pick"
            return
        self.points = order_corners(self.points)
        size = self.frozen_size()
        self.problems = validate_corners(self.points, size)
        if not self.problems:
            try:
                self.candidate = Calibration.from_corners(self.points, size, self._board_size(), self.frozen_mirror)
            except CalibrationError as exc:
                self.problems = exc.problems
        self.mode = "review"

    def frozen_size(self) -> tuple[int, int]:
        return (self.frozen.shape[1], self.frozen.shape[0]) if self.frozen is not None else (1, 1)

    def _board_size(self) -> tuple[int, int]:
        return int(self.settings.get("board.width", 1600)), int(self.settings.get("board.height", 900))

    # ------------------------------------------------------------------ camera updates
    def _on_signal_lost(self) -> None:
        self._last_result = None
        self.minimap.set_pointer(None)
        self.coords_label.setText("-")
        if self.mode == "live":
            self.view.set_frame(None)
            self.view.set_placeholder("No camera signal.\nStart the camera on the Camera page.")

    def _on_result(self, res: VisionResult) -> None:
        self._last_result = res
        if not self.isVisible():
            return
        if self.mode == "live":
            self.view.set_frame(res.frame)
        if self.ctl.mapper is not None and res.calib_state != "mismatch":
            b = res.board
            self.minimap.set_pointer((b.x, b.y) if b else None, res.track.state)
            if b:
                self.coords_label.setText(f"board  x {b.x:7.1f}   y {b.y:7.1f}"
                                          + ("   (held)" if res.track.state != "tracking" else ""))
            else:
                self.coords_label.setText("pointer lost" if res.track.position is None else "outside the board")
        else:
            self.minimap.set_pointer(None)

    # ------------------------------------------------------------------ view refresh
    def _refresh(self) -> None:
        cal = self.ctl.calibration
        self.minimap.active = cal is not None and self.ctl.state.calibration[0] != "error"
        self.minimap.set_board_size(cal.board_size if cal else self._board_size())

        # status box
        if self.ctl.calibration_error and cal is None:
            kind, text = "noteError", self.ctl.calibration_error
        elif cal is None:
            kind, text = "note", "Not calibrated. The pointer cannot be mapped onto the board yet."
        else:
            state, msg = self.ctl.state.calibration
            w, h = cal.camera_size
            kind = {"ok": "noteOk", "warn": "note"}.get(state, "noteError")
            text = (f"{msg}.  Camera {w}x{h}, mirror {'on' if cal.mirror else 'off'}, saved {cal.created.replace('T', ' ')}. "
                    f"Corner error {cal.rms_error:.2f} px.")
            if state == "error":
                text = "Recalibration needed: the camera resolution or mirroring changed since this calibration."
        self.status_box.setObjectName(kind)
        self.status_box.style().unpolish(self.status_box)
        self.status_box.style().polish(self.status_box)
        self.status_label.setText(text)

        # steps
        active = {"live": 0, "pick": 1, "review": 2}[self.mode]
        for i, lab in enumerate(self.step_labels):
            name = "stepActive" if i == active else "stepDone" if i < active else "stepIdle"
            lab.setObjectName(name)
            lab.style().unpolish(lab)
            lab.style().polish(lab)
        n = len(self.points)
        self.instruction.setText({
            "live": "Point the camera so the whole board is visible, keep it steady, then press Capture frame.",
            "pick": (f"Click corner {n + 1} of 4: {CORNER_NAMES[n]}. Drag a point to adjust it, right-click to remove "
                     "the last one." if n < 4 else ""),
            "review": "Check that the grid follows the board edges. Drag a corner to refine, then save.",
        }[self.mode] + (f"\n{self.notice}" if self.notice else ""))
        self.subtitle.setText({
            "live": "Live view. The saved calibration (if any) stays active until you save a new one.",
            "pick": "Captured image. Mark the four corners of the board: Top-left, Top-right, Bottom-right, Bottom-left.",
            "review": "Review the calibration. The grid shows the board coordinate system projected into the camera image.",
        }[self.mode])

        # corners list
        for i, lab in enumerate(self.corner_labels):
            if i < len(self.points):
                x, y = self.points[i]
                lab.setText(f"{CORNER_SHORT[i]}  {CORNER_NAMES[i]:<13} {x:6.1f}, {y:6.1f}")
                lab.setStyleSheet(f"color: {GREEN};")
            else:
                lab.setText(f"{CORNER_SHORT[i]}  {CORNER_NAMES[i]:<13} -")
                lab.setStyleSheet(f"color: {MUTED};")

        # transformation panel
        self.result_panel.setVisible(self.mode == "review")
        if self.mode == "review":
            if self.candidate is not None:
                H = self.candidate.H
                self.matrix_label.setText("H (camera -> board)\n" + "\n".join(
                    "[" + "  ".join(f"{v:11.4f}" for v in row) + " ]" for row in H))
                self.error_label.setText(f"Corner reprojection error: {self.candidate.rms_error:.4f} board px   "
                                         f"(valid, non-singular, w > 0 over the board)")
                self.error_label.setStyleSheet(f"color: {GREEN}; font-weight: 600;")
                self.problem_label.setText("\n".join(self.candidate.warnings))
                self.problem_label.setStyleSheet(f"color: {AMBER};")
                self._show_rectified()
            else:
                self.matrix_label.setText("-")
                self.error_label.setText("The calibration cannot be used:")
                self.error_label.setStyleSheet(f"color: {ROSE}; font-weight: 700;")
                self.problem_label.setText("\n".join(f"- {p}" for p in self.problems))
                self.problem_label.setStyleSheet(f"color: {ROSE};")
                self.rectified.clear()
                self.rectified.setMinimumHeight(0)

        # buttons
        has_frame = self.ctl.latest_frame() is not None
        self.capture_btn.setVisible(self.mode == "live")
        self.capture_btn.setEnabled(has_frame)
        self.save_btn.setVisible(self.mode == "review")
        self.save_btn.setEnabled(self.candidate is not None)
        self.reset_btn.setVisible(self.mode in ("pick", "review"))
        self.live_btn.setVisible(self.mode in ("pick", "review"))
        self.recal_btn.setVisible(self.mode == "live" and cal is not None)
        self.clear_btn.setVisible(self.mode == "live" and cal is not None)
        if self.mode != "live":
            self.view.set_frame(self.frozen)
        elif self._last_result is not None:
            self.view.set_frame(self._last_result.frame)
        self.view.update()

    def _show_rectified(self) -> None:
        """Perspective-corrected view of the captured board, computed with H (cv2.warpPerspective just
        resamples the pixels: for every output pixel it reads the input at H^-1 of that position)."""
        cal = self.candidate
        if cal is None or self.frozen is None:
            return
        out_w = 340
        out_h = max(1, int(round(out_w * cal.board_size[1] / cal.board_size[0])))
        S = np.diag([out_w / cal.board_size[0], out_h / cal.board_size[1], 1.0])
        warped = cv2.warpPerspective(self.frozen, S @ cal.H, (out_w, out_h), flags=cv2.INTER_LINEAR)
        rgb = np.ascontiguousarray(warped[..., ::-1])
        img = QImage(rgb.data, out_w, out_h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
        self.rectified.setPixmap(QPixmap.fromImage(img))
        self.rectified.setMinimumHeight(out_h + 4)

    # ------------------------------------------------------------------ overlay on the video
    def _overlay(self, p: QPainter, view: VideoView) -> None:
        font = QFont(p.font())
        font.setPointSize(10)
        font.setBold(True)
        p.setFont(font)

        if self.mode == "live":
            self._draw_saved_calibration(p, view)
            res = self._last_result
            if res is not None and res.track.position is not None:
                color = QColor(GREEN if res.track.state == "tracking" else AMBER)
                draw_crosshair(p, view.frame_to_widget(*res.track.position), color, 12)
            return

        pts = [view.frame_to_widget(x, y) for x, y in self.points]
        if len(pts) >= 2:
            ok = self.candidate is not None
            line_color = QColor(GREEN if ok or len(pts) < 4 else ROSE)
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            if len(pts) == 4:
                path.closeSubpath()
                p.setBrush(QColor(line_color.red(), line_color.green(), line_color.blue(), 38))
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(line_color, 2.2))
            p.drawPath(path)
        if self.candidate is not None:
            self._draw_grid(p, view, self.candidate)
        for i, c in enumerate(pts):
            p.setPen(QPen(QColor(255, 255, 255), 3))
            p.setBrush(QColor(ACCENT))
            p.drawEllipse(c, 9, 9)
            p.setPen(QColor(255, 255, 255))
            p.drawText(QRectF(c.x() - 9, c.y() - 9, 18, 18), Qt.AlignmentFlag.AlignCenter, str(i + 1))
            label = CORNER_SHORT[i]
            p.setPen(QColor(0, 0, 0, 180))
            p.drawText(QPointF(c.x() + 15, c.y() - 11), label)
            p.setPen(QColor(255, 255, 255))
            p.drawText(QPointF(c.x() + 14, c.y() - 12), label)
        if len(self.points) < 4:                       # hint next target
            p.setPen(QColor(255, 255, 255, 230))
            p.drawText(QRectF(10, 8, view.width() - 20, 28), Qt.AlignmentFlag.AlignLeft,
                       f"Click: {CORNER_NAMES[len(self.points)]}")

    def _draw_grid(self, p: QPainter, view: VideoView, cal: Calibration) -> None:
        """Project the board's coordinate grid into the camera image with H^-1 (visual validation)."""
        bw, bh = cal.board_size
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 190), 1.3))
        n = 10
        for i in range(1, n):
            for a, b in (((bw * i / n, 0), (bw * i / n, bh)), ((0, bh * i / n), (bw, bh * i / n))):
                pa, pb = apply_homography(cal.H_inv, a), apply_homography(cal.H_inv, b)
                p.drawLine(view.frame_to_widget(*pa), view.frame_to_widget(*pb))
        centre = apply_homography(cal.H_inv, (bw / 2, bh / 2))
        p.setPen(QPen(QColor(AMBER), 2))
        c = view.frame_to_widget(*centre)
        p.drawLine(QPointF(c.x() - 10, c.y()), QPointF(c.x() + 10, c.y()))
        p.drawLine(QPointF(c.x(), c.y() - 10), QPointF(c.x(), c.y() + 10))

    def _draw_saved_calibration(self, p: QPainter, view: VideoView) -> None:
        cal = self.ctl.calibration
        res = self._last_result
        if cal is None or res is None or res.calib_state == "mismatch":
            return
        sx, sy = res.frame_size[0] / cal.camera_size[0], res.frame_size[1] / cal.camera_size[1]
        pts = [view.frame_to_widget(x * sx, y * sy) for x, y in cal.corners]
        path = QPainterPath(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
        path.closeSubpath()
        p.setPen(QPen(QColor(GREEN), 2, Qt.PenStyle.DashLine))
        p.setBrush(QColor(22, 163, 74, 28))
        p.drawPath(path)
