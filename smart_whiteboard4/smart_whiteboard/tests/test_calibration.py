"""Homography, calibration validation and persistence."""
import json

import cv2
import numpy as np
import pytest

from core.calibration import (Calibration, CalibrationError, check_compatibility, load_calibration,
                              order_corners, save_calibration, validate_corners)
from core.homography import (HomographyError, apply_homography, estimate_homography,
                             homography_problems, reprojection_error)
from tests.synthetic import BOARD_H, BOARD_W, CAM_H, CAM_QUAD, CAM_W

BOARD = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
CAM = (CAM_W, CAM_H)


def make_cal(quad=CAM_QUAD, cam=CAM, mirror=False):
    return Calibration.from_corners(quad, cam, (BOARD_W, BOARD_H), mirror)


# ------------------------------------------------------------------ homography
def test_homography_matches_opencv():
    mine = estimate_homography(CAM_QUAD, BOARD)
    ref = cv2.getPerspectiveTransform(np.float32(CAM_QUAD), np.float32(BOARD))
    assert np.allclose(mine / mine[2, 2], ref / ref[2, 2], rtol=1e-5, atol=1e-5)


def test_homography_maps_the_four_points_exactly():
    H = estimate_homography(CAM_QUAD, BOARD)
    assert np.allclose(apply_homography(H, CAM_QUAD), BOARD, atol=1e-6)
    assert reprojection_error(H, CAM_QUAD, BOARD) < 1e-6


def test_identity_translation_and_scale_cases():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert np.allclose(estimate_homography(sq, sq), np.eye(3), atol=1e-9)
    H = estimate_homography(sq, [(5, 5), (25, 5), (25, 25), (5, 25)])            # scale 2 + shift 5
    assert np.allclose(apply_homography(H, (3, 4)), (11, 13))


def test_homogeneous_normalisation_divides_by_w():
    H = np.array([[1, 0, 0], [0, 1, 0], [0.001, 0, 1.0]])
    assert apply_homography(H, (100, 50)) == pytest.approx((100 / 1.1, 50 / 1.1))


def test_point_on_horizon_line_returns_nan_not_inf():
    H = np.array([[1, 0, 0], [0, 1, 0], [1, 0, 0.0]])
    out = apply_homography(H, (0, 5))                                           # W = 0
    assert np.isnan(out).all()


def test_least_squares_with_more_than_four_points():
    src = [(0, 0), (4, 0), (4, 3), (0, 3), (2, 1.5)]
    dst = [(0, 0), (8, 0), (8, 6), (0, 6), (4, 3)]
    assert np.allclose(apply_homography(estimate_homography(src, dst), src), dst, atol=1e-9)


@pytest.mark.parametrize("pts", [[(0, 0), (1, 1), (2, 2), (3, 3)], [(5, 5)] * 4])
def test_degenerate_points_raise(pts):
    with pytest.raises(HomographyError):
        estimate_homography(pts, BOARD)


def test_too_few_or_non_finite_points_raise():
    with pytest.raises(HomographyError):
        estimate_homography(CAM_QUAD[:3], BOARD[:3])
    with pytest.raises(HomographyError):
        estimate_homography([(0, 0), (1, 0), (float("nan"), 1), (0, 1)], BOARD)


def test_homography_problems():
    assert homography_problems(np.eye(3)) == []
    assert homography_problems(np.zeros((3, 3)))
    assert homography_problems(np.full((3, 3), np.nan))
    assert homography_problems(np.eye(2))
    assert homography_problems("x")


# ------------------------------------------------------------------ corner validation
def test_valid_corners_accepted():
    assert validate_corners(CAM_QUAD, CAM) == []


