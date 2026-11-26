"""Pointer detection tests on synthetic images (no webcam needed)."""
import cv2
import numpy as np
import pytest

from core.detector import (Component, DetectionParams, bgr_to_hsv, closing, component_confidence,
                           connected_components, detect, dilate, erode, hsv_range_from_sample,
                           median_hsv_at, opening, threshold_hsv)
from tests.synthetic import BLUE, GREEN, RED, blob_frame

P = DetectionParams()


# ------------------------------------------------------------------ BGR -> HSV
def test_bgr_to_hsv_matches_opencv_on_random_image():
    rng = np.random.default_rng(1)
    img = rng.integers(0, 256, (60, 80, 3), dtype=np.uint8)
    mine, ref = bgr_to_hsv(img).astype(int), cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(int)
    hue_diff = np.minimum(np.abs(mine[..., 0] - ref[..., 0]), 180 - np.abs(mine[..., 0] - ref[..., 0]))
    assert hue_diff.max() <= 1
    assert np.abs(mine[..., 1:] - ref[..., 1:]).max() <= 1


@pytest.mark.parametrize("bgr,hsv", [((0, 0, 255), (0, 255, 255)), ((0, 255, 0), (60, 255, 255)),
                                     ((255, 0, 0), (120, 255, 255)), ((0, 0, 0), (0, 0, 0)),
                                     ((255, 255, 255), (0, 0, 255)), ((128, 128, 128), (0, 0, 128))])
def test_bgr_to_hsv_primary_colours(bgr, hsv):
    assert tuple(bgr_to_hsv(np.array([[bgr]], np.uint8))[0, 0]) == hsv


# ------------------------------------------------------------------ thresholding
def test_threshold_selects_only_marker_colour():
    img = blob_frame(blobs=[(100, 90, 20)], color=GREEN)
    mask = threshold_hsv(bgr_to_hsv(img), P.hsv_low, P.hsv_high)
    assert mask[90, 100] and not mask[10, 10]
    assert abs(int(mask.sum()) - np.pi * 20 ** 2) < 60


def test_threshold_wrapped_hue_for_red():
    img = blob_frame(blobs=[(100, 90, 20)], color=RED)
    hsv = bgr_to_hsv(img)
    assert not threshold_hsv(hsv, (35, 90, 70), (85, 255, 255)).any()          # green range: nothing
    wrapped = threshold_hsv(hsv, (170, 120, 70), (10, 255, 255))               # low > high = wrap
    assert wrapped[90, 100] and not wrapped[10, 10]


def test_hsv_range_from_sample_contains_sample_and_excludes_other_hues():
    low, high = hsv_range_from_sample((60, 200, 200), 50)
    assert (low, high) == ((35, 90, 70), (85, 255, 255))                       # the defaults
    for sample in ((60, 200, 200), (2, 220, 230), (120, 180, 200)):
        low, high = hsv_range_from_sample(sample, 50)
        px = np.array([[sample]], np.uint8)
        assert threshold_hsv(px, low, high)[0, 0]
    low, high = hsv_range_from_sample((60, 200, 200), 20)
    assert not threshold_hsv(np.array([[(120, 200, 200)]], np.uint8), low, high)[0, 0]
    narrow = hsv_range_from_sample((60, 200, 200), 0)
    wide = hsv_range_from_sample((60, 200, 200), 100)
    assert narrow[1][0] - narrow[0][0] < wide[1][0] - wide[0][0]


def test_median_hsv_at_handles_red_hue_wrap():
    img = np.full((20, 20, 3), RED, np.uint8)
    h, s, v = median_hsv_at(img, 10, 10)
    assert min(h, 180 - h) <= 4 and s > 150


# ------------------------------------------------------------------ morphology / noise
def test_erode_dilate_match_opencv_in_the_interior():
    rng = np.random.default_rng(3)
    mask = rng.random((40, 50)) > 0.5
    kernel = np.ones((5, 5), np.uint8)
    ref_e = cv2.erode(mask.astype(np.uint8), kernel).astype(bool)
    ref_d = cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)
    assert np.array_equal(erode(mask, 5)[3:-3, 3:-3], ref_e[3:-3, 3:-3])
    assert np.array_equal(dilate(mask, 5)[3:-3, 3:-3], ref_d[3:-3, 3:-3])


def test_opening_removes_specks_and_keeps_the_blob():
    mask = np.zeros((90, 120), bool)
    mask[30:60, 40:80] = True                                    # real blob 30 x 40
    rng = np.random.default_rng(5)
    ys, xs = rng.integers(0, 90, 40), rng.integers(0, 120, 40)
    noise = np.zeros_like(mask)
    noise[ys, xs] = True                                         # single-pixel salt noise
    noise[30:60, 40:80] = False
    cleaned = opening(mask | noise, 5)
    assert not cleaned[noise].any()
    assert cleaned[30:60, 40:80].sum() >= 0.97 * 30 * 40


def test_closing_fills_small_holes():
    mask = np.zeros((60, 60), bool)
    mask[10:50, 10:50] = True
    mask[28:31, 28:31] = False                                   # 3 x 3 hole
    assert not closing(mask, 5)[29, 29] == False                 # noqa: E712 (hole is filled)


# ------------------------------------------------------------------ components / centroid
def test_connected_components_matches_opencv():
    rng = np.random.default_rng(11)
    mask = np.zeros((80, 100), np.uint8)
    for _ in range(6):
        cv2.circle(mask, (int(rng.integers(10, 90)), int(rng.integers(10, 70))), int(rng.integers(3, 9)), 1, -1)
    mask[5:9, 50:75] = 1
    mine = sorted(connected_components(mask.astype(bool)), key=lambda c: (round(c.cy), round(c.cx)))
    n, _, stats, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
    ref = sorted(((stats[i, cv2.CC_STAT_AREA], *cents[i]) for i in range(1, n)), key=lambda r: (round(r[2]), round(r[1])))
    assert len(mine) == len(ref)
    for c, (area, cx, cy) in zip(mine, ref):
        assert c.area == area and c.cx == pytest.approx(cx, abs=1e-6) and c.cy == pytest.approx(cy, abs=1e-6)


