"""Tests for the drawing canvas: strokes, undo/redo, clear, export."""

import numpy as np
import pygame
import pytest

from interface.drawing import DrawingCanvas, _hex_to_rgba

RED = _hex_to_rgba("#e53935")
BLUE = _hex_to_rgba("#1e88e5")


@pytest.fixture
def canvas():
    return DrawingCanvas(200, 200, history_limit=10)


def test_stroke_draws_on_layer(canvas):
    canvas.begin_stroke((10, 10), RED, 4)
    canvas.extend_stroke((100, 10))
    canvas.end_stroke()
    assert canvas.layer[10, 50, 3] > 0
    # Nothing drawn far away.
    assert canvas.layer[150, 150, 3] == 0


def test_stroke_breaks_on_end(canvas):
    canvas.begin_stroke((10, 10), RED, 4)
    canvas.extend_stroke((50, 10))
    canvas.end_stroke()
    canvas.begin_stroke((150, 150), RED, 4)
    canvas.extend_stroke((190, 190))
    canvas.end_stroke()
    # The two strokes must not be connected.
    assert canvas.layer[80, 80, 3] == 0


def test_undo_redo(canvas):
    canvas.begin_stroke((10, 10), RED, 4)
    canvas.extend_stroke((100, 10))
    canvas.end_stroke()
    assert canvas.layer[10, 50, 3] > 0

    assert canvas.undo() is True
    assert canvas.layer[10, 50, 3] == 0  # layer rebuilt without the stroke

    assert canvas.redo() is True
    assert canvas.layer[10, 50, 3] > 0


def test_undo_empty_returns_false(canvas):
    assert canvas.undo() is False
    assert canvas.redo() is False


def test_clear(canvas):
    canvas.begin_stroke((10, 10), RED, 4)
    canvas.extend_stroke((100, 100))
    canvas.end_stroke()
    canvas.clear()
    assert canvas.layer[..., 3].max() == 0
    assert canvas.strokes == []


def test_history_limit(canvas):
    for i in range(15):
        canvas.begin_stroke((10 + i, 10), RED, 2)
        canvas.extend_stroke((50 + i, 50))
        canvas.end_stroke()
    assert len(canvas.strokes) <= canvas.history_limit


def test_export_png(canvas, tmp_path):
    canvas.begin_stroke((10, 10), RED, 6)
    canvas.extend_stroke((150, 150))
    canvas.end_stroke()
    out = tmp_path / "annotations.png"
    assert canvas.export(out) is True
    assert out.exists() and out.stat().st_size > 0
    # The saved file must be a valid PNG loadable by pygame.
    surf = pygame.image.load(str(out))
    assert surf.get_size() == (200, 200)


def test_two_colors(canvas):
    canvas.begin_stroke((10, 10), RED, 4)
    canvas.extend_stroke((100, 10))
    canvas.end_stroke()
    canvas.begin_stroke((10, 50), BLUE, 4)
    canvas.extend_stroke((100, 50))
    canvas.end_stroke()
    # Red stroke: R channel high, B low. Blue stroke: opposite.
    assert canvas.layer[10, 50, 0] > 200   # red channel of red stroke
    assert canvas.layer[50, 50, 2] > 200   # blue channel of blue stroke
