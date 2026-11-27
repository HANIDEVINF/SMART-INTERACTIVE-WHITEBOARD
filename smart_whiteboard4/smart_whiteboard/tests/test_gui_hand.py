"""GUI side of the hand backend: pinch events act like the remote keys; the settings panel switches the source."""
from types import SimpleNamespace

from tests.test_gui_interaction import qapp, win  # noqa: F401  (fixtures)


def result(event, x=400.0, y=300.0):
    return SimpleNamespace(calib_state="ok", board=SimpleNamespace(x=x, y=y), tracking_fps=30.0, gesture_event=event,
                           track=SimpleNamespace(state="tracking", position=(1.0, 1.0)))


def test_pinch_next_is_a_left_click_and_previous_a_right_click(win):
    wb = win.whiteboard
    wb.action_bar.track_btn.setChecked(True)
    wb.show_vision_result(result(None))
    assert not wb.canvas.ripples
    wb.show_vision_result(result("next"))
    assert [r.kind for r in wb.canvas.ripples] == ["left"]
    wb.show_vision_result(result("previous"))
    assert wb.canvas.ripples[-1].kind == "right"


def test_pinch_in_drawing_mode_toggles_the_pen(win):
    wb = win.whiteboard
    wb.action_bar.track_btn.setChecked(True)
    wb.set_mode("drawing", announce=False)
    wb.select_tool("pen")
    wb.show_vision_result(result(None))
    wb.show_vision_result(result("next"))
    assert wb.interaction.pen_down
    wb.show_vision_result(result("previous"))
    assert not wb.interaction.pen_down


def test_settings_switch_to_hand_source_and_persist(win):
    win.navigate("settings", animate=False)
    page = win.pages["settings"]
    assert page.method_combo.currentData() == "color_marker"
    page.method_combo.setCurrentIndex(1)
    assert win.controller.detection_params.method == "hand"
    assert win.settings.get("detection.method") == "hand"
    assert page.hand_status.text()                     # explains whether the model / MediaPipe is ready
    page.method_combo.setCurrentIndex(0)
    assert win.controller.detection_params.method == "color_marker"
