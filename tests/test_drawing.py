"""Unit tests for the NumPy drawing engine (no GUI, no camera needed)."""
import numpy as np
import pytest

from tools.drawing import DrawingEngine, Tool
from tools.image_tools import fit_rect, imread_unicode, imwrite_unicode
from tools.primitives import segment_coverage

RED = (0, 0, 255)  # BGR
BLUE = (255, 0, 0)


@pytest.fixture
def eng():
    return DrawingEngine(200, 100, paper_rgb=(255, 255, 255))


def ink_alpha_sum(e):
    return int(e.ink[..., 3].astype(np.int64).sum())


def test_blank_board_is_paper_colour(eng):
    assert eng.composite.shape == (100, 200, 3)
    assert (eng.composite == 255).all()
    assert not eng.has_ink


def test_segment_coverage_is_one_on_axis_and_zero_far_away():
    (x0, y0, x1, y1), cov = segment_coverage((100, 200, 4), (20, 50), (120, 50), 6)
    assert cov[50 - y0, 70 - x0] == pytest.approx(1.0)
    assert cov[50 - y0, 70 - x0] > cov[53 - y0, 70 - x0] >= 0.0   # fades with distance
    assert cov[0, 0] == 0.0


def test_pen_stroke_draws_colour_and_is_antialiased(eng):
    eng.begin_stroke(Tool.PEN, RED, 6, (20, 50))
    eng.stroke_to((120, 50))
    eng.end_stroke()
    assert eng.has_ink
    assert tuple(eng.composite[50, 70]) == RED          # centre of the stroke is solid red
    assert tuple(eng.composite[10, 70]) == (255, 255, 255)
    edge = eng.composite[53, 70]
    assert 0 < edge[1] < 255                             # soft edge pixel: neither paper nor red


def test_undo_redo_roundtrip(eng):
    eng.draw_line((10, 10), (150, 80), RED, 4)
    after = eng.ink.copy()
    assert eng.can_undo and not eng.can_redo
    eng.undo()
    assert not eng.has_ink and eng.can_redo
    eng.redo()
    assert np.array_equal(eng.ink, after)


def test_new_action_clears_redo_stack(eng):
    eng.draw_line((10, 10), (50, 10), RED, 4)
    eng.undo()
    assert eng.can_redo
    eng.draw_line((10, 30), (50, 30), BLUE, 4)
    assert not eng.can_redo


def test_history_stores_only_changed_region(eng):
    eng.draw_line((10, 10), (30, 10), RED, 4)
    entry = eng._undo[-1]
    x0, y0, x1, y1 = entry.bbox
    assert (x1 - x0) * (y1 - y0) < 200 * 100 / 4
    assert entry.before.shape[:2] == (y1 - y0, x1 - x0)


def test_history_limit():
    e = DrawingEngine(100, 100, max_history=5)
    for i in range(10):
        e.draw_line((5, 5 + i * 8), (90, 5 + i * 8), RED, 2)
    assert e.history_size == 5


def test_eraser_removes_ink_and_is_undoable(eng):
    eng.draw_line((10, 50), (190, 50), RED, 10)
    before = ink_alpha_sum(eng)
    eng.begin_stroke(Tool.ERASER, (0, 0, 0), 20, (100, 50))
    eng.stroke_to((150, 50))
    eng.end_stroke()
    assert ink_alpha_sum(eng) < before
    assert tuple(eng.composite[50, 120]) == (255, 255, 255)
    eng.undo()
    assert ink_alpha_sum(eng) == before


def test_clear_is_undoable_and_keeps_background(eng):
    bg = np.full((50, 100, 3), (10, 200, 10), np.uint8)
    eng.set_background(bg)
    eng.draw_line((10, 10), (150, 80), RED, 4)
    eng.clear_ink()
    assert not eng.has_ink and eng.has_background
    eng.undo()
    assert eng.has_ink


def test_rectangle_and_circle_outlines(eng):
    eng.draw_rect((20, 20), (120, 80), RED, 4)
    assert tuple(eng.composite[20, 70]) == RED          # top edge
    assert tuple(eng.composite[50, 70]) == (255, 255, 255)  # interior stays empty
    eng.draw_circle((100, 50), 30, BLUE, 4)
    assert tuple(eng.composite[50, 130]) == BLUE        # on the circle
    assert tuple(eng.composite[50, 100]) == (255, 255, 255)


def test_drawing_outside_canvas_does_not_crash(eng):
    eng.draw_line((-500, -500), (-300, -300), RED, 4)
    eng.draw_circle((1000, 1000), 20, RED, 4)
    eng.begin_stroke(Tool.PEN, RED, 5, (-10, 50))
    eng.stroke_to((250, 50))
    eng.end_stroke()
    assert eng.has_ink  # the visible part of the stroke was drawn


def test_text_draws_pixels(eng):
    eng.draw_text((10, 10), "Hello", RED, 24)
    assert eng.has_ink
    assert eng.can_undo


def test_empty_text_is_ignored(eng):
    assert eng.draw_text((10, 10), "   ", RED, 24) is None
    assert not eng.can_undo


def test_cancel_action_restores_ink(eng):
    eng.begin_stroke(Tool.PEN, RED, 6, (10, 10))
    eng.stroke_to((100, 60))
    eng.cancel_action()
    eng.take_dirty()
    assert not eng.has_ink


def test_reset_clears_everything(eng):
    eng.set_background(np.zeros((10, 10, 3), np.uint8))
    eng.draw_line((10, 10), (50, 50), RED, 4)
    eng.reset()
    assert not eng.has_ink and not eng.has_background and eng.history_size == 0
    assert (eng.composite == 255).all()


def test_fit_rect_preserves_aspect_ratio():
    x, y, w, h = fit_rect(400, 100, 200, 100)     # wide image into a 2:1 box
    assert (w, h) == (200, 50) and (x, y) == (0, 25)
    x, y, w, h = fit_rect(100, 400, 200, 100)     # tall image
    assert (w, h) == (25, 100) and (x, y) == (87, 0)
    with pytest.raises(ValueError):
        fit_rect(0, 10, 10, 10)


def test_background_is_letterboxed(eng):
    img = np.full((100, 400, 3), (0, 255, 0), np.uint8)   # 4:1 image on a 2:1 board
    x, y, w, h = eng.set_background(img)
    assert (w, h) == (200, 50) and y == 25
    assert tuple(eng.composite[50, 100]) == (0, 255, 0)
    assert tuple(eng.composite[5, 100]) == (255, 255, 255)   # padding


def test_unicode_path_roundtrip(tmp_path):
    path = tmp_path / "dessin_éàç_ملف.png"
    img = np.random.default_rng(0).integers(0, 255, (20, 30, 3), dtype=np.uint8)
    imwrite_unicode(path, img)
    assert np.array_equal(imread_unicode(path), img)


def test_invalid_image_returns_none(tmp_path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"this is not an image")
    assert imread_unicode(bad) is None
    assert imread_unicode(tmp_path / "missing.png") is None
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    assert imread_unicode(empty) is None