def test_eight_connectivity_joins_diagonal_pixels():
    mask = np.zeros((5, 5), bool)
    mask[1, 1] = mask[2, 2] = mask[3, 3] = True
    comps = connected_components(mask)
    assert len(comps) == 1 and comps[0].area == 3


def test_centroid_and_bbox_of_known_rectangle():
    mask = np.zeros((50, 60), bool)
    mask[10:20, 30:50] = True                                    # rows 10-19, cols 30-49
    (c,) = connected_components(mask)
    assert (c.cx, c.cy) == (39.5, 14.5)
    assert (c.x0, c.y0, c.x1, c.y1) == (30, 10, 50, 20)
    assert c.area == 200
    assert c.mu20 == pytest.approx((20 ** 2 - 1) / 12) and c.mu02 == pytest.approx((10 ** 2 - 1) / 12)


def test_u_shaped_blob_is_one_component():
    mask = np.zeros((30, 30), bool)
    mask[5:25, 5:8] = mask[5:25, 20:23] = mask[22:25, 5:23] = True
    assert len(connected_components(mask)) == 1


def test_noise_mask_is_rejected_not_hung():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        connected_components(rng.random((300, 400)) > 0.5)


# ------------------------------------------------------------------ complete detector
def test_detect_finds_marker_with_subpixel_accuracy():
    img = np.full((360, 640, 3), 60, np.uint8)
    cv2.circle(img, (321, 187), 12, GREEN, -1, cv2.LINE_AA)
    res = detect(img, P)
    assert res.status == "ok" and res.detection is not None
    assert res.detection.x == pytest.approx(321, abs=1.2) and res.detection.y == pytest.approx(187, abs=1.2)
    assert res.detection.area == pytest.approx(np.pi * 144, rel=0.25)
    x0, y0, x1, y1 = res.detection.bbox
    assert x0 < 321 < x1 and y0 < 187 < y1


def test_detect_works_at_full_hd_and_reports_full_resolution_coordinates():
    img = np.full((1080, 1920, 3), 60, np.uint8)
    cv2.circle(img, (1500, 400), 40, GREEN, -1)
    det = detect(img, P).detection
    assert det is not None and det.x == pytest.approx(1500, abs=3) and det.y == pytest.approx(400, abs=3)


def test_detect_no_marker():
    res = detect(blob_frame(blobs=[]), P)
    assert res.detection is None and res.status == "no_pixels"


def test_tiny_blob_rejected_as_too_small():
    res = detect(blob_frame(320, 180, [(100, 90, 3)]), DetectionParams(min_area=150, kernel_size=1))
    assert res.detection is None and res.status == "area_too_small"


def test_huge_blob_rejected_as_too_large():
    res = detect(blob_frame(320, 180, [(160, 90, 80)]), DetectionParams(max_area=5000))
    assert res.detection is None and res.status == "area_too_large"


def test_thin_line_rejected_by_shape_confidence():
    img = np.full((180, 320, 3), 40, np.uint8)
    cv2.line(img, (30, 20), (250, 160), GREEN, 9)                # long diagonal stick, area is fine
    res = detect(img, DetectionParams(min_area=100))
    assert res.detection is None and res.status == "low_confidence"
    assert component_confidence(Component(100, 5, 5, 0, 0, 100, 1, 0, 0, 0)) < 0.1


def test_largest_valid_blob_is_chosen():
    res = detect(blob_frame(320, 180, [(60, 60, 8), (200, 100, 18)]), P)
    assert res.candidates == 2
    assert res.detection.x == pytest.approx(200, abs=1.5)


def test_other_colours_are_ignored():
    res = detect(blob_frame(320, 180, [(60, 60, 15)], color=BLUE), P)
    assert res.detection is None


def test_red_marker_detected_with_wrapped_range():
    params = DetectionParams(hsv_low=(170, 120, 70), hsv_high=(10, 255, 255))
    res = detect(blob_frame(320, 180, [(90, 70, 14)], color=RED), params)
    assert res.detection is not None and res.detection.x == pytest.approx(90, abs=1.5)


def test_detection_with_sensor_noise():
    rng = np.random.default_rng(9)
    img = blob_frame(640, 360, [(300, 200, 14)], bg=(90, 100, 110)).astype(np.int16)
    img = np.clip(img + rng.integers(-18, 19, img.shape), 0, 255).astype(np.uint8)
    res = detect(img, P)
    assert res.detection is not None and res.detection.x == pytest.approx(300, abs=2)


def test_params_sanitized_and_roundtrip(tmp_path):
    from core.settings import Settings
    p = DetectionParams(hsv_low=(-5, 300, 70), hsv_high=(200, 255, 255), min_area=0, max_area=-3,
                        kernel_size=4, confidence_min=7).sanitized()
    assert p.hsv_low == (0, 255, 70) and p.hsv_high[0] == 179
    assert p.min_area >= 1 and p.max_area >= p.min_area and p.kernel_size % 2 == 1 and p.confidence_min == 1.0
    s = Settings(tmp_path / "s.json")
    DetectionParams(hsv_low=(100, 50, 60), min_area=222).write_to(s)
    assert DetectionParams.from_settings(s).min_area == 222
    s.set("detection.hsv_low", "garbage")
    assert DetectionParams.from_settings(s) == DetectionParams()                 # bad settings -> defaults