@pytest.mark.parametrize("bad,fragment", [
    (CAM_QUAD[:3], "Four corners"),
    ([(10, 10), (10, 10.5), (300, 300), (20, 300)], "same place"),
    ([(0, 0), (900, 0), (500, 300), (20, 300)], "outside"),
    ([CAM_QUAD[1], CAM_QUAD[0], CAM_QUAD[3], CAM_QUAD[2]], "order"),            # mirrored order
    ([(100, 50), (500, 60), (300, 150), (80, 300)], "convex"),
    ([(300, 150), (320, 150), (320, 170), (300, 170)], "too small"),
    ([(float("nan"), 1), (2, 2), (3, 3), (4, 4)], "invalid"),
])
def test_invalid_corners_rejected_with_reason(bad, fragment):
    problems = validate_corners(bad, CAM)
    assert problems and fragment in problems[0]


def test_order_corners_from_any_click_order():
    rng = np.random.default_rng(4)
    for _ in range(20):
        shuffled = [CAM_QUAD[i] for i in rng.permutation(4)]
        assert order_corners(shuffled) == [tuple(map(float, p)) for p in CAM_QUAD]
    with pytest.raises(CalibrationError):
        order_corners(CAM_QUAD[:3])


# ------------------------------------------------------------------ calibration object
def test_calibration_builds_valid_matrix():
    cal = make_cal()
    assert cal.rms_error < 1e-6 and homography_problems(cal.H) == []
    assert np.allclose(cal.H @ cal.H_inv / (cal.H @ cal.H_inv)[2, 2], np.eye(3), atol=1e-9)


def test_invalid_calibration_raises_calibration_error():
    with pytest.raises(CalibrationError):
        make_cal(quad=[(100, 50), (500, 60), (300, 150), (80, 300)])
    with pytest.raises(CalibrationError):
        Calibration.from_corners(CAM_QUAD, CAM, (0, 900))


# ------------------------------------------------------------------ persistence
def test_calibration_json_roundtrip_keeps_resolution(tmp_path):
    path = tmp_path / "cal.json"
    cal = make_cal(mirror=True)
    save_calibration(path, cal)
    data = json.loads(path.read_text())
    assert data["camera_resolution"] == [CAM_W, CAM_H] and data["mirror"] is True
    assert data["corner_order"][0] == "Top-left" and len(data["homography_camera_to_board"]) == 3
    loaded, err = load_calibration(path)
    assert err is None and np.allclose(loaded.H, cal.H) and loaded.corners == cal.corners
    assert loaded.camera_size == (CAM_W, CAM_H) and loaded.mirror is True


def test_missing_file_is_not_an_error(tmp_path):
    assert load_calibration(tmp_path / "none.json") == (None, None)


@pytest.mark.parametrize("content", ["{ not json", "[]", "{}", '{"version": 1}', '{"version": 99}'])
def test_corrupt_files_give_clear_error_not_exception(tmp_path, content):
    path = tmp_path / "cal.json"
    path.write_text(content)
    cal, err = load_calibration(path)
    assert cal is None and err and "recalibrate" in err.lower()


def test_tampered_matrix_or_corners_are_detected(tmp_path):
    path = tmp_path / "cal.json"
    save_calibration(path, make_cal())
    data = json.loads(path.read_text())
    data["homography_camera_to_board"][0][0] *= 2
    path.write_text(json.dumps(data))
    assert load_calibration(path)[0] is None
    data = json.loads(path.read_text())
    data["corners_px"] = [[0, 0], [1, 1], [2, 2], [3, 3]]
    path.write_text(json.dumps(data))
    cal, err = load_calibration(path)
    assert cal is None and err


def test_failed_save_leaves_no_partial_file(tmp_path, monkeypatch):
    path = tmp_path / "cal.json"
    save_calibration(path, make_cal())
    before = path.read_text()
    monkeypatch.setattr(json, "dump", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        save_calibration(path, make_cal())
    assert path.read_text() == before and list(tmp_path.glob("*.tmp")) == []


# ------------------------------------------------------------------ resolution changes
def test_compatibility_rules():
    cal = make_cal()
    assert check_compatibility(cal, CAM, False)[0] == "ok"
    assert check_compatibility(cal, (CAM_W // 2, CAM_H // 2), False)[0] == "scaled"
    state, msg = check_compatibility(cal, (640, 480), False)
    assert state == "mismatch" and "recalibrate" in msg.lower()
    assert check_compatibility(cal, CAM, True)[0] == "mismatch"
