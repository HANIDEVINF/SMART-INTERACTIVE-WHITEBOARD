"""Tests for marker detection on synthetic frames."""

import cv2
import numpy as np

from detection.color_detector import ColorDetector

GREEN = {"h_min": 90.0, "h_max": 150.0, "s_min": 0.35, "s_max": 1.0,
         "v_min": 0.35, "v_max": 1.0}


def make_frame(shape=(480, 640, 3), blobs=()):
    """Dark frame with optional (center, radius, bgr) blobs."""
    frame = np.full(shape, (30, 30, 45), dtype=np.uint8)
    for (cx, cy), r, color in blobs:
        cv2.circle(frame, (cx, cy), r, color, -1)
    return frame


def test_detect_single_green_marker():
    frame = make_frame(blobs=[((320, 240), 25, (0, 255, 0))])
    det = ColorDetector(GREEN, min_area=200).detect(frame)
    assert det is not None
    assert abs(det.x - 320) < 5
    assert abs(det.y - 240) < 5
    assert det.area > 500


def test_detect_returns_none_without_marker():
    frame = make_frame()  # empty dark frame
    det = ColorDetector(GREEN, min_area=200).detect(frame)
    assert det is None


def test_detect_rejects_small_noise():
    frame = make_frame(blobs=[((100, 100), 3, (0, 255, 0))])  # tiny blob
    det = ColorDetector(GREEN, min_area=500).detect(frame)
    assert det is None


def test_detect_ignores_wrong_colour():
    frame = make_frame(blobs=[((320, 240), 25, (0, 0, 255))])  # red blob
    det = ColorDetector(GREEN, min_area=200).detect(frame)
    assert det is None


def test_detect_picks_largest_blob():
    frame = make_frame(blobs=[
        ((100, 100), 15, (0, 255, 0)),
        ((400, 300), 30, (0, 255, 0)),
    ])
    det = ColorDetector(GREEN, min_area=200).detect(frame)
    assert det is not None
    assert abs(det.x - 400) < 5
    assert abs(det.y - 300) < 5


def test_detect_handles_none_frame():
    det = ColorDetector(GREEN).detect(None)
    assert det is None
