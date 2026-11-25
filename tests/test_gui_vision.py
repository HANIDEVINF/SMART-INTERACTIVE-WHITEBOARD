"""GUI + computer-vision integration: the real main window driven by a fake webcam.

The fake webcam plays synthetic scenes with known geometry (tests/synthetic.py), so every assertion
compares what the *application* shows (pointer on the board, calibration, detection settings) with
the ground truth of the scene.
"""
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from core.app_state import AppState
from core.calibration import Calibration
from core.settings import Settings
from core.vision_engine import VisionController
from tests.qt_helpers import run_loop, wait_until
from tests.synthetic import (BOARD_H, BOARD_W, CAM_H, CAM_QUAD, CAM_W, RED, FakeCapture, board_to_cam_matrix,
                             project, render_scene)
from ui.calibration_page import CalibrationPage
from ui.camera_page import CameraPage
from ui.main_window import MainWindow
from ui.settings_page import SettingsPage
from ui.styles import STYLESHEET

CAM = (CAM_W, CAM_H)
TRUTH = (900.0, 400.0)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app


class Rig:
    """Main window + controller + fake webcam, all writing to a temp folder."""

    def __init__(self, tmp_path, frames, **capture_kw):
        self.tmp = tmp_path
        self.settings = Settings(tmp_path / "settings.json")
        self.state = AppState()
        self.frames = frames
        self.ctl = VisionController(self.settings, self.state,
                                    capture_factory=lambda i, b: FakeCapture(self.frames, **capture_kw),
                                    calibration_path=tmp_path / "calibration.json")
        self.win = MainWindow(self.settings, self.state, self.ctl)
        self.win.resize(1360, 840)
        self.win.show()
        QApplication.processEvents()

    def calibrate(self):
        self.ctl.set_calibration(Calibration.from_corners(CAM_QUAD, CAM, (BOARD_W, BOARD_H)))

    def close(self):
        self.win.close()


@pytest.fixture
def rig(qapp, tmp_path):
    made = []

    def make(frames=None, **kw):
        r = Rig(tmp_path, frames or (lambda i: render_scene(TRUTH, noise=3)), **kw)
        made.append(r)
        return r

    yield make
    for r in made:
        r.close()


def last_result(r):
    got = []
    r.ctl.resultReady.connect(got.append)
    return got


# ------------------------------------------------------------------------------------ navigation
def test_camera_calibration_and_settings_are_real_pages(rig):
    r = rig()
    assert isinstance(r.win.pages["camera"], CameraPage)
    assert isinstance(r.win.pages["calibration"], CalibrationPage)
    assert isinstance(r.win.pages["settings"], SettingsPage)
    for page_id in ("camera", "calibration", "settings", "home"):
        r.win.navigate(page_id)
        assert r.win.stack.currentWidget() is r.win.pages[page_id]


def test_dashboard_shows_calibration_status(rig):
    r = rig()
    assert r.win.dashboard.row_calibration._value.text() == "Not calibrated"
    r.calibrate()
    assert r.win.dashboard.row_calibration._value.text().startswith("Calibrated")


# ------------------------------------------------------------------------------------ camera lifecycle
def test_camera_opens_automatically_on_camera_page_and_not_on_home(rig):
    r = rig()
    assert not r.ctl.running                              # Home: camera stays off
    results = last_result(r)
    r.win.navigate("camera")
    assert r.ctl.running
    assert wait_until(lambda: len(results) >= 10)
    page = r.win.pages["camera"]
    assert wait_until(lambda: page.r_res._value.text() == f"{CAM_W} x {CAM_H}")
    assert page.r_det._value.text() == "Marker found"


def test_camera_stops_after_idle_grace_and_restarts_on_demand(rig):
    r = rig()
    r.win.navigate("camera")
    assert wait_until(lambda: r.ctl.camera_state[0] == "ok")
    r.win.navigate("home")
    assert r.win._camera_idle_timer.isActive() and r.ctl.running      # grace period: still warm
    r.win._stop_idle_camera()
    assert not r.ctl.running
    r.win.navigate("calibration")                                      # needed again -> restarts by itself
    assert r.ctl.running and wait_until(lambda: r.ctl.camera_state[0] == "ok")


def test_pressing_stop_is_respected_by_other_pages(rig):
    r = rig()
    r.win.navigate("camera")
    assert wait_until(lambda: r.ctl.camera_state[0] == "ok")
    r.ctl.stop()                                                       # user pressed "Stop camera"
    r.win.navigate("settings")
    r.win.navigate("calibration")
    assert not r.ctl.running


