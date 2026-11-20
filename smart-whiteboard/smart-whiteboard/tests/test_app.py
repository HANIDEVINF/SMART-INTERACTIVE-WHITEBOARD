"""Headless end-to-end tests of the whole application (no window, no camera).

The mouse pointer source stands in for the vision pipeline; clicks are
injected exactly like remote events.  Set SWB_SHOTS=<dir> to save screenshots.
"""
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from smartboard.app import App
from smartboard.config import Config
from smartboard.events import LEFT, RIGHT, ClickEvent
from smartboard.vision.calibration import Calibration
from smartboard.vision.pointer_source import MousePointerSource

SHOTS = os.environ.get("SWB_SHOTS")


def make_app(w=960, h=540):
    cfg = Config()
    cfg.display.width, cfg.display.height = w, h
    cfg.assets_dir = os.path.join(ROOT, "assets")
    calib = Calibration(w, h)
    calib.fit([(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 0), (1, 0), (1, 1), (0, 1)])
    src = MousePointerSource()
    return App(cfg, src, calib, mouse_mode=True), src


def shot(app, name):
    if SHOTS:
        import cv2
        os.makedirs(SHOTS, exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, name + ".png"), app.canvas.img)


def point(app, src, x, y):
    src.pos = (float(x), float(y))
    app.frame()


def click(app, src, x, y, button=LEFT):
    point(app, src, x, y)
    app.frame(remote_buttons=[button])          # same path as a real remote press


def click_label(app, src, label, button=LEFT):
    for b in app.nav.current.buttons:
        if label.lower() in b.text().lower():
            x0, y0, x1, y1 = b.rect
            click(app, src, (x0 + x1) / 2, (y0 + y1) / 2, button)
            return b
    raise AssertionError(f"no button '{label}' on {type(app.nav.current).__name__}: "
                         f"{[b.text() for b in app.nav.current.buttons]}")


def test_menu_and_submenu():
    app, src = make_app()
    app.frame(); shot(app, "01_main_menu")
    click_label(app, src, "Draw")
    assert app.nav.current.path, "submenu should be open"
    app.frame(); shot(app, "02_submenu_draw")
    click(app, src, 400, 300, RIGHT)                    # RIGHT = back one level
    assert not app.nav.current.path
    click_label(app, src, "Draw")
    click_label(app, src, "< Back")
    assert not app.nav.current.path


def test_drawing_colours_sizes_clear():
    app, src = make_app()
    click_label(app, src, "Draw"); click_label(app, src, "Free drawing")
    assert type(app.nav.current).__name__ == "DrawScreen"
    d = app.ctx.drawing
    click_label(app, src, "Cyan"); assert d.color_idx == 1
    click_label(app, src, "Thick"); assert d.size_idx == 2
    click(app, src, 400, 200)                           # pen down
    assert d.pen_down
    for i in range(30):
        point(app, src, 400 + i * 8, 200 + 60 * np.sin(i / 4))
    click(app, src, 640, 260)                           # pen up
    assert not d.pen_down and d.mask.sum() > 500
    click_label(app, src, "Green"); click_label(app, src, "Thin")
    click(app, src, 300, 400)
    for i in range(20):
        point(app, src, 300 + i * 10, 400 - i * 4)
    click(app, src, 500, 320)
    n_strokes = len(d.strokes)
    assert n_strokes == 2
    app.frame(); shot(app, "03_drawing")
    click_label(app, src, "Undo"); assert len(d.strokes) == 1
    click_label(app, src, "Clear"); assert d.mask.sum() == 0 and not d.strokes
    click(app, src, 400, 200, RIGHT)                    # RIGHT with pen up -> back to menu
    assert type(app.nav.current).__name__ == "MenuScreen"


def test_pen_lifts_over_toolbar_and_eraser():
    app, src = make_app()
    click_label(app, src, "Draw"); click_label(app, src, "Free drawing")
    d = app.ctx.drawing
    click(app, src, 400, 200)
    for i in range(10):
        point(app, src, 400 + i * 10, 200)
    ink = d.mask.sum()
    point(app, src, 20, 200)                            # moved onto the toolbar
    assert not d.pen_down
    click_label(app, src, "Eraser")
    click(app, src, 400, 200)
    for i in range(12):
        point(app, src, 400 + i * 10, 200)
    click(app, src, 520, 300)
    assert d.mask.sum() < ink


def test_image_zoom_pan_reset():
    app, src = make_app()
    click_label(app, src, "Images"); click_label(app, src, "Gallery")
    v = app.ctx.viewer
    assert v.img is not None
    app.frame(); shot(app, "04_image")
    click_label(app, src, "Zoom +"); click_label(app, src, "Zoom +")
    assert v.zoom > 1.5
    click(app, src, 480, 250)                           # grab
    assert v.panning
    c0 = v.center
    for i in range(10):
        point(app, src, 480 + i * 12, 250)
    assert v.center != c0
    app.frame(); shot(app, "05_image_zoomed")
    click(app, src, 480, 250)                           # release
    assert not v.panning
    click_label(app, src, "Zoom -"); click_label(app, src, "Reset")
    assert v.zoom == 1.0
    n = v.idx
    click_label(app, src, "Next >"); assert v.idx != n or len(v.paths) == 1


