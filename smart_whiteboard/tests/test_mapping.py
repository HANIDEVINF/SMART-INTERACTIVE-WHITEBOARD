"""Camera -> board -> canvas coordinate mapping."""
import numpy as np
import pytest

from core.calibration import Calibration
from core.coordinate_mapping import (CoordinateMapper, board_to_canvas, canvas_to_board,
                                     fit_board_in_canvas)
from tests.synthetic import BOARD_H, BOARD_W, CAM_H, CAM_QUAD, CAM_W, board_to_cam_matrix, project

BOARD = (BOARD_W, BOARD_H)


@pytest.fixture
def mapper():
    return CoordinateMapper(Calibration.from_corners(CAM_QUAD, (CAM_W, CAM_H), BOARD), edge_margin=12)


def test_corners_and_centre_map_to_board_corners_and_centre(mapper):
    for (cx, cy), (bx, by) in zip(CAM_QUAD, [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]):
        p = mapper.camera_to_board(cx, cy)
        assert p.x == pytest.approx(bx, abs=1e-6) and p.y == pytest.approx(by, abs=1e-6)
    H = board_to_cam_matrix()
    p = mapper.camera_to_board(*project(H, BOARD_W / 2, BOARD_H / 2))
    assert (p.x, p.y) == pytest.approx((BOARD_W / 2, BOARD_H / 2), abs=1e-6)


def test_perspective_is_corrected_for_arbitrary_points(mapper):
    H = board_to_cam_matrix()
    rng = np.random.default_rng(8)
    for bx, by in rng.uniform([50, 50], [BOARD_W - 50, BOARD_H - 50], (200, 2)):
        p = mapper.camera_to_board(*project(H, bx, by))
        assert (p.x, p.y) == pytest.approx((bx, by), abs=1e-4)


def test_equal_camera_steps_are_not_equal_board_steps(mapper):
    """Sanity check that this is a *perspective* map: the far (shorter) edge maps to the same board width."""
    top = np.linalg.norm(np.subtract(CAM_QUAD[1], CAM_QUAD[0]))
    bottom = np.linalg.norm(np.subtract(CAM_QUAD[2], CAM_QUAD[3]))
    assert bottom > top * 1.1                       # trapezium in the camera image ...
    a, b = mapper.camera_to_board(*CAM_QUAD[0]), mapper.camera_to_board(*CAM_QUAD[1])
    c, d = mapper.camera_to_board(*CAM_QUAD[3]), mapper.camera_to_board(*CAM_QUAD[2])
    assert b.x - a.x == pytest.approx(d.x - c.x)    # ... but a rectangle on the board


@pytest.mark.parametrize("pt", [(5, 5), (CAM_W - 3, CAM_H - 3), (300, 10), (-50, 100)])
def test_points_outside_the_board_are_rejected(mapper, pt):
    assert mapper.camera_to_board(*pt) is None


def test_points_in_the_edge_margin_are_clamped(mapper):
    H = board_to_cam_matrix()
    p = mapper.camera_to_board(*project(H, -6, 450))                 # 6 board px outside, margin is 12
    assert p is not None and p.clamped and p.x == 0.0
    assert mapper.camera_to_board(*project(H, -40, 450)) is None


@pytest.mark.parametrize("pt", [(float("nan"), 1.0), (1.0, float("inf"))])
def test_invalid_input_returns_none(mapper, pt):
    assert mapper.camera_to_board(*pt) is None


def test_different_camera_resolution_same_aspect_gives_same_board_point(mapper):
    H = board_to_cam_matrix()
    x, y = project(H, 800, 300)
    full = mapper.camera_to_board(x, y)
    half = mapper.camera_to_board(x / 2, y / 2, frame_size=(CAM_W // 2, CAM_H // 2))
    double = mapper.camera_to_board(x * 2, y * 2, frame_size=(CAM_W * 2, CAM_H * 2))
    assert (half.x, half.y) == pytest.approx((full.x, full.y), abs=1e-6)
    assert (double.x, double.y) == pytest.approx((full.x, full.y), abs=1e-6)


def test_board_to_camera_is_the_inverse(mapper):
    x, y = mapper.board_to_camera(800, 450)
    p = mapper.camera_to_board(x, y)
    assert (p.x, p.y) == pytest.approx((800, 450), abs=1e-6)


# ------------------------------------------------------------------ board <-> canvas
@pytest.mark.parametrize("canvas", [(1000, 700), (700, 1000), (1600, 900), (320, 240), (2560, 1440)])
def test_fit_preserves_aspect_ratio_and_centres(canvas):
    x, y, w, h = fit_board_in_canvas(BOARD, canvas, margin=10)
    assert w / h == pytest.approx(BOARD_W / BOARD_H)
    assert x == pytest.approx(canvas[0] - x - w) and y == pytest.approx(canvas[1] - y - h)
    assert x >= 0 and y >= 0 and x + w <= canvas[0] + 1e-9 and y + h <= canvas[1] + 1e-9


def test_board_canvas_roundtrip_for_any_window_size():
    rng = np.random.default_rng(6)
    for cw, ch in [(800, 500), (1234, 777), (400, 900)]:
        rect = fit_board_in_canvas(BOARD, (cw, ch), 10)
        for bx, by in rng.uniform([0, 0], BOARD, (50, 2)):
            px, py = board_to_canvas(bx, by, BOARD, rect)
            assert canvas_to_board(px, py, BOARD, rect) == pytest.approx((bx, by))


def test_pointer_stays_on_the_same_board_spot_when_the_window_is_resized():
    """The pointer lives in board coordinates; resizing only changes the last (board -> canvas) step."""
    for size in [(900, 600), (1500, 800)]:
        rect = fit_board_in_canvas(BOARD, size, 10)
        px, py = board_to_canvas(BOARD_W / 2, BOARD_H / 2, BOARD, rect)
        assert (px, py) == pytest.approx((size[0] / 2, size[1] / 2))                  # board centre = canvas centre
        assert board_to_canvas(0, 0, BOARD, rect) == pytest.approx(rect[:2])
        assert board_to_canvas(BOARD_W, BOARD_H, BOARD, rect) == pytest.approx((rect[0] + rect[2], rect[1] + rect[3]))
