"""Tests for the NumPy homography implementation."""

import numpy as np
import pytest

from utils.geometry import (compute_homography, is_valid_quad,
                            point_in_rect, transform_points)


def test_identity_homography():
    src = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=float)
    H = compute_homography(src, src.copy())
    out = transform_points(H, np.array([[50, 50]]))
    assert np.allclose(out[0], [50, 50], atol=1e-6)


def test_known_translation():
    src = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
    dst = src + np.array([100.0, 50.0])
    H = compute_homography(src, dst)
    out = transform_points(H, np.array([[5, 5]]))
    assert np.allclose(out[0], [105, 55], atol=1e-6)


def test_known_scale():
    src = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
    dst = src * 3.0
    H = compute_homography(src, dst)
    out = transform_points(H, np.array([[4, 6]]))
    assert np.allclose(out[0], [12, 18], atol=1e-6)


def test_board_corners_map_correctly():
    # Camera quad -> board corners (0,0),(W,0),(W,H),(0,H)
    cam = np.array([[100, 50], [600, 80], [620, 450], [80, 420]], dtype=float)
    W, Hh = 1280, 720
    dst = np.array([[0, 0], [W, 0], [W, Hh], [0, Hh]], dtype=float)
    H = compute_homography(cam, dst)
    # The clicked corners must map exactly onto the board corners.
    out = transform_points(H, cam)
    assert np.allclose(out, dst, atol=1e-6)
    # Centre of the camera quad should map near the board centre.
    centre = transform_points(H, np.array([[cam[:, 0].mean(),
                                            cam[:, 1].mean()]]))
    assert abs(centre[0, 0] - W / 2) < W * 0.2
    assert abs(centre[0, 1] - Hh / 2) < Hh * 0.2


def test_degenerate_collinear_points_raise():
    src = np.array([[0, 0], [10, 0], [20, 0], [30, 0]], dtype=float)  # collinear
    dst = src.copy()
    with pytest.raises(ValueError):
        compute_homography(src, dst)


def test_duplicate_points_raise():
    src = np.array([[0, 0], [0, 0], [10, 10], [20, 0]], dtype=float)
    with pytest.raises(ValueError):
        compute_homography(src, src.copy())


def test_is_valid_quad():
    good = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=float)
    assert is_valid_quad(good)
    tiny = np.array([[0, 0], [5, 0], [5, 5], [0, 5]], dtype=float)
    assert not is_valid_quad(tiny, min_area=1000)
    collinear = np.array([[0, 0], [50, 0], [100, 0], [0, 100]], dtype=float)
    assert not is_valid_quad(collinear)


def test_point_in_rect():
    assert point_in_rect((5, 5), (0, 0, 10, 10))
    assert not point_in_rect((15, 5), (0, 0, 10, 10))
