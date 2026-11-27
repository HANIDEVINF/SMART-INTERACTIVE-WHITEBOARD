"""GUI integration tests (run headless with QT_QPA_PLATFORM=offscreen)."""
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.app_state import AppState
from core.settings import Settings
from tools.image_tools import imwrite_unicode
from ui.main_window import MainWindow
from ui.styles import STYLESHEET


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app


@pytest.fixture
def win(qapp, tmp_path):
    settings = Settings(tmp_path / "settings.json")
    window = MainWindow(settings, AppState())
    window.show()
    qapp.processEvents()
    yield window
    window.close()


def canvas_point(win, bx, by):
    return win.whiteboard.canvas.board_to_widget(bx, by).toPoint()


def drag(win, p0, p1):
    c = win.whiteboard.canvas
    QTest.mousePress(c, Qt.MouseButton.LeftButton, pos=canvas_point(win, *p0))
    QTest.mouseMove(c, canvas_point(win, (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2))
    QTest.mouseMove(c, canvas_point(win, *p1))
    QTest.mouseRelease(c, Qt.MouseButton.LeftButton, pos=canvas_point(win, *p1))


def test_starts_on_home_with_working_navigation(win):
    assert win.stack.currentWidget() is win.dashboard
    for page in ("whiteboard", "teaching", "calibration", "camera", "settings", "home"):
        win.navigate(page)
        assert win.stack.currentWidget() is win.pages[page]
        assert win._nav_buttons[page].isChecked()


def test_every_dashboard_card_navigates_or_acts(win, monkeypatch):
    targets = ["whiteboard", None, "teaching", "calibration", "camera", "settings"]
    opened = []
    monkeypatch.setattr(win.whiteboard, "open_image_dialog", lambda: opened.append(1) or False)
    for card, target in zip(win.dashboard.cards, targets):
        win.navigate("home")
        card.clicked.emit()
        if target:
            assert win.stack.currentWidget() is win.pages[target]
        else:
            assert opened == [1]


def test_mouse_pen_draws_and_undo_redo(win):
    win.navigate("whiteboard")
    wb = win.whiteboard
    drag(win, (200, 200), (600, 400))
    assert wb.engine.has_ink and wb.engine.can_undo
    assert wb.action_bar.undo_btn.isEnabled()
    wb.undo()
    assert not wb.engine.has_ink and wb.action_bar.redo_btn.isEnabled()
    wb.redo()
    assert wb.engine.has_ink


@pytest.mark.parametrize("tool", ["line", "rect", "circle"])
def test_shape_tools_commit_on_release(win, tool):
    win.navigate("whiteboard")
    wb = win.whiteboard
    wb.select_tool(tool)
    drag(win, (300, 300), (500, 450))
    assert wb.engine.has_ink and wb.engine.history_size == 1


def test_eraser_removes_ink(win):
    win.navigate("whiteboard")
    wb = win.whiteboard
    drag(win, (200, 300), (800, 300))
    before = int(wb.engine.ink[..., 3].astype(np.int64).sum())
    wb.select_tool("eraser")
    drag(win, (400, 300), (600, 300))
    assert int(wb.engine.ink[..., 3].astype(np.int64).sum()) < before


def test_colour_and_thickness_apply_to_new_strokes(win):
    win.navigate("whiteboard")
    wb = win.whiteboard
    wb.style_bar._swatches["#e11d48"].click()
    wb.style_bar.slider.setValue(20)
    drag(win, (300, 300), (700, 300))
    pixel = wb.engine.composite[300, 500]
    assert tuple(pixel) == (0x48, 0x1D, 0xE1)           # BGR of #E11D48
    thick_rows = np.count_nonzero((wb.engine.ink[:, 500, 3] > 200))
    assert 18 <= thick_rows <= 21


def test_clear_requires_confirmation(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    win.navigate("whiteboard")
    wb = win.whiteboard
    drag(win, (200, 200), (600, 400))
    # user cancels
    monkeypatch.setattr(QMessageBox, "exec", lambda self: self.setProperty("x", 1) or 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: None)
    wb.confirm_clear()
    assert wb.engine.has_ink
    # user confirms
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: self.buttons()[0])
    wb.confirm_clear()
    assert not wb.engine.has_ink
    wb.undo()
    assert wb.engine.has_ink            # clearing is undoable


def test_open_invalid_and_valid_images(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a[1]))
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    assert win.whiteboard.open_path(str(bad)) is False
    wrong_ext = tmp_path / "doc.txt"
    wrong_ext.write_text("x")
    assert win.whiteboard.open_path(str(wrong_ext)) is False
    assert len(warnings) == 2 and not win.whiteboard.engine.has_background

    good = tmp_path / "été.png"
    imwrite_unicode(good, np.full((120, 300, 3), (20, 120, 220), np.uint8))
    assert win.whiteboard.open_path(str(good)) is True
    assert win.whiteboard.engine.has_background
    assert str(good.resolve()) in win.settings.recent_files()


def test_save_png_roundtrip(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    win.navigate("whiteboard")
    drag(win, (200, 200), (600, 400))
    target = tmp_path / "board.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    assert win.whiteboard.save_png_dialog() is True
    assert target.exists() and target.stat().st_size > 100


def test_reset_restores_blank_state(win, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    win.navigate("whiteboard")
    drag(win, (200, 200), (600, 400))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    win.whiteboard.confirm_reset()
    e = win.whiteboard.engine
    assert not e.has_ink and e.history_size == 0 and not e.can_undo


def test_fullscreen_toggle_hides_sidebar(win):
    win.set_fullscreen(True)
    assert win.isFullScreen() and win.sidebar.isHidden()
    win._escape()
    assert not win.isFullScreen() and not win.sidebar.isHidden()


def test_escape_cancels_shape_in_progress(win):
    win.navigate("whiteboard")
    wb = win.whiteboard
    wb.select_tool("rect")
    c = wb.canvas
    QTest.mousePress(c, Qt.MouseButton.LeftButton, pos=canvas_point(win, 200, 200))
    QTest.mouseMove(c, canvas_point(win, 400, 300))
    win._escape()
    QTest.mouseRelease(c, Qt.MouseButton.LeftButton, pos=canvas_point(win, 400, 300))
    assert not wb.engine.has_ink


def test_pointer_api_draws_like_the_mouse(win):
    """The camera pipeline will drive the canvas through these exact calls."""
    win.navigate("whiteboard")
    c = win.whiteboard.canvas
    c.pointer_down(100, 100)
    c.pointer_move(300, 200)
    c.pointer_up(500, 200)
    assert win.whiteboard.engine.has_ink


def test_settings_persist_between_runs(qapp, tmp_path):
    path = tmp_path / "s.json"
    w = MainWindow(Settings(path), AppState())
    w.whiteboard.style_bar.slider.setValue(17)
    w.whiteboard.select_tool("circle")
    w.close()
    again = Settings(path)
    assert again.get("pen.thickness") == 17 and again.get("pen.tool") == "circle"


def test_corrupt_settings_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{ this is not json")
    s = Settings(path)
    assert s.get("board.width") == 1600 and s.load_error