def test_camera_unavailable_is_reported_on_page_dashboard_and_whiteboard(rig):
    r = rig(opened=False)
    r.win.navigate("whiteboard")
    r.win.whiteboard.action_bar.track_btn.setChecked(True)
    assert wait_until(lambda: r.state.camera[0] == "error")
    assert wait_until(lambda: r.win.whiteboard.canvas.tracking_badge == ("error", "Camera unavailable"))
    assert r.win.whiteboard.canvas.pointer_pos is None
    r.win.navigate("camera")                                           # the page must still work
    assert "Not available" in r.win.pages["camera"].r_conn._value.text()


# ------------------------------------------------------------------------------------ whiteboard pointer
def test_tracked_pointer_lands_on_the_right_board_position(rig):
    r = rig()
    r.calibrate()
    r.win.navigate("whiteboard")
    wb = r.win.whiteboard
    wb.action_bar.track_btn.setChecked(True)
    assert wait_until(lambda: wb.canvas.pointer_pos is not None and wb.canvas.pointer_state == "tracking")
    assert wb.canvas.pointer_pos == pytest.approx(TRUTH, abs=8)
    assert wb.action_bar.track_chip.text().startswith("Tracking")


def test_pointer_stays_correct_when_the_window_is_resized(rig):
    r = rig()
    r.calibrate()
    r.win.navigate("whiteboard")
    wb = r.win.whiteboard
    wb.action_bar.track_btn.setChecked(True)
    assert wait_until(lambda: wb.canvas.pointer_pos is not None)
    for size in ((1100, 700), (1700, 1000), (1360, 840)):
        r.win.resize(*size)
        run_loop(80)
        board = wb.canvas.pointer_pos
        assert board == pytest.approx(TRUTH, abs=8)                    # board coordinates do not change ...
        rect = wb.canvas.board_rect()
        pos = wb.canvas.board_to_widget(*board)                        # ... only where they are painted
        assert (pos.x() - rect.x()) / rect.width() == pytest.approx(board[0] / BOARD_W, abs=1e-6)
        assert (pos.y() - rect.y()) / rect.height() == pytest.approx(board[1] / BOARD_H, abs=1e-6)
        assert rect.width() / rect.height() == pytest.approx(BOARD_W / BOARD_H, rel=1e-6)   # aspect kept
        assert wb.canvas.widget_to_board(pos) == pytest.approx(board, abs=1e-6)


def test_whiteboard_tracking_without_calibration_says_so(rig):
    r = rig()
    r.win.navigate("whiteboard")
    wb = r.win.whiteboard
    wb.action_bar.track_btn.setChecked(True)
    assert wait_until(lambda: wb.canvas.tracking_badge == ("warn", "Not calibrated"))
    assert wb.canvas.pointer_pos is None


def test_pointer_lost_is_indicated_and_stale_position_is_not_shown(rig):
    r = rig(lambda i: render_scene(TRUTH if i < 40 else None, noise=3))
    r.calibrate()
    r.win.navigate("whiteboard")
    wb = r.win.whiteboard
    wb.action_bar.track_btn.setChecked(True)
    assert wait_until(lambda: wb.canvas.pointer_pos is not None)
    assert wait_until(lambda: wb.canvas.tracking_badge == ("warn", "Pointer lost"), timeout_ms=6000)
    assert wb.canvas.pointer_pos is None


def test_pointer_outside_the_board_is_not_drawn(rig):
    outside = (-120.0, 450.0)                                          # left of the board, but still inside the image
    cam = project(board_to_cam_matrix(), *outside)
    assert 10 < cam[0] < CAM_W - 10 and 10 < cam[1] < CAM_H - 10       # the marker is visible to the camera
    r = rig(lambda i: _scene_with_disc(cam))
    r.calibrate()
    r.win.navigate("whiteboard")
    wb = r.win.whiteboard
    wb.action_bar.track_btn.setChecked(True)
    assert wait_until(lambda: wb.canvas.tracking_badge == ("warn", "Outside the board"))
    assert wb.canvas.pointer_pos is None


def _scene_with_disc(cam_xy):
    import cv2
    img = render_scene(None, noise=3)
    cv2.circle(img, (int(round(cam_xy[0])), int(round(cam_xy[1]))), 9, (60, 200, 40), -1)
    return img


