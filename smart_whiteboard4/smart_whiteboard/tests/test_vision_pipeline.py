"""End-to-end vision tests: fake webcam -> camera thread -> vision thread -> signals.

The fake capture plays synthetic scenes whose geometry is known, so the final *board coordinates*
can be compared with the ground truth.
"""
import time

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QTimer

from core.app_state import AppState
from core.calibration import Calibration
from core.coordinate_mapping import CoordinateMapper
from core.detector import DetectionParams
from core.settings import Settings
from core.tracker import LOST, TRACKING, TrackerParams
from core.vision_engine import VisionController, VisionWorker
from tests.qt_helpers import run_loop, wait_until
from tests.synthetic import (BOARD_H, BOARD_W, CAM_H, CAM_QUAD, CAM_W, FakeCapture, render_scene)

CAM = (CAM_W, CAM_H)


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def calibrated_mapper():
    return CoordinateMapper(Calibration.from_corners(CAM_QUAD, CAM, (BOARD_W, BOARD_H)))


def new_worker(mapper=None, **tkw):
    from core.camera import FrameMailbox
    w = VisionWorker(FrameMailbox(), DetectionParams(), TrackerParams(**tkw))
    w.set_mapper(mapper)
    return w


# ------------------------------------------------------------------ pipeline without threads
@pytest.mark.parametrize("board_pt", [(200, 150), (800, 450), (1400, 800), (1000, 120)])
def test_mapped_board_coordinates_match_ground_truth(board_pt):
    worker = new_worker(calibrated_mapper(), alpha=1.0)
    res = worker.process(render_scene(board_pt, noise=5), 0.0)
    assert res.track.state == TRACKING and res.board is not None and res.calib_state == "ok"
    assert (res.board.x, res.board.y) == pytest.approx(board_pt, abs=6)           # < 6 board px of 1600


def test_marker_moving_across_the_board_is_followed_accurately():
    worker = new_worker(calibrated_mapper(), alpha=1.0)
    errors = []
    for i in range(40):
        truth = (150 + i * 30, 150 + 12 * np.sin(i / 4) * 20 + i * 8)
        res = worker.process(render_scene(truth, noise=4), i / 30)
        errors.append(np.hypot(res.board.x - truth[0], res.board.y - truth[1]))
    assert max(errors) < 8 and np.mean(errors) < 4


def test_uncalibrated_tracking_gives_camera_position_but_no_board_position():
    res = new_worker(None).process(render_scene((800, 450)), 0.0)
    assert res.track.state == TRACKING and res.board is None and res.calib_state == "none"


def test_pointer_outside_the_board_is_rejected():
    worker = new_worker(calibrated_mapper(), alpha=1.0)
    res = worker.process(render_scene(None, extra=[lambda im: __import__("cv2").circle(im, (15, 15), 9, (60, 200, 40), -1)]), 0.0)
    assert res.track.state == TRACKING and res.board is None                        # seen by camera, not on the board


def test_pointer_lost_when_marker_disappears():
    worker = new_worker(calibrated_mapper(), alpha=1.0, lost_timeout_ms=300)
    assert worker.process(render_scene((800, 450)), 0.0).track.state == TRACKING
    held = worker.process(render_scene(None), 0.1)
    assert held.track.state == "holding" and held.board is not None and not held.track.valid
    lost = worker.process(render_scene(None), 0.5)
    assert lost.track.state == LOST and lost.board is None and lost.detection.status == "no_pixels"


