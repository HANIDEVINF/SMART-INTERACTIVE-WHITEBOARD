"""Geometry + detection tests on synthetic data (no camera needed).

Run:  python -m pytest -q        or        python tests/test_vision.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from smartboard.config import Config
from smartboard.vision import imgproc
from smartboard.vision.calibration import (Calibration, apply_homography, calibration_targets,
                                           compute_homography)
from smartboard.vision.camera import SyntheticCamera
from smartboard.vision.detector import RedDotDetector
from smartboard.vision.pointer_source import VisionPointerSource
from smartboard.vision.tracker import OneEuroFilter2D

BOARD = (1920, 1080)
# an oblique camera: board corners land on a skewed quadrilateral
CAM_QUAD = np.array([[210, 120], [1050, 80], [1120, 640], [140, 600]], float)
BOARD_QUAD = np.array([[0, 0], [BOARD[0], 0], [BOARD[0], BOARD[1]], [0, BOARD[1]]], float)


def make_h_board_to_cam():
    return compute_homography(BOARD_QUAD, CAM_QUAD)


def test_homography_recovers_known_transform():
    H = make_h_board_to_cam()
    pts = np.random.default_rng(0).uniform([0, 0], BOARD, (20, 2))
    back = apply_homography(np.linalg.inv(H), apply_homography(H, pts))
    assert np.abs(back - pts).max() < 1e-6


def test_hsv_matches_opencv():
    import cv2
    img = np.random.default_rng(1).integers(0, 256, (40, 50, 3), dtype=np.uint8)
    h, s, v = imgproc.bgr_to_hsv(img)
    ref = cv2.cvtColor(img, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)   # H 0..255 == 0..360
    assert np.abs(v - ref[..., 2] / 255).max() < 0.01
    sat_ok = ref[..., 1] > 0
    assert np.abs(s - ref[..., 1] / 255)[sat_ok].max() < 0.01
    col = (ref[..., 1] > 40) & (ref[..., 2] > 40)
    dh = np.abs(h - ref[..., 0] * 360 / 256)[col]
    dh = np.minimum(dh, 360 - dh)
    assert dh.max() < 3.0


def test_bilinear_resize_close_to_opencv():
    import cv2
    img = np.random.default_rng(2).integers(0, 256, (30, 40, 3), dtype=np.uint8)
    mine = imgproc.resize_bilinear(img, 97, 71)
    ref = cv2.resize(img, (97, 71), interpolation=cv2.INTER_LINEAR)
    assert np.abs(mine.astype(int) - ref.astype(int)).mean() < 1.5


def test_end_to_end_mapping_accuracy():
    cfg = Config()
    Hbc = make_h_board_to_cam()
    target = {"p": None}
    cam = SyntheticCamera(1280, 720, BOARD, Hbc, lambda: target["p"])
    calib = Calibration(*BOARD)
    src = VisionPointerSource(cfg, cam, calib)

    # --- calibration: dot sits on the 4 targets, we record the detected camera positions
    targets = calibration_targets(*BOARD, cfg.calibration.target_margin)
    cam_pts = []
    for tpt in targets:
        target["p"] = tuple(tpt)
        for _ in range(12):
            s = src.update()
        cam_pts.append(s.cam)
    calib.fit(cam_pts, targets)
    src.refresh_roi()

    # --- validation on unseen points
    errs = []
    rng = np.random.default_rng(3)
    for _ in range(25):
        p = rng.uniform([200, 150], [BOARD[0] - 200, BOARD[1] - 150])
        target["p"] = tuple(p)
        src.track_cam.reset()
        src.track_board.reset()
        for _ in range(10):
            s = src.update()
        assert s.tracked and s.board is not None
        errs.append(np.hypot(s.board[0] - p[0], s.board[1] - p[1]))
    print("mean error %.2f px, max %.2f px (board 1920x1080)" % (np.mean(errs), np.max(errs)))
    assert np.mean(errs) < 8 and np.max(errs) < 20


def test_red_projected_patch_is_ignored():
    cfg = Config()
    cam = SyntheticCamera(1280, 720, BOARD, make_h_board_to_cam(), lambda: None)
    det = RedDotDetector(cfg.detection).detect(cam.read())
    assert det is None


def test_tracker_holds_then_loses():
    from smartboard.vision.tracker import PointerTracker
    t = PointerTracker(Config().tracking)
    p, tr, lost = t.update((10, 10), 0.0)
    assert tr and p is not None
    for i in range(Config().tracking.max_lost_frames):
        p, tr, lost = t.update(None, 0.03 * (i + 1))
        assert p is not None and not tr
    p, tr, lost = t.update(None, 1.0)
    assert p is None


def test_one_euro_reduces_jitter():
    rng = np.random.default_rng(4)
    f = OneEuroFilter2D()
    raw = 500 + rng.normal(0, 2.0, (200, 2))
    out = np.array([f(tuple(p), i / 30) for i, p in enumerate(raw)])
    assert out[50:].std() < raw[50:].std() * 0.6


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