def test_pointer_can_be_hidden_from_settings(rig):
    r = rig()
    r.calibrate()
    page = r.win.pages["settings"]
    assert r.win.whiteboard.canvas.pointer_visible
    page.pointer_box.setChecked(False)
    assert r.win.whiteboard.canvas.pointer_visible is False and r.settings.get("pointer.visible") is False


# ------------------------------------------------------------------------------------ calibration wizard
def test_calibration_wizard_end_to_end_and_survives_restart(rig, tmp_path):
    r = rig()
    results = last_result(r)
    r.win.navigate("calibration")
    page = r.win.pages["calibration"]
    assert wait_until(lambda: len(results) >= 5)
    page.capture()
    assert page.mode == "pick"
    for x, y in CAM_QUAD:                                              # TL, TR, BR, BL
        page._on_click(x, y, 1)
    assert page.mode == "review" and page.problems == [] and page.candidate is not None
    page.save()
    assert r.ctl.calibration is not None and (tmp_path / "calibration.json").is_file()
    assert np.allclose(r.ctl.calibration.corners, CAM_QUAD, atol=1.0)
    assert r.state.calibration[0] == "ok"
    # the live test: the mini map shows the pointer at its true board position
    assert wait_until(lambda: page.minimap.pointer is not None)
    assert page.minimap.pointer == pytest.approx(TRUTH, abs=8)

    # --- "restart the application": brand new settings + controller on the same files
    again = VisionController(Settings(tmp_path / "settings.json"), AppState(),
                             capture_factory=lambda i, b: FakeCapture(r.frames),
                             calibration_path=tmp_path / "calibration.json")
    assert again.calibration is not None
    assert np.allclose(again.calibration.corners, CAM_QUAD, atol=1.0)
    assert again.calibration.camera_size == CAM and again.state.calibration[0] == "ok"
    again.shutdown()


def test_calibration_wizard_rejects_degenerate_selection(rig):
    r = rig()
    results = last_result(r)
    r.win.navigate("calibration")
    page = r.win.pages["calibration"]
    assert wait_until(lambda: len(results) >= 5)
    page.capture()
    for x, y in ((100, 100), (200, 101), (300, 100), (400, 101)):      # four almost collinear points
        page._on_click(x, y, 1)
    assert page.problems and page.candidate is None
    page.save()                                                        # must do nothing
    assert r.ctl.calibration is None


def test_calibration_reset_and_recalibrate(rig):
    r = rig()
    results = last_result(r)
    r.win.navigate("calibration")
    page = r.win.pages["calibration"]
    assert wait_until(lambda: len(results) >= 5)
    page.capture()
    page._on_click(100, 100, 1)
    page._on_click(500, 100, 1)
    assert len(page.points) == 2
    page._on_click(0, 0, 2)                                            # right click removes the last corner
    assert len(page.points) == 1
    page.reset_selection()
    assert page.points == [] and page.mode == "pick"
    page.back_to_live()
    assert page.mode == "live"


def test_resolution_change_requests_recalibration(rig):
    r = rig(lambda i: render_scene(TRUTH, noise=3, size=(640, 480), quad=[(110, 60), (540, 80), (590, 420), (60, 400)]),
            size=(640, 480))                                           # 4:3 camera, calibration made at 16:9
    r.calibrate()
    r.win.navigate("whiteboard")
    wb = r.win.whiteboard
    wb.action_bar.track_btn.setChecked(True)
    assert wait_until(lambda: r.state.calibration[0] == "error")
    assert "ecalibrat" in r.state.calibration[1]
    assert wait_until(lambda: wb.canvas.tracking_badge == ("error", "Recalibrate (camera changed)"))
    assert wb.canvas.pointer_pos is None


# ------------------------------------------------------------------------------------ settings / tuning panel
def test_clicking_the_marker_picks_its_colour_and_the_wrapped_red_range_detects_it(rig):
    r = rig(lambda i: render_scene(TRUTH, marker_color=RED, noise=3))
    results = last_result(r)
    r.win.navigate("settings")
    page = r.win.pages["settings"]
    assert wait_until(lambda: len(results) >= 5)
    assert results[-1].detection.detection is None                     # default (green) range cannot see a red marker
    cam_xy = project(board_to_cam_matrix(), *TRUTH)
    page._on_pick(cam_xy[0], cam_xy[1], 1)
    low, high = r.ctl.detection_params.hsv_low, r.ctl.detection_params.hsv_high
    assert low[0] > high[0]                                            # hue range wraps around 0
    assert wait_until(lambda: results[-1].detection.detection is not None)
    det = results[-1].detection.detection
    assert (det.x, det.y) == pytest.approx(cam_xy, abs=2)
    assert r.settings.get("detection.hsv_low") == list(low)            # persisted without touching any file


