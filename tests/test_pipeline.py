"""Tests for the performance / robustness fixes and the full pointer
pipeline (threaded camera -> detector -> homography -> tracker)."""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

from calibration.calibration_ui import HSVCalibrationScreen  # noqa: E402
from config.settings import DEFAULT_SETTINGS  # noqa: E402
from detection.color_detector import ColorDetector  # noqa: E402
from detection.tracker import PointerTracker  # noqa: E402
from interface.components import layout_row  # noqa: E402
from utils.geometry import is_clockwise_convex  # noqa: E402
from utils.image_processing import bgr_to_hsv  # noqa: E402


def _frame(w, h, center, radius, bgr=(0, 255, 0)):
    f = np.full((h, w, 3), (40, 40, 60), np.uint8)
    cv2.circle(f, center, radius, bgr, -1)
    return f


@pytest.mark.parametrize("size", [(640, 480), (1280, 720), (1920, 1080)])
def test_downscaled_detection_matches_full_resolution(size):
    w, h = size
    center = (int(w * 0.62), int(h * 0.4))
    frame = _frame(w, h, center, radius=max(18, w // 50))
    cfg = DEFAULT_SETTINGS["marker_hsv"]
    full = ColorDetector(cfg, 400, 0.25, downscale=1).detect(frame)
    fast = ColorDetector(cfg, 400, 0.25).detect(frame)       # automatic
    assert full is not None and fast is not None, "marker lost by downscaling"
    assert abs(full.x - fast.x) <= 3 and abs(full.y - fast.y) <= 3
    assert abs(fast.x - center[0]) <= 3 and abs(fast.y - center[1]) <= 3


def test_downscale_is_automatic_and_only_for_large_frames():
    det = ColorDetector(DEFAULT_SETTINGS["marker_hsv"])
    assert det.stride_for(np.zeros((480, 640, 3), np.uint8)) == 1
    assert det.stride_for(np.zeros((720, 1280, 3), np.uint8)) == 2
    assert det.stride_for(np.zeros((1080, 1920, 3), np.uint8)) == 3


def test_red_marker_hue_wraps_around_zero():
    """Regression: sampling clamped the hue to [0, 360], so a red marker
    (hue ~0/360) produced a range that missed half of its pixels."""
    red = np.full((41, 41, 3), (0, 0, 255), np.uint8)
    # Half the patch slightly toward orange, half slightly toward magenta.
    red[:, :20] = (0, 40, 255)
    red[:, 21:] = (40, 0, 255)
    r = HSVCalibrationScreen.ranges_from_patch(bgr_to_hsv(red))
    assert r["h_min"] > r["h_max"], "range must wrap (h_min > h_max)"
    frame = _frame(640, 480, (300, 200), 30, bgr=(0, 0, 255))
    det = ColorDetector(r, 400, 0.25, downscale=1).detect(frame)
    assert det is not None and abs(det.x - 300) <= 2


def test_tracker_current_honours_loss_timeout():
    t = PointerTracker(alpha=1.0, loss_timeout=1.0)
    assert t.current(now=0.0) is None                # never initialised
    t.update((10.0, 20.0), now=100.0)
    assert t.current(now=100.5) == (10.0, 20.0)      # grace period
    assert t.current(now=101.5) is None              # lost


def test_corner_order_validation():
    cw = np.array([[0, 0], [100, 0], [100, 80], [0, 80]], float)
    assert is_clockwise_convex(cw)
    assert not is_clockwise_convex(cw[::-1])                     # reversed
    assert not is_clockwise_convex(cw[[0, 2, 1, 3]])             # bow-tie


@pytest.mark.parametrize("n", [3, 8, 14])
def test_layout_row_never_overflows(n):
    area = pygame.Rect(16, 0, 600, 60)
    rects = layout_row(area, [110] * n, gap=10)
    assert len(rects) == n
    assert all(area.contains(r) for r in rects)
    assert all(a.right <= b.left for a, b in zip(rects, rects[1:]))


def test_end_to_end_camera_pointer(monkeypatch, tmp_path):
    """Simulated camera thread -> detection -> calibration -> pointer, and
    the pointer must agree with the detected marker position."""
    from tests.test_app_integration import make_app
    app = make_app(monkeypatch, tmp_path, 1280, 720, pointer_mode="camera")
    fw, fh = 640, 480
    # Calibrate the whole camera image onto the whole board.
    app.calibration.reset_clicks()
    for p in [(0, 0), (fw, 0), (fw, fh), (0, fh)]:
        app.calibration.add_click(p)
    assert app.calibration.compute() is not None

    seen, deadline = 0, time.time() + 3.0
    while time.time() < deadline and seen < 25:
        app.step(0.016)
        if app.pointer_visible and app.last_detection is not None:
            seen += 1
            d = app.last_detection
            assert app.pointer_source == "camera"
            expect = (d.x * 1280 / fw, d.y * 720 / fh)
            # EMA smoothing lags a moving marker slightly: 150 px is far
            # tighter than any mapping error (flip, wrong scale, offset).
            assert abs(app.pointer_pos[0] - expect[0]) < 150
            assert abs(app.pointer_pos[1] - expect[1]) < 150
        time.sleep(0.01)
    assert seen >= 10, "pointer never appeared from the camera pipeline"
    app._shutdown()


def test_saved_calibration_is_rescaled_when_window_size_changes(
        monkeypatch, tmp_path):
    """A calibration made at 1280x720 must still map the marker to the
    same *relative* board position after switching to 1920x1080."""
    from tests.test_app_integration import make_app
    app = make_app(monkeypatch, tmp_path, 1280, 720)
    for p in [(100, 80), (540, 90), (560, 400), (90, 410)]:
        app.calibration.add_click(p)
    assert app.calibration.compute() is not None
    assert app.calibration.save()
    probe = (300.0, 240.0)
    x1, y1 = app.calibration.mapper.camera_to_board(probe)
    app._shutdown()

    big = make_app(monkeypatch, tmp_path, 1920, 1080)
    assert big.calibration.mapper.is_calibrated
    assert big.calibration.mapper.board_size == (1920, 1080)
    x2, y2 = big.calibration.mapper.camera_to_board(probe)
    assert abs(x2 - x1 * 1.5) < 1e-6 and abs(y2 - y1 * 1.5) < 1e-6
    big._shutdown()