def test_objects_drag_drop():
    app, src = make_app()
    click_label(app, src, "Objects"); click_label(app, src, "Drag")
    sc = app.ctx.scene
    sq = [s for s in sc.shapes if s.kind == "square"][0]
    click(app, src, sq.x, sq.y)
    assert sc.grabbed is sq
    zone = [z for z in sc.zones if z.kind == "square"][0]
    zx, zy = (zone.rect[0] + zone.rect[2]) / 2, (zone.rect[1] + zone.rect[3]) / 2
    for t in np.linspace(0, 1, 8):
        point(app, src, sq.x * (1 - t) + zx * t, sq.y * (1 - t) + zy * t)
    click(app, src, zx, zy)
    assert sc.grabbed is None and abs(sq.x - zx) < 1
    app.frame(); shot(app, "06_objects")
    c = [s for s in sc.shapes if s.kind == "circle"][0]
    click(app, src, c.x, c.y)
    click(app, src, c.x, c.y, RIGHT)                    # cancel -> back home
    assert sc.grabbed is None


def test_lesson_pages_and_annotation():
    app, src = make_app()
    click_label(app, src, "Lesson"); click_label(app, src, "Start")
    L = app.ctx.lesson
    assert L.idx == 0
    app.frame(); shot(app, "07_lesson_text")
    click_label(app, src, "Next >"); assert L.idx == 1
    app.frame(); shot(app, "08_lesson_image")
    click(app, src, 480, 250)                           # click on page (annotate off) -> next page
    assert L.idx == 2
    click(app, src, 480, 250, RIGHT); assert L.idx == 1   # RIGHT = previous
    click_label(app, src, "Next >"); click_label(app, src, "Next >"); click_label(app, src, "Next >")
    assert L.page.type == "draw" and app.nav.current.annotate
    click(app, src, 300, 260)
    for i in range(20):
        point(app, src, 300 + i * 12, 260 + 40 * np.sin(i / 3))
    click(app, src, 540, 260)
    assert app.nav.current.ink(app.ctx).mask.sum() > 200
    app.frame(); shot(app, "09_lesson_draw")


def test_home_reset_buttons_and_settings_toggle():
    app, src = make_app()
    click_label(app, src, "Draw"); click_label(app, src, "Free drawing")
    click(app, src, 400, 200)
    for i in range(10):
        point(app, src, 400 + i * 10, 200)
    click(app, src, 520, 200)
    hb = app.hud.btn_home.rect
    click(app, src, (hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2)       # HUD Home
    assert type(app.nav.current).__name__ == "MenuScreen" and not app.nav.current.path
    assert app.ctx.drawing.mask.sum() > 0                            # Home keeps the drawing
    rb = app.hud.btn_reset.rect
    click(app, src, (rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2)       # HUD Reset
    assert app.ctx.drawing.mask.sum() == 0
    click_label(app, src, "Settings")
    before = app.ctx.show_trail
    click_label(app, src, "Pointer trail")
    assert app.ctx.show_trail != before
    app.frame(); shot(app, "10_settings")
    click_label(app, src, "Quit"); assert app.ctx.quit


def test_pointer_lost_click_is_ignored():
    app, src = make_app()
    src.pos = None
    app.frame(remote_buttons=[LEFT])
    assert app.nav.current.path == []                   # nothing happened, no crash


def test_calibration_flow_with_synthetic_camera():
    from smartboard.vision.camera import SyntheticCamera
    from smartboard.vision.calibration import compute_homography
    from smartboard.vision.pointer_source import VisionPointerSource
    W, H = 960, 540
    cfg = Config()
    cfg.display.width, cfg.display.height = W, H
    cfg.assets_dir = os.path.join(ROOT, "assets")
    cfg.calibration.file = os.path.join(os.environ.get("TMPDIR", "/tmp"), "swb_test_calib.json")
    board = np.array([[0, 0], [W, 0], [W, H], [0, H]], float)
    cam_quad = np.array([[210, 120], [1050, 80], [1120, 640], [140, 600]], float)
    Hbc = compute_homography(board, cam_quad)
    dot = {"p": None}
    cam = SyntheticCamera(1280, 720, (W, H), Hbc, lambda: dot["p"])
    calib = Calibration(W, H)
    src = VisionPointerSource(cfg, cam, calib)
    app = App(cfg, src, calib)                           # not calibrated -> opens calibration screen
    scr = app.nav.current
    assert type(scr).__name__ == "CalibrationScreen" and scr.state == "collect"
    for t in scr.targets:                                # operator aims at each target and presses NEXT
        dot["p"] = tuple(t)
        for _ in range(10):
            app.frame()
        app.frame(remote_buttons=[LEFT])
    assert scr.state == "validate" and calib.calibrated
    app.frame(); shot(app, "11_calibration_validate")
    for t in scr.val_targets:
        dot["p"] = tuple(t)
        src.track_board.reset(); src.track_cam.reset()
        for _ in range(10):
            app.frame()
        app.frame(remote_buttons=[LEFT])
    assert scr.state == "result" and scr.mean_err < 5, scr.mean_err
    app.frame(); shot(app, "12_calibration_result")
    app.frame(remote_buttons=[LEFT])                     # accept + save
    assert os.path.exists(cfg.calibration.file)
    assert type(app.nav.current).__name__ == "MenuScreen"
    # saved calibration reloads
    c2 = Calibration(W, H)
    assert c2.load(cfg.calibration.file)
    assert np.allclose(c2.H, calib.H, atol=1e-6)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
