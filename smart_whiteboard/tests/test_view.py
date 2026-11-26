import pytest

from core.view_transform import MAX_ZOOM, ViewTransform


def test_identity_and_round_trip():
    v = ViewTransform(1600, 900)
    assert v.is_identity and v.to_content(300, 200) == (300, 200)
    v.set_zoom_at(3, 400, 300)
    for p in [(0, 0), (800, 450), (1599, 899)]:
        assert v.to_screen(*v.to_content(*p)) == pytest.approx(p)


def test_zoom_keeps_the_anchor_fixed():
    v = ViewTransform(1600, 900)
    v.set_zoom_at(2, 1000, 500)
    assert v.to_content(1000, 500) == pytest.approx((1000, 500))      # content under the anchor did not move
    before = v.to_content(1200, 300)
    v.zoom_in(1200, 300)
    assert v.to_content(1200, 300) == pytest.approx(before)


def test_limits_and_no_empty_margins():
    v = ViewTransform(1600, 900)
    v.zoom_out()
    assert v.zoom == 1.0 and v.is_identity
    for _ in range(40):
        v.zoom_in(1590, 890)
    assert v.zoom == MAX_ZOOM
    x, y, w, h = v.visible_rect()
    assert 0 <= x and x + w <= 1600 + 1e-6 and 0 <= y and y + h <= 900 + 1e-6
    v.pan_by(100_000, 100_000)
    assert v.visible_rect()[0] == pytest.approx(0) and v.visible_rect()[1] == pytest.approx(0)
    v.pan_by(-100_000, -100_000)
    x, y, w, h = v.visible_rect()
    assert x + w == pytest.approx(1600) and y + h == pytest.approx(900)


def test_pan_moves_content_with_the_drag_and_view_window_with_move_view():
    v = ViewTransform(1600, 900)
    v.set_zoom_at(2)
    c0 = v.to_content(800, 450)
    v.pan_by(-100, 0)                       # drag content left -> we now see content further right
    assert v.to_content(800, 450)[0] == pytest.approx(c0[0] + 50)
    v.reset()
    v.set_zoom_at(2)
    v.move_view(-0.25, 0)                   # look left by a quarter of the board
    assert v.to_content(800, 450)[0] < c0[0]


def test_reset_at_unit_zoom_cannot_pan():
    v = ViewTransform(1600, 900)
    v.pan_by(50, 50)
    assert v.is_identity
