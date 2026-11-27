"""Test with the REAL built-in webcam (skipped automatically when no camera can be opened).

Run it on your laptop, with other camera apps (Teams, Zoom, browser tabs) closed:

    python -m pytest tests/test_camera_live.py -s -v

It checks the whole chain with actual frames: camera thread -> vision thread -> detector -> tracker,
and prints the measured resolution, camera FPS, tracking FPS and processing time.
"""
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from core.app_state import AppState
from core.camera import probe_cameras
from core.detector import DetectionParams, detect
from core.settings import Settings
from core.vision_engine import VisionController
from tests.qt_helpers import wait_until


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def cameras():
    found = probe_cameras(4)
    if not found:
        pytest.skip("no webcam available on this machine")
    return found


def test_real_webcam_delivers_frames_and_the_pipeline_runs(qapp, cameras, tmp_path):
    index = cameras[0][0]
    settings = Settings(tmp_path / "s.json")
    ctl = VisionController(settings, AppState(), calibration_path=tmp_path / "cal.json")
    results = []
    ctl.resultReady.connect(results.append)
    ctl.start(index)
    try:
        assert wait_until(lambda: len(results) >= 30, timeout_ms=15000), "no frames received from the webcam"
        frame = results[-1].frame
        assert frame.ndim == 3 and frame.shape[2] == 3 and frame.dtype == np.uint8
        assert frame.std() > 1.0, "frame is uniform: the camera is covered or returns black frames"
        assert ctl.state.camera[0] == "ok"
        print(f"\n  camera {index}: {frame.shape[1]}x{frame.shape[0]}  camera FPS {ctl.camera_fps:.1f}  "
              f"tracking FPS {results[-1].tracking_fps:.1f}  processing {results[-1].process_ms:.1f} ms")
        assert results[-1].tracking_fps > 5
    finally:
        ctl.shutdown()


def test_real_webcam_can_be_restarted(qapp, cameras, tmp_path):
    ctl = VisionController(Settings(tmp_path / "s.json"), AppState(), calibration_path=tmp_path / "cal.json")
    got = []
    ctl.resultReady.connect(got.append)
    try:
        ctl.start(cameras[0][0])
        assert wait_until(lambda: len(got) >= 5, timeout_ms=15000)
        ctl.stop()
        assert not ctl.running
        got.clear()
        ctl.start()
        assert wait_until(lambda: len(got) >= 5, timeout_ms=15000), "camera did not restart"
    finally:
        ctl.shutdown()


def test_detector_runs_on_a_real_frame(qapp, cameras, tmp_path):
    ctl = VisionController(Settings(tmp_path / "s.json"), AppState(), calibration_path=tmp_path / "cal.json")
    got = []
    ctl.resultReady.connect(got.append)
    ctl.start(cameras[0][0])
    try:
        assert wait_until(lambda: len(got) >= 3, timeout_ms=15000)
        res = detect(got[-1].frame, DetectionParams())
        assert res.status in {"ok", "no_pixels", "area_too_small", "area_too_large", "low_confidence", "noisy"}
        assert res.mask.shape[1] <= DetectionParams().detect_width
    finally:
        ctl.shutdown()
