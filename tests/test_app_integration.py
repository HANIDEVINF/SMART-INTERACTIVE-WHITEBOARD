"""Integration tests: the full app starts, runs frames, navigates every
screen and shuts down cleanly in simulation mode (no hardware needed)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_app(monkeypatch, tmp_path, width=1280, height=720, **overrides):
    """Build a real SmartBoardApp with simulated camera and temp config."""
    import config.settings as cs
    import interface.app as appmod

    pygame.init()
    monkeypatch.setattr(cs, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(cs, "CALIBRATION_PATH", tmp_path / "calibration.json")
    settings = {**cs.DEFAULT_SETTINGS, "camera_source": "simulated",
                "pointer_mode": "mouse", "remote_mode": "keyboard",
                "fullscreen": False, "display_width": width,
                "display_height": height, **overrides}
    # app.py imported load_settings by name, so patch it THERE (patching
    # config.settings.load_settings has no effect on the app).
    monkeypatch.setattr(appmod, "load_settings", lambda: dict(settings))
    return appmod.SmartBoardApp()


def test_app_startup_shutdown(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path, 640, 480)
    assert app.camera_ok is True
    for _ in range(30):
        app.step(0.016)
    for name in list(app.screens):
        app.go_to(name)
        app.step(0.016)
        app.go_home()
    app._shutdown()


def test_restart_does_not_crash(monkeypatch, tmp_path):
    """Regression: shutting down used to call pygame.quit(), so the
    second app (restart) could not create its window or fonts."""
    app = make_app(monkeypatch, tmp_path, 640, 480)
    app.step(0.016)
    app._shutdown()
    app2 = make_app(monkeypatch, tmp_path, 640, 480)
    app2.step(0.016)
    app2.current_screen.draw()
    app2._shutdown()


def test_home_and_back_navigation(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app.go_to("menu_draw")
    app.go_to("drawing")
    assert app.screen_stack == ["menu", "menu_draw"]
    app.go_back()
    assert app.current_screen_name == "menu_draw"
    app.go_to("drawing")
    app.go_home()
    assert app.current_screen_name == "menu" and app.screen_stack == []
    app._shutdown()


def test_submenus_navigate_to_screens(monkeypatch, tmp_path):
    """The brief requires a main menu AND at least one submenu level."""
    app = make_app(monkeypatch, tmp_path)
    main = app.screens["menu"]
    tile = {b.title: b for b in main.buttons}
    tile["Whiteboard"].on_click()
    assert app.current_screen_name == "menu_draw"
    sub = {b.title: b for b in app.current_screen.buttons}
    sub["Dark board"].on_click()
    assert app.current_screen_name == "drawing"
    assert app.screens["drawing"].board_style == "dark"
    app._shutdown()


def test_mouse_wheel_is_not_a_click(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app._update_pointer()
    pygame.event.clear()
    for button in (4, 5):
        pygame.event.post(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=button, pos=(10, 10)))
    assert app._collect_clicks() == []
    pygame.event.post(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=3, pos=(10, 10)))
    assert [c[0] for c in app._collect_clicks()] == ["right"]
    app._shutdown()


@pytest.mark.parametrize("size", [(640, 480), (1280, 720), (1600, 900),
                                  (1920, 1080)])
def test_all_buttons_stay_inside_the_usable_area(monkeypatch, tmp_path, size):
    """Regression: toolbars used to overflow the window and hide under the
    status bar.  Every visible button must lie inside the area above the
    status bar, at every supported display size."""
    from interface.components import STATUS_H
    app = make_app(monkeypatch, tmp_path, *size)
    usable = pygame.Rect(0, 0, size[0], size[1] - STATUS_H)
    for name, screen in app.screens.items():
        for b in screen.all_buttons():
            assert usable.contains(b.rect), (name, b.label, b.rect, usable)
    app._shutdown()


def test_calibration_clicks_are_registered(monkeypatch, tmp_path):
    """Regression: the screen compared the button to the integer 1 while
    the app sends "left"/"right", so no calibration click ever counted."""
    app = make_app(monkeypatch, tmp_path)
    app.go_to("calibration")
    scr = app.current_screen
    for _ in range(3):
        scr.update(0.016)
    r = scr._img_rect
    corners = [(r.x + 0.2 * r.w, r.y + 0.2 * r.h),
               (r.x + 0.8 * r.w, r.y + 0.2 * r.h),
               (r.x + 0.8 * r.w, r.y + 0.8 * r.h),
               (r.x + 0.2 * r.w, r.y + 0.8 * r.h)]
    for c in corners:
        scr.on_click(c, "left")
    assert len(app.calibration.clicked_points) == 4
    assert scr._H is not None
    scr.update(0.016)                           # enables the Save button
    scr.on_click(scr.btn_save.rect.center, "left")
    assert app.calibration.mapper.is_calibrated
    assert (tmp_path / "calibration.json").exists()
    app._shutdown()


def test_calibration_rejects_wrong_corner_order(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app.go_to("calibration")
    scr = app.current_screen
    scr.update(0.016)
    r = scr._img_rect
    ccw = [(r.x + 0.2 * r.w, r.y + 0.2 * r.h),
           (r.x + 0.2 * r.w, r.y + 0.8 * r.h),
           (r.x + 0.8 * r.w, r.y + 0.8 * r.h),
           (r.x + 0.8 * r.w, r.y + 0.2 * r.h)]
    for c in ccw:
        scr.on_click(c, "left")
    assert scr._H is None
    assert "order" in app.calibration.last_error
    app._shutdown()


def test_lesson_right_click_goes_to_previous_page(monkeypatch, tmp_path):
    """Regression: the screen tested ``button == 2`` but received "right"."""
    app = make_app(monkeypatch, tmp_path)
    app.go_to("lesson")
    lesson = app.current_screen
    lesson.on_click((600, 300), "left")
    lesson.on_click((600, 300), "left")
    assert lesson.page_idx == 2
    lesson.on_click((600, 300), "right")
    assert lesson.page_idx == 1
    app._shutdown()


def test_drawing_pen_toggle_and_undo(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app.go_to("drawing")
    d = app.current_screen
    c = d.canvas_rect.center
    app.pointer_pos, app.pointer_visible = (float(c[0]), float(c[1])), True
    d.on_click(c, "left")                       # pen down
    assert d.pen_down
    for i in range(1, 15):                      # move -> a stroke appears
        app.pointer_pos = (c[0] + 6.0 * i, float(c[1]))
        d.update(0.016)
    assert d.canvas.layer[..., 3].any()
    d.on_click(c, "left")                       # pen up
    assert not d.pen_down
    d.update(0.016)
    assert len(d.canvas.strokes) == 1
    d.on_click(c, "right")                      # right click = undo
    assert len(d.canvas.strokes) == 0
    assert not d.canvas.layer[..., 3].any()
    app._shutdown()


def test_drawing_stops_when_pointer_leaves_board(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app.go_to("drawing")
    d = app.current_screen
    c = d.canvas_rect.center
    app.pointer_pos, app.pointer_visible = (float(c[0]), float(c[1])), True
    d.on_click(c, "left")
    d.update(0.016)
    app.pointer_pos = (50.0, 10.0)               # over the header
    d.update(0.016)
    assert not d.pen_down
    app._shutdown()


def test_clear_needs_confirmation(monkeypatch, tmp_path):
    app = make_app(monkeypatch, tmp_path)
    app.go_to("drawing")
    d = app.current_screen
    d.canvas.begin_stroke((10, 10), (0, 0, 0, 255), 4)
    d.canvas.extend_stroke((60, 60))
    d.canvas.end_stroke()
    d._clear()
    assert len(d.canvas.strokes) == 1            # first click only arms
    d._clear()
    assert len(d.canvas.strokes) == 0
    app._shutdown()


def test_image_viewer_loads_and_zooms(monkeypatch, tmp_path):
    from interface.image_viewer import list_gallery_images
    assert list_gallery_images(), "sample images are missing"
    app = make_app(monkeypatch, tmp_path)
    app.go_to("image")
    v = app.current_screen
    assert v.load_path(list_gallery_images()[0])
    for _ in range(3):
        v.update(0.016)
        v.draw()
    v._zoom_by(1.25)
    v._zoom_by(1.25)
    v._pan(1, 0)
    v.draw()
    assert v.zoom > 1.0 and v.center[0] > 0.5
    v.on_click((100, 100), "right")              # right click zooms out
    assert v.zoom < 1.5625
    v._reset_zoom()
    assert v.zoom == 1.0 and v.center == (0.5, 0.5)
    app._shutdown()