def test_resolution_change_scaled_and_mismatch():
    worker = new_worker(calibrated_mapper(), alpha=1.0)
    half = render_scene((800, 450), size=(CAM_W // 2, CAM_H // 2),
                        quad=[(x / 2, y / 2) for x, y in CAM_QUAD], radius=9)   # >= min_area at 320x180
    res = worker.process(half, 0.0)
    assert res.calib_state == "scaled" and res.board is not None
    assert (res.board.x, res.board.y) == pytest.approx((800, 450), abs=12)
    odd = render_scene((800, 450), size=(640, 480))
    res = new_worker(calibrated_mapper(), alpha=1.0).process(odd, 0.0)
    assert res.calib_state == "mismatch" and res.board is None and "recalibrate" in res.calib_message.lower()


def test_mask_only_returned_when_requested():
    w = new_worker(None)
    assert w.process(render_scene((800, 450)), 0.0).mask is None
    w.set_want_mask(True)
    m = w.process(render_scene((800, 450)), 0.1).mask
    assert m is not None and m.dtype == np.uint8 and m.max() == 255


# ------------------------------------------------------------------ full threaded engine
def make_controller(tmp_path, frames, **kw):
    settings = Settings(tmp_path / "s.json")
    state = AppState()
    ctl = VisionController(settings, state, capture_factory=lambda i, b: FakeCapture(frames, **kw),
                           calibration_path=tmp_path / "cal.json")
    return ctl, state


def test_threaded_engine_tracks_and_reports_status(qapp, tmp_path):
    truth = (900, 400)
    ctl, state = make_controller(tmp_path, lambda i: render_scene(truth, noise=4))
    ctl.set_calibration(Calibration.from_corners(CAM_QUAD, CAM, (BOARD_W, BOARD_H)))
    results = []
    ctl.resultReady.connect(results.append)
    ctl.start()
    try:
        assert wait_until(lambda: len(results) >= 15)
        last = results[-1]
        assert last.board is not None and (last.board.x, last.board.y) == pytest.approx(truth, abs=6)
        assert wait_until(lambda: state.camera[0] == "ok" and "640x360" in state.camera[1])
        assert state.tracking == ("ok", "Tracking") and state.calibration[0] == "ok"
        assert wait_until(lambda: ctl.camera_fps > 20)
        assert last.tracking_fps > 10
    finally:
        ctl.shutdown()


def test_gui_thread_stays_responsive_while_vision_runs(qapp, tmp_path):
    ctl, _ = make_controller(tmp_path, lambda i: render_scene((800, 450), noise=4))
    ticks = []
    timer = QTimer()
    timer.setInterval(10)
    clock = time.perf_counter
    timer.timeout.connect(lambda: ticks.append(clock()))
    timer.start()
    ctl.start()
    try:
        run_loop(1200)
    finally:
        timer.stop()
        ctl.shutdown()
    gaps = np.diff(ticks)
    assert len(ticks) > 40 and gaps.max() < 0.25                                   # event loop never blocked


def test_camera_unavailable_is_reported_without_crashing(qapp, tmp_path):
    settings, state = Settings(tmp_path / "s.json"), AppState()
    ctl = VisionController(settings, state, capture_factory=lambda i, b: FakeCapture(lambda n: None, opened=False),
                           calibration_path=tmp_path / "cal.json")
    ctl.start()
    try:
        assert wait_until(lambda: state.camera[0] == "error")
        assert "Camera could not be opened" in state.camera[1] and not ctl.resolution
        assert state.tracking[0] == "off"
    finally:
        ctl.shutdown()


def test_camera_disconnect_then_reconnect(qapp, tmp_path):
    calls = {"n": 0}

    def factory(i, b):
        calls["n"] += 1
        if calls["n"] == 1:                                    # first device dies after 20 frames
            return FakeCapture(lambda n: render_scene((800, 450)) if n < 20 else None, fps=200)
        return FakeCapture(lambda n: render_scene((800, 450)), fps=60)

    settings, state = Settings(tmp_path / "s.json"), AppState()
    ctl = VisionController(settings, state, capture_factory=factory, calibration_path=tmp_path / "cal.json")
    seen = []
    ctl.cameraStatusChanged.connect(lambda s, t: seen.append((s, t)))
    ctl.start()
    try:
        assert wait_until(lambda: any("disconnected" in t for _, t in seen), 5000)
        assert wait_until(lambda: calls["n"] >= 2 and state.camera[0] == "ok", 6000)    # reconnected on its own
    finally:
        ctl.shutdown()


def test_camera_restart_without_restarting_the_app(qapp, tmp_path):
    ctl, state = make_controller(tmp_path, lambda i: render_scene((800, 450)))
    got = []
    ctl.resultReady.connect(got.append)
    ctl.start()
    try:
        assert wait_until(lambda: len(got) > 5)
        ctl.stop()
        assert state.camera[0] == "off" and not ctl.running
        got.clear()
        ctl.restart()
        assert wait_until(lambda: len(got) > 5) and ctl.running
    finally:
        ctl.shutdown()


def test_signal_loss_is_announced_when_frames_stop(qapp, tmp_path):
    ctl, state = make_controller(tmp_path, lambda i: render_scene((800, 450)) if i < 30 else None, fps=200)
    lost = []
    ctl.signalLost.connect(lambda: lost.append(1))
    ctl.start()
    try:
        assert wait_until(lambda: bool(lost), 5000)
        assert state.tracking[0] == "off"
    finally:
        ctl.shutdown()


def test_settings_changes_reach_the_running_worker(qapp, tmp_path):
    ctl, _ = make_controller(tmp_path, lambda i: render_scene((800, 450)))
    got = []
    ctl.resultReady.connect(got.append)
    ctl.start()
    try:
        assert wait_until(lambda: len(got) > 3 and got[-1].track.state == TRACKING)
        ctl.set_detection_params(DetectionParams(hsv_low=(100, 90, 70), hsv_high=(130, 255, 255)))   # blue only
        got.clear()
        assert wait_until(lambda: got and got[-1].track.state != TRACKING, 4000)
        assert ctl.settings.get("detection.hsv_low") == [100, 90, 70]
    finally:
        ctl.shutdown()


def test_calibration_survives_application_restart(qapp, tmp_path):
    ctl, state = make_controller(tmp_path, lambda i: None)
    ctl.set_calibration(Calibration.from_corners(CAM_QUAD, CAM, (BOARD_W, BOARD_H)))
    assert (tmp_path / "cal.json").exists()
    again = VisionController(Settings(tmp_path / "s.json"), AppState(), calibration_path=tmp_path / "cal.json")
    assert again.calibration is not None and again.mapper is not None
    assert again.calibration.camera_size == CAM and np.allclose(again.calibration.H, ctl.calibration.H)
    assert again.state.calibration[0] == "ok"
    p = again.mapper.camera_to_board(*CAM_QUAD[2])
    assert (p.x, p.y) == pytest.approx((BOARD_W, BOARD_H))


def test_corrupt_calibration_file_is_reported_not_fatal(qapp, tmp_path):
    (tmp_path / "cal.json").write_text("{ broken")
    ctl = VisionController(Settings(tmp_path / "s.json"), AppState(), calibration_path=tmp_path / "cal.json")
    assert ctl.calibration is None and ctl.calibration_error and ctl.state.calibration[0] == "error"
