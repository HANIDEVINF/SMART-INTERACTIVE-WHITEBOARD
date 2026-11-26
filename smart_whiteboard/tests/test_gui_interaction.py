"""Phase 5 integration: remote keys, interaction modes, on-board menu, pointer drawing, key diagnostics."""
import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.app_state import AppState
from core.interaction import Mode
from core.remote_control import RemoteAction
from core.settings import Settings
from tests.qt_helpers import run_loop, wait_until
from tests.synthetic import render_scene
from tests.test_gui_vision import CAM, Rig
from ui.main_window import MainWindow
from ui.styles import STYLESHEET

K = Qt.Key
BW, BH = 1600, 900


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app


@pytest.fixture
def win(qapp, tmp_path):
    w = MainWindow(Settings(tmp_path / "settings.json"), AppState())
    w.resize(1360, 840)
    w.show()
    w.navigate("whiteboard", animate=False)
    qapp.processEvents()
    yield w
    w.close()


def key(win, k, mods=Qt.KeyboardModifier.NoModifier):
    QTest.keyClick(win.whiteboard.canvas, k, mods)
    QApplication.processEvents()


def hover(win, bx, by):
    """Deliver a real mouse-move event (QTest.mouseMove skips moves to the cursor's current position)."""
    c = win.whiteboard.canvas
    pt = c.board_to_widget(bx, by)
    QApplication.sendEvent(c, QMouseEvent(QEvent.Type.MouseMove, pt, c.mapToGlobal(pt), Qt.MouseButton.NoButton,
                                          Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
    QApplication.processEvents()


def click_item(win, item_id):
    wb = win.whiteboard
    slot = next(s for s in wb.menu.layout(BW, BH) if s.id == item_id)
    x, y, w, h = slot.rect
    QTest.mouseClick(wb.canvas, Qt.MouseButton.LeftButton, pos=wb.canvas.board_to_widget(x + w / 2, y + h / 2).toPoint())
    QApplication.processEvents()


def slot_center(win, item_id):
    slot = next(s for s in win.whiteboard.menu.layout(BW, BH) if s.id == item_id)
    x, y, w, h = slot.rect
    return x + w / 2, y + h / 2


# ------------------------------------------------------------------------------------------- remote keys
def test_next_is_a_left_click_and_previous_a_right_click_at_the_pointer(win):
    wb = win.whiteboard
    assert win.remote.enabled
    hover(win, 900, 450)
    key(win, K.Key_Right)
    assert [r.kind for r in wb.canvas.ripples] == ["left"]
    assert (wb.canvas.ripples[0].x, wb.canvas.ripples[0].y) == pytest.approx((900, 450), abs=2)
    run_loop(300)                                        # past the debounce time
    key(win, K.Key_Left)
    assert [r.kind for r in wb.canvas.ripples][-1] == "right"
    assert wb.menu.is_open                               # Previous with no menu and no pen = open the menu


def test_pagedown_pageup_are_accepted_as_clicker_keys(win):
    hover(win, 900, 450)
    key(win, K.Key_PageDown)
    run_loop(300)
    key(win, K.Key_PageUp)
    assert [r.kind for r in win.whiteboard.canvas.ripples] == ["left", "right"]


def test_repeated_presses_are_debounced_and_auto_repeat_is_ignored(win):
    hover(win, 900, 450)
    key(win, K.Key_Right)
    key(win, K.Key_Right)
    key(win, K.Key_Right)
    assert win.remote.counts[RemoteAction.NEXT] == 1
    run_loop(300)
    key(win, K.Key_Right)
    assert win.remote.counts[RemoteAction.NEXT] == 2


def test_remote_only_acts_on_the_whiteboard_page(win):
    win.navigate("home", animate=False)
    assert not win.remote.enabled
    before = len(win.whiteboard.canvas.ripples)
    QTest.keyClick(win.dashboard, K.Key_Right)
    assert win.remote.counts[RemoteAction.NEXT] == 0 and len(win.whiteboard.canvas.ripples) == before
    win.navigate("whiteboard", animate=False)
    assert win.remote.enabled


def test_no_pointer_gives_a_warning_not_a_click(win):
    toasts = []
    win.whiteboard.message.connect(lambda t, k: toasts.append((t, k)))
    c = win.whiteboard.canvas
    c._hover = None
    win.whiteboard.on_remote_next()
    assert win.whiteboard.canvas.ripples == [] and toasts and toasts[-1][1] == "warn"


# ---------------------------------------------------------------------------------------------- the menu
def test_menu_is_operated_with_the_mouse_through_submenus(win):
    wb = win.whiteboard
    key(win, K.Key_M)
    assert wb.menu.is_open and wb.menu.title == "Menu"
    click_item(win, "drawing")
    assert wb.menu.title == "Menu / Drawing"
    click_item(win, "tool.eraser")
    assert wb.canvas.tool.value == "eraser"
    click_item(win, "colours")
    click_item(win, "color.#E11D48")
    assert wb.canvas.color.name().upper() == "#E11D48"
    click_item(win, "@back")
    assert wb.menu.title == "Menu / Drawing"
    click_item(win, "thickness")
    click_item(win, "th.thick")
    assert wb.canvas.thickness == 18


def test_clicking_the_menu_does_not_draw_underneath(win):
    wb = win.whiteboard
    key(win, K.Key_M)
    click_item(win, "image")
    assert not wb.engine.has_ink


def test_clear_needs_confirmation_and_cancel_keeps_the_drawing(win):
    wb = win.whiteboard
    wb.engine.draw_line((100, 100), (500, 400), (0, 0, 0), 6)
    key(win, K.Key_M)
    click_item(win, "drawing")
    click_item(win, "clear")
    assert wb.engine.has_ink and wb.menu.title.endswith("Clear board")
    click_item(win, "clear.no")
    assert wb.engine.has_ink
    click_item(win, "clear")
    click_item(win, "clear.yes")
    assert not wb.engine.has_ink and not wb.menu.is_open


def test_keyboard_navigation_of_the_menu(win):
    wb = win.whiteboard
    key(win, K.Key_M)
    key(win, K.Key_Down)
    key(win, K.Key_Return)                               # second entry of the main menu: Image
    assert wb.menu.title == "Menu / Image"
    key(win, K.Key_Backspace)
    assert wb.menu.title == "Menu"
    key(win, K.Key_Up)
    assert wb.canvas.menu_focus == "@close"
    key(win, K.Key_Return)
    assert not wb.menu.is_open


def test_escape_closes_the_menu_first(win):
    key(win, K.Key_M)
    QTest.keyClick(win, K.Key_Escape)
    assert not win.whiteboard.menu.is_open


def test_menu_navigation_items_change_page(win):
    wb = win.whiteboard
    key(win, K.Key_M)
    click_item(win, "settings")
    click_item(win, "nav.remote")
    assert win.current_page == "settings" and win.pages["settings"].tabs.currentWidget() is win.pages["settings"].remote_panel
    win.navigate("whiteboard", animate=False)
    key(win, K.Key_M)
    click_item(win, "presentation")
    click_item(win, "nav.home")
    assert win.current_page == "home"


def test_menu_flags_show_current_state(win):
    wb = win.whiteboard
    wb.select_tool("circle")
    key(win, K.Key_2)
    wb._sync_menu()
    assert wb.menu.flags["tool:circle"] and wb.menu.flags["mode:drawing"]


# ---------------------------------------------------------------------------------------- modes + drawing
def test_mode_keys_and_buttons(win):
    wb = win.whiteboard
    key(win, K.Key_2)
    assert wb.mode is Mode.DRAWING and wb.action_bar.mode_buttons["drawing"].isChecked()
    key(win, K.Key_3)
    assert wb.mode is Mode.SELECTION
    wb.action_bar.mode_buttons["navigation"].click()
    assert wb.mode is Mode.NAVIGATION
    assert wb.settings.get("interaction.mode") == "navigation"


def test_drawing_mode_next_toggles_pen_and_moving_draws(win):
    wb = win.whiteboard
    key(win, K.Key_2)
    wb.select_tool("pen")
    hover(win, 300, 300)
    key(win, K.Key_Right)
    assert wb.interaction.pen_down and wb.canvas.hud_pen_down
    for x in range(300, 800, 50):
        hover(win, x, 300 + (x - 300) // 5)
    run_loop(300)
    key(win, K.Key_Right)
    assert not wb.interaction.pen_down
    assert wb.engine.has_ink and wb.engine.can_undo
    ink = wb.engine.composite[330:350, 490:510]     # rows = y, columns = x
    assert (ink < 200).any()                              # a stroke really passes there


def test_previous_lifts_the_pen_without_opening_the_menu(win):
    wb = win.whiteboard
    key(win, K.Key_2)
    hover(win, 300, 300)
    key(win, K.Key_Right)
    run_loop(300)
    key(win, K.Key_Left)
    assert not wb.interaction.pen_down and not wb.menu.is_open


def test_leaving_the_board_lifts_the_pen(win):
    wb = win.whiteboard
    key(win, K.Key_2)
    hover(win, 300, 300)
    key(win, K.Key_Right)
    assert wb.interaction.pen_down
    wb.canvas.leaveEvent(None)
    QApplication.processEvents()
    assert not wb.interaction.pen_down


def test_selection_mode_confirms_a_menu_item_by_dwell(win):
    wb = win.whiteboard
    wb.set_dwell_ms(300)
    key(win, K.Key_3)
    key(win, K.Key_M)
    hover(win, *slot_center(win, "drawing"))
    assert wb.menu.title == "Menu"
    assert wait_until(lambda: wb.menu.title == "Menu / Drawing", 3000)
    assert wb.canvas.dwell_target is None or wb.canvas.dwell_progress < 1.0


def test_selection_mode_does_not_fire_when_pointer_moves_on(win):
    wb = win.whiteboard
    wb.set_dwell_ms(600)
    key(win, K.Key_3)
    key(win, K.Key_M)
    hover(win, *slot_center(win, "drawing"))
    run_loop(250)
    hover(win, 1200, 700)
    run_loop(700)
    assert wb.menu.title == "Menu"


# ---------------------------------------------------------------------------------- camera as the pointer
def test_camera_pointer_draws_in_drawing_mode_and_lifts_when_lost(rig_factory):
    r, pos = rig_factory
    wb = r.win.whiteboard
    r.calibrate()
    r.win.navigate("whiteboard", animate=False)
    wb.action_bar.track_btn.setChecked(True)
    assert wait_until(lambda: wb.canvas.pointer_pos is not None and wb.canvas.pointer_state == "tracking", 6000)
    wb.set_mode("drawing", announce=False)
    wb.select_tool("pen")
    assert wb.canvas.hud_source == "camera" or wait_until(lambda: wb.canvas.hud_source == "camera")
    key(r.win, K.Key_Right)
    assert wb.interaction.pen_down
    for x in (500, 600, 700, 800, 900):
        pos["p"] = (x, 400)
        run_loop(180)
    assert wb.engine.has_ink or wb.interaction.pen_down
    pos["p"] = None                                       # marker hidden -> pointer lost
    assert wait_until(lambda: not wb.interaction.pen_down, 5000)
    assert wb.engine.has_ink and wb.engine.can_undo       # the stroke was committed, not discarded


@pytest.fixture
def rig_factory(qapp, tmp_path):
    pos = {"p": (400.0, 400.0)}
    r = Rig(tmp_path, lambda i: render_scene(pos["p"], noise=3))
    yield r, pos
    r.close()


# ------------------------------------------------------------------------------------- settings panel
def open_remote_tab(win):
    win.navigate("settings", animate=False)
    win.pages["settings"].show_remote_tab()
    QApplication.processEvents()
    return win.pages["settings"].remote_panel


def test_diagnostics_records_key_codes_and_performs_no_action(win):
    panel = open_remote_tab(win)
    panel.diag_btn.setChecked(True)
    assert win.remote.diagnostics
    QTest.keyClick(panel.log_view, K.Key_Right)
    QTest.keyClick(panel.log_view, K.Key_PageDown)
    recs = win.remote.log.presses()
    assert [r.name for r in recs][:2] == ["Right", "PgDown"]
    assert recs[0].qt_key == int(K.Key_Right)
    assert "bound to NEXT" in recs[0].result
    assert "Right" in panel.log_view.toPlainText() and "Qt key code" not in panel.summary.text() or panel.summary.text()
    assert win.remote.counts[RemoteAction.NEXT] == 0
    win.navigate("home", animate=False)                   # leaving the page stops diagnostics
    assert not win.remote.diagnostics


def test_rebinding_a_key_is_saved_and_used(win):
    panel = open_remote_tab(win)
    panel._begin_capture(RemoteAction.NEXT, add=False)
    assert win.remote.capturing
    QTest.keyClick(panel, K.Key_N)
    assert win.remote.mapper.next_keys == ("N",)
    assert win.settings.get("remote.next_keys") == ["N"]
    win.navigate("whiteboard", animate=False)
    hover(win, 900, 450)
    key(win, K.Key_N)
    assert win.remote.counts[RemoteAction.NEXT] == 1


def test_adding_a_key_for_a_real_remote_and_moving_a_key_between_buttons(win):
    panel = open_remote_tab(win)
    panel._begin_capture(RemoteAction.PREVIOUS, add=True)
    QTest.keyClick(panel, K.Key_F5)
    assert "F5" in win.remote.mapper.previous_keys and "Left" in win.remote.mapper.previous_keys
    panel._begin_capture(RemoteAction.NEXT, add=True)     # steal Left from Previous
    QTest.keyClick(panel, K.Key_Left)
    assert "Left" in win.remote.mapper.next_keys and "Left" not in win.remote.mapper.previous_keys


def test_escape_cancels_capturing_and_default_keys_can_be_restored(win):
    panel = open_remote_tab(win)
    panel._begin_capture(RemoteAction.NEXT, add=False)
    QTest.keyClick(panel, K.Key_Escape)
    assert win.remote.mapper.next_keys == ("Right", "PgDown")
    panel._begin_capture(RemoteAction.NEXT, add=False)
    QTest.keyClick(panel, K.Key_N)
    panel._restore_defaults()
    assert win.remote.mapper.next_keys == ("Right", "PgDown")


def test_saved_bindings_load_at_startup_and_corrupt_ones_fall_back(qapp, tmp_path):
    s = Settings(tmp_path / "s.json")
    s.set("remote.next_keys", ["X"])
    s.set("remote.previous_keys", ["Y"])
    w = MainWindow(s, AppState())
    assert w.remote.mapper.next_keys == ("X",)
    w.close()
    s.set("remote.next_keys", ["Y"])                      # conflicts with Previous
    w = MainWindow(s, AppState())
    assert w.remote.mapper.next_keys == ("Right", "PgDown")
    w.close()


def test_reset_application_restores_keys_and_mode(win):
    panel = open_remote_tab(win)
    panel._begin_capture(RemoteAction.NEXT, add=False)
    QTest.keyClick(panel, K.Key_N)
    win.whiteboard.set_mode("drawing", announce=False)
    win.reset_application()
    assert win.remote.mapper.next_keys == ("Right", "PgDown")
    assert win.whiteboard.mode is Mode.NAVIGATION


# --------------------------------------------------------------------------------------------- image viewer
def _image(win, tmp_path):
    import numpy as np
    from tools.image_tools import imwrite_unicode
    img = np.zeros((600, 800, 3), np.uint8)
    img[:, :400] = (200, 80, 40)
    img[:, 400:] = (40, 160, 220)
    p = tmp_path / "pic.png"
    imwrite_unicode(p, img)
    assert win.whiteboard.open_path(str(p))


def test_zoom_buttons_keys_and_menu(win, tmp_path):
    wb = win.whiteboard
    _image(win, tmp_path)
    assert wb.canvas.view.is_identity and wb.style_bar.zoom_label.text() == "100%"
    wb.style_bar.zoom_in_btn.click()
    assert wb.canvas.view.zoom == pytest.approx(1.25) and wb.style_bar.zoom_label.text() == "125%"
    key(win, K.Key_Plus)
    assert wb.canvas.view.zoom == pytest.approx(1.25 ** 2)
    key(win, K.Key_Minus)
    key(win, K.Key_Minus)
    assert wb.canvas.view.is_identity
    key(win, K.Key_M)
    click_item(win, "image")
    click_item(win, "view.in")
    click_item(win, "view.in")
    assert wb.canvas.view.zoom > 1.5 and wb.menu.is_open                  # the menu stays open for repeated steps
    click_item(win, "view.fit")
    assert wb.canvas.view.is_identity


def test_wheel_zooms_at_the_cursor_and_panning_by_drag_keys_and_menu(win, tmp_path):
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    wb = win.whiteboard
    _image(win, tmp_path)
    c = wb.canvas
    pt = c.board_to_widget(1200, 300)
    anchor_before = c.view.to_content(1200, 300)
    QApplication.sendEvent(c, QWheelEvent(pt, c.mapToGlobal(pt), QPoint(0, 0), QPoint(0, 240),
                                          Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                                          Qt.ScrollPhase.NoScrollPhase, False))
    assert c.view.zoom > 1.5 and c.view.to_content(1200, 300) == pytest.approx(anchor_before)
    x0 = c.view.ox
    key(win, K.Key_Right, Qt.KeyboardModifier.ControlModifier)          # Ctrl+Right moves the view right
    assert c.view.ox < x0
    c.set_pan_mode(True)
    c.pointer_down(800, 450)
    c.pointer_move(700, 450)
    c.pointer_up(700, 450)
    assert c.view.ox < x0 - 50 and not wb.engine.has_ink
    c.set_pan_mode(False)


def test_annotations_stay_glued_to_the_image_when_zoomed(win, tmp_path):
    wb = win.whiteboard
    _image(win, tmp_path)
    c = wb.canvas
    c.view.set_zoom_at(2, 0, 0)                    # zoom about the top-left corner
    wb.select_tool("pen")
    c.pointer_down(400, 200)
    c.pointer_move(600, 200)
    c.pointer_up(600, 200)
    ys, xs = (wb.engine.ink[..., 3] > 0).nonzero()
    assert xs.min() == pytest.approx(200, abs=8) and xs.max() == pytest.approx(300, abs=8)   # content coordinates
    assert ys.mean() == pytest.approx(100, abs=4)


def test_pointer_in_drawing_mode_draws_at_the_zoomed_position(win, tmp_path):
    wb = win.whiteboard
    _image(win, tmp_path)
    wb.canvas.view.set_zoom_at(4, 0, 0)
    key(win, K.Key_2)
    hover(win, 800, 400)
    key(win, K.Key_Right)
    hover(win, 1000, 400)
    run_loop(300)
    key(win, K.Key_Right)
    ys, xs = (wb.engine.ink[..., 3] > 0).nonzero()
    assert xs.min() == pytest.approx(200, abs=10) and xs.max() == pytest.approx(250, abs=10)


def test_render_zoomed_view_and_reset_clears_the_view(win, tmp_path):
    wb = win.whiteboard
    _image(win, tmp_path)
    wb.canvas.zoom_in()
    wb.canvas.grab()                                # painting the layered path must not raise
    wb.reset()
    assert wb.canvas.view.is_identity and not wb.canvas.pan_mode