def test_mask_is_only_produced_while_the_tuning_panel_is_visible(rig):
    r = rig()
    results = last_result(r)
    r.win.navigate("settings")
    assert r.ctl.want_mask
    assert wait_until(lambda: results and results[-1].mask is not None)
    assert page_mask_is_binary(results[-1].mask)
    r.win.navigate("camera")
    assert not r.ctl.want_mask
    # results queued before the switch may still carry a mask; once they drain, none do
    assert wait_until(lambda: len(results) > 5 and all(x.mask is None for x in results[-4:]))


def page_mask_is_binary(mask):
    return set(np.unique(mask).tolist()) <= {0, 255}


def test_sliders_change_the_running_detector_and_are_saved(rig):
    r = rig()
    r.win.navigate("settings")
    page = r.win.pages["settings"]
    page.s_min._slider.setValue(400)
    page.s_kernel._slider.setValue(7)
    page.s_hl._slider.setValue(40)
    page.s_alpha._slider.setValue(30)
    page.s_lost._slider.setValue(900)
    d, t = r.ctl.detection_params, r.ctl.tracker_params
    assert d.min_area == 400 and d.kernel_size == 7 and d.hsv_low[0] == 40
    assert t.alpha == pytest.approx(0.30) and t.lost_timeout_ms == 900
    assert r.settings.get("detection.min_area") == 400 and r.settings.get("detection.alpha") == pytest.approx(0.30)


def test_presets_and_reset_detection(rig):
    r = rig()
    page = r.win.pages["settings"]
    page._apply_preset("Red")
    assert r.ctl.detection_params.hsv_low[0] > r.ctl.detection_params.hsv_high[0]
    page._apply_preset("Blue")
    assert 95 <= r.ctl.detection_params.hsv_low[0] < r.ctl.detection_params.hsv_high[0] <= 130
    page._reset_detection()
    assert r.ctl.detection_params.hsv_low == (35, 90, 70)
    assert int(page.s_hl.value()) == 35


def test_changing_resolution_updates_settings(rig):
    r = rig()
    page = r.win.pages["settings"]
    page.res_combo.setCurrentIndex(0)
    assert (r.settings.get("camera.width"), r.settings.get("camera.height")) == (640, 480)


# ------------------------------------------------------------------------------------ reset / destructive actions
def test_reset_application_restores_defaults_but_keeps_calibration_and_camera_choice(rig, monkeypatch, tmp_path):
    r = rig()
    r.calibrate()
    r.settings.set("detection.min_area", 999)
    r.settings.set("pen.thickness", 33)
    r.settings.set("camera.index", 2)
    r.win.navigate("whiteboard")
    r.win.whiteboard.canvas.pointer_down(100, 100)
    r.win.whiteboard.canvas.pointer_up(500, 300)
    assert r.win.whiteboard.engine.has_ink
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    r.win.pages["settings"]._confirm_reset()
    assert r.settings.get("detection.min_area") == 150 and r.ctl.detection_params.min_area == 150
    assert r.settings.get("pen.thickness") == 6 and r.win.whiteboard.canvas.thickness == 6
    assert r.settings.get("camera.index") == 2                         # kept
    assert r.ctl.calibration is not None and (tmp_path / "calibration.json").is_file()   # kept
    assert not r.win.whiteboard.engine.has_ink


def test_deleting_calibration_asks_first(rig, monkeypatch, tmp_path):
    r = rig()
    r.calibrate()
    page = r.win.pages["settings"]
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    page._delete_calibration()
    assert r.ctl.calibration is not None
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    page._delete_calibration()
    assert r.ctl.calibration is None and not (tmp_path / "calibration.json").exists()
    assert r.state.calibration[0] == "warn"


def test_closing_the_window_stops_the_worker_threads(qapp, tmp_path):
    r = Rig(tmp_path, lambda i: render_scene(TRUTH))
    r.win.navigate("camera")
    assert wait_until(lambda: r.ctl.camera_state[0] == "ok")
    r.close()
    assert not r.ctl.running
