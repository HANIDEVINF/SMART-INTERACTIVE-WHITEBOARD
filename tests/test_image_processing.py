"""Tests for the manual NumPy image-processing primitives."""

import numpy as np
import pytest

from utils.image_processing import (bgr_to_gray, bgr_to_hsv, binary_dilation,
                                    binary_erosion, component_stats,
                                    get_pixel, in_hsv_range, morphological_open,
                                    rasterize_line, set_pixel, threshold_gray)


# ---------------------------------------------------------------------------
# Pixel access
# ---------------------------------------------------------------------------

def test_get_set_pixel():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    set_pixel(img, 3, 4, (10, 20, 30))
    assert tuple(get_pixel(img, 3, 4)) == (10, 20, 30)
    with pytest.raises(IndexError):
        get_pixel(img, 99, 0)


# ---------------------------------------------------------------------------
# Colour conversion
# ---------------------------------------------------------------------------

def test_bgr_to_gray_white_black():
    img = np.array([[[255, 255, 255], [0, 0, 0]]], dtype=np.uint8)  # BGR
    gray = bgr_to_gray(img)
    assert gray[0, 0] == 255
    assert gray[0, 1] == 0


def test_bgr_to_gray_red():
    # Pure red in BGR is (0, 0, 255); luma = 0.299*255 ≈ 76
    img = np.array([[[0, 0, 255]]], dtype=np.uint8)
    gray = bgr_to_gray(img)
    assert abs(int(gray[0, 0]) - 76) <= 1


def test_bgr_to_hsv_pure_green():
    # Pure green BGR (0, 255, 0) -> HSV hue ≈ 120 deg, S = 1, V = 1
    img = np.array([[[0, 255, 0]]], dtype=np.uint8)
    hsv = bgr_to_hsv(img)
    h, s, v = hsv[0, 0]
    assert abs(h - 120.0) < 1.0
    assert abs(s - 1.0) < 1e-3
    assert abs(v - 1.0) < 1e-3


def test_bgr_to_hsv_black_is_achromatic():
    img = np.zeros((2, 2, 3), dtype=np.uint8)
    hsv = bgr_to_hsv(img)
    assert hsv[..., 1].max() == 0.0  # saturation 0
    assert hsv[..., 2].max() == 0.0  # value 0


# ---------------------------------------------------------------------------
# Thresholding
# ---------------------------------------------------------------------------

def test_threshold_gray():
    gray = np.array([[0, 100, 200]], dtype=np.uint8)
    mask = threshold_gray(gray, 100)
    assert mask.tolist() == [[False, True, True]]


def test_in_hsv_range_wraparound():
    # Hue 5 deg should match range [350, 10] (wraps through 0).
    hsv = np.array([[[5.0, 0.8, 0.9], [200.0, 0.8, 0.9]]], dtype=np.float32)
    mask = in_hsv_range(hsv, 350.0, 10.0, 0.0, 1.0, 0.0, 1.0)
    assert mask[0, 0] and not mask[0, 1]


# ---------------------------------------------------------------------------
# Morphology
# ---------------------------------------------------------------------------

def test_dilation_grows_region():
    mask = np.zeros((7, 7), dtype=bool)
    mask[3, 3] = True
    out = binary_dilation(mask, kernel_size=3)
    assert out.sum() == 9  # 3x3 block
    assert out[3, 3]


def test_erosion_shrinks_region():
    mask = np.ones((7, 7), dtype=bool)
    mask[0, :] = False  # break the border so erosion has room
    mask[:, 0] = False
    out = binary_erosion(mask, kernel_size=3)
    assert not out[0, 0]
    assert out[3, 3]


def test_opening_removes_speckle():
    mask = np.zeros((15, 15), dtype=bool)
    mask[7, 7] = True          # single-pixel noise
    mask[3:6, 3:6] = True      # 3x3 blob
    out = morphological_open(mask, kernel_size=3)
    assert out[4, 4]
    assert not out[7, 7]       # speckle removed


# ---------------------------------------------------------------------------
# Component statistics
# ---------------------------------------------------------------------------

def test_component_stats_centroid_and_bbox():
    labels = np.zeros((10, 10), dtype=np.int32)
    labels[2:4, 3:5] = 1  # 2x2 block at rows 2-3, cols 3-4
    stats = component_stats(labels, 2)
    s = stats[1]
    assert s["area"] == 4
    assert s["centroid"] == pytest.approx((3.5, 2.5))
    assert s["bbox"] == (3, 2, 4, 3)


# ---------------------------------------------------------------------------
# Line rasterisation
# ---------------------------------------------------------------------------

def test_rasterize_line_draws_pixels():
    layer = np.zeros((50, 50, 4), dtype=np.uint8)
    rasterize_line(layer, (5, 5), (45, 5), (255, 0, 0, 255), thickness=3)
    # Pixels along the horizontal line must be drawn.
    assert layer[5, 10, 3] > 0
    assert layer[5, 40, 3] > 0
    # Far away pixels must stay empty.
    assert layer[40, 40, 3] == 0


def test_rasterize_line_diagonal():
    layer = np.zeros((60, 60, 4), dtype=np.uint8)
    rasterize_line(layer, (5, 5), (55, 55), (0, 255, 0, 255), thickness=2)
    assert layer[30, 30, 3] > 0
    assert layer[5, 5, 3] > 0
    assert layer[55, 55, 3] > 0
