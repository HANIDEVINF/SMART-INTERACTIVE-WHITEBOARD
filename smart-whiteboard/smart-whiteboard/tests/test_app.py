"""Headless end-to-end tests of the whole application (no window, no camera).

The mouse pointer source stands in for the vision pipeline; clicks are
injected exactly like remote events.  Set SWB_SHOTS=<dir> to save screenshots.
"""
import os
import sys
import time

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from smartboard.app import App
from smartboard.config import Config
from smartboard.events import LEFT, RIGHT, ClickEvent
from smartboard.vision.calibration import Calibration
from smartboard.vision.pointer_source import MousePointerSource, VisionPointerSource

SHOTS = os.environ.get("SWB_SHOTS")


def make_app(w=960, h=540):
    cfg = Config()
    cfg.display.ui_transitions = False
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
    assert type(app.nav.current).__name__ == "MenuScreen"
    click_label(app, src, "Draw")                        # submenu opens
    assert app.nav.current.path and "Free drawing" in [b.text() for b in app.nav.current.buttons]
    click_label(app, src, "Back")
    assert not app.nav.current.path
    click_label(app, src, "Draw")
    click_label(app, src, "Free drawing")
    assert type(app.nav.current).__name__ == "DrawScreen"
    click(app, src, 400, 300, RIGHT)                     # PREV = back
    assert type(app.nav.current).__name__ == "MenuScreen"
    shot(app, "menu")


def test_drawing_colours_sizes_tools_undo_clear():
    app, src = make_app()
    app.nav.push("draw")
    d = app.ctx.drawing
    click_label(app, src, "Cyan");  assert d.color == app.ctx.drawing.color and d.color_idx == 1
    click_label(app, src, "Thick"); assert d.size_idx == 2
    click(app, src, 500, 300)                             # pen down
    assert d.pen_down
    for x in range(500, 700, 10):
        point(app, src, x, 300 + (x - 500) // 5)
    click(app, src, 700, 340)                             # pen up
    assert not d.pen_down and d.A.sum() > 0 and len(d.strokes) == 1
    ink_before = int(d.A.sum())
    click_label(app, src, "Box")                          # shape tool: two clicks
    click(app, src, 450, 200); point(app, src, 650, 250); click(app, src, 650, 250)
    assert len(d.strokes) == 2 and d.A.sum() > ink_before
    click_label(app, src, "Undo");  assert len(d.strokes) == 1
    click_label(app, src, "Redo");  assert len(d.strokes) == 2
    click_label(app, src, "Eraser")
    n = int(d.A.sum())
    click(app, src, 450, 200); point(app, src, 500, 200); click(app, src, 500, 200)
    assert d.A.sum() < n                                  # eraser removed ink
    click_label(app, src, "Clear");  assert d.A.sum() == 0 and not d.strokes
    shot(app, "draw")


def test_ink_is_antialiased():
    app, src = make_app()
    d = app.ctx.drawing
    d.lower((100, 100)); d.move((300, 180)); d.lift()
    vals = np.unique(d.A)
    assert len(vals) > 5 and vals.max() == 255            # soft edge pixels exist


def test_pen_lifts_over_toolbar():
    app, src = make_app()
    app.nav.push("draw")
    d = app.ctx.drawing
    click(app, src, 500, 300); assert d.pen_down
    point(app, src, 40, 300)                              # pointer enters the toolbar
    assert not d.pen_down


def test_image_zoom_pan_reset():
    app, src = make_app()
    app.nav.push("images")
    v = app.ctx.viewer
    z0 = v.zoom
    click_label(app, src, "Zoom +"); click_label(app, src, "Zoom +")
    assert v.zoom > z0 * 1.4
    click(app, src, 480, 250)                             # grab the image
    assert v.panning
    c0 = v.center
    for i in range(10):
        point(app, src, 480 - i * 10, 250)
    click(app, src, 380, 250)                             # release
    assert not v.panning and v.center != c0            # the pan moved the view
    click_label(app, src, "Original")
    assert abs(v.zoom - z0) < 1e-6
    click_label(app, src, "Next")
    shot(app, "images")


def test_objects_drag_drop():
    app, src = make_app()
    app.nav.push("objects")
    sc = app.ctx.scene
    sh = sc.shapes[0]
    zone = next(z for z in sc.zones if z.kind == sh.kind)
    click(app, src, sh.x, sh.y); assert sc.grabbed is sh
    zx, zy = (zone.rect[0] + zone.rect[2]) / 2, (zone.rect[1] + zone.rect[3]) / 2
    for t in np.linspace(0, 1, 8):
        point(app, src, sh.x + (zx - sh.x) * t, sh.y + (zy - sh.y) * t)
    click(app, src, zx, zy)
    assert sc.grabbed is None and zone.rect[0] <= sh.x < zone.rect[2]
    shot(app, "objects")


def test_lesson_pages_annotation_and_quiz():
    app, src = make_app()
    app.nav.push("lesson")
    L = app.ctx.lesson
    assert L.idx == 0
    click_label(app, src, "Next"); assert L.idx == 1
    click_label(app, src, "Prev"); assert L.idx == 0
    click_label(app, src, "Annotate")
    click(app, src, 300, 250)
    for x in range(300, 400, 10):
        point(app, src, x, 250)
    click(app, src, 400, 250)
    assert app.nav.current.ink(app.ctx).A.sum() > 0
    # quiz: wrong then correct answers are scored once
    assert L.goto_first("quiz")
    app.nav.back(); app.nav.push("lesson")
    scr = app.nav.current
    assert [b.text()[0] for b in scr.buttons if b.text()[:2] in ("A ", "B ", "C ")] == ["A", "B", "C"]
    click_label(app, src, "planar homography")
    assert L.chosen[L.idx] == L.page.answer and L.score[0] == 1
    click_label(app, src, "rotation only")                # second answer ignored
    assert L.score[0] == 1
    shot(app, "quiz")


def test_timer():
    app, src = make_app()
    app.nav.push("timer")
    T = app.ctx.timer
    click_label(app, src, "5 min"); assert abs(T.left - 300) < 1
    click_label(app, src, "+ 1 min"); assert T.total == 360
    click_label(app, src, "Start"); assert T.running
    click_label(app, src, "Pause"); assert not T.running
    T.set(1); T.toggle(); T.left = 0.0; T.tick()
    app.frame(); assert T.finished
    shot(app, "timer")


def test_pointer_test_accuracy():
    app, src = make_app()
    app.nav.push("pointer_test")
    scr = app.nav.current
    for i in range(len(scr.targets)):
        tx, ty = scr._tpos(app.ctx, i)
        click(app, src, tx + 3, ty - 4)                   # 5 px off
    assert len(scr.errors) == 5 and all(abs(e - 5.0) < 0.01 for e in scr.errors)
    shot(app, "pointer_test")


def test_overlays_work_on_every_screen():
    app, src = make_app()
    o = app.ctx.overlays
    click_label(app, src, "Tools")
    click_label(app, src, "Spotlight"); assert o.spotlight
    click_label(app, src, "Magnifier"); assert o.magnifier
    point(app, src, 300, 200)
    img = app.frame().copy()
    assert img.mean() < 90                                 # dimmed
    for name in ("draw", "images", "lesson"):
        app.nav.push(name); point(app, src, 480, 270); app.nav.back()
    shot(app, "overlays")
    click_label(app, src, "Spotlight"); assert not o.spotlight


def test_home_reset_buttons_and_settings_toggle():
    app, src = make_app()
    app.nav.push("draw")
    d = app.ctx.drawing
    click(app, src, 500, 300); point(app, src, 600, 320); click(app, src, 600, 320)
    assert d.A.sum() > 0
    b = app.hud.btn_home; x0, y0, x1, y1 = b.rect
    click(app, src, (x0 + x1) / 2, (y0 + y1) / 2)
    assert type(app.nav.current).__name__ == "MenuScreen"
    assert app.ctx.drawing.A.sum() > 0                     # Home keeps the work
    b = app.hud.btn_reset; x0, y0, x1, y1 = b.rect
    click(app, src, (x0 + x1) / 2, (y0 + y1) / 2)
    assert app.ctx.drawing.A.sum() == 0                    # Reset restores everything
    click_label(app, src, "Settings")
    t0 = app.ctx.show_trail
    click_label(app, src, "Pointer trail")
    assert app.ctx.show_trail != t0
    click_label(app, src, "sensitivity")
    click(app, src, 400, 300, RIGHT)
    assert not app.nav.current.path


def test_pointer_lost_click_is_ignored():
    app, src = make_app()
    src.pos = None
    app.frame(remote_buttons=[LEFT])
    assert type(app.nav.current).__name__ == "MenuScreen"


def test_remote_keys_light_the_hud():
    app, src = make_app()
    point(app, src, 400, 300)
    app.frame(remote_buttons=[RIGHT])
    assert app.hud.key_flash["right"] < 0.5 and app.hud.key_flash["left"] > 0.5
    assert "right" in app.ctx.last_click


def test_no_red_anywhere_in_the_interface():
    """The projector must never create a red dot: run the detector on every rendered screen."""
    from smartboard.vision.detector import RedDotDetector
    app, src = make_app()
    det = RedDotDetector(app.cfg.detection)
    names = ["menu", "draw", "images", "objects", "lesson", "timer", "pointer_test"]
    app.ctx.overlays.spotlight = True
    for n in names:
        if n != "menu":
            app.nav.push(n)
        for pos in ((300, 200), (700, 400)):
            point(app, src, *pos)
            app.ctx.hud.flash_click(pos, True); app.ctx.hud.flash_click(pos, False)
            img = app.frame()
            assert det.detect(img) is None, f"false red dot on screen {n}"
        if n != "menu":
            app.nav.back()
    app.ctx.overlays.spotlight = False
    app.nav.push("lesson"); app.ctx.lesson.goto_first("quiz"); app.nav.back(); app.nav.push("lesson")
    click_label(app, src, "rotation only")                # wrong answer -> amber highlight must not look red
    assert det.detect(app.frame()) is None


def synthetic_setup(w, h, fps=0.0, k1=0.12, core=True, threaded=False):
    from smartboard.vision.calibration import apply_homography, compute_homography
    from smartboard.vision.camera import SyntheticCamera
    cfg = Config()
    cfg.display.ui_transitions = False
    cfg.display.width, cfg.display.height = w, h
    cfg.assets_dir = os.path.join(ROOT, "assets")
    cfg.calibration.dwell_s = 0.0
    Hbc = compute_homography(np.array([[0, 0], [w, 0], [w, h], [0, h]], float),
                             np.array([[210, 120], [1050, 80], [1120, 640], [140, 600]], float))
    lens = Calibration(w, h); lens.set_camera_size(1280, 720); lens.k1 = k1
    state = {"p": None}
    cam = SyntheticCamera(1280, 720, (w, h), Hbc, lambda: state["p"], fps=fps, lens=lens, core=core)
    calib = Calibration(w, h)
    src = VisionPointerSource(cfg, cam, calib)
    return cfg, cam, calib, src, state


def test_calibration_flow_with_distorted_lens():
    w, h = 960, 540
    cfg, cam, calib, src, state = synthetic_setup(w, h)
    app = App(cfg, src, calib)
    scr = app.nav.current
    assert type(scr).__name__ == "CalibrationScreen" and len(scr.targets) == 9
    app.frame(remote_buttons=[LEFT])                       # no dot: ignored
    assert scr.cam_pts == []
    for t in scr.targets:
        state["p"] = tuple(t)
        for _ in range(10):
            app.frame()
        app.frame(remote_buttons=[LEFT])
    assert scr.state == "validate" and calib.calibrated
    assert abs(calib.k1 - 0.12) < 0.03, calib.k1           # lens distortion recovered
    for t in scr.val_targets:
        state["p"] = tuple(t)
        for _ in range(12):
            app.frame()
        app.frame(remote_buttons=[LEFT])
    assert scr.state == "result" and scr.mean_err < 3.0, scr.mean_err
    app.frame(remote_buttons=[LEFT])                       # accept + save
    assert type(app.nav.current).__name__ == "MenuScreen"
    shot(app, "after_calibration")


def test_calibration_dwell_autocapture():
    w, h = 960, 540
    cfg, cam, calib, src, state = synthetic_setup(w, h)
    cfg.calibration.dwell_s = 0.15
    app = App(cfg, src, calib)
    scr = app.nav.current
    t0 = time.time()
    for t in scr.targets[:3]:
        state["p"] = tuple(t)
        n0 = len(scr.cam_pts)
        while len(scr.cam_pts) == n0 and time.time() - t0 < 20:
            app.frame(); time.sleep(0.01)
    assert len(scr.cam_pts) == 3                           # captured with no remote click at all


def test_click_stabilisation_uses_position_before_the_press():
    cfg, cam, calib, src, state = synthetic_setup(960, 540)
    from smartboard.events import PointerSample
    now = time.perf_counter()
    src.history.extend([(now - 0.30, (400.0, 300.0)), (now - 0.10, (500.0, 300.0)), (now - 0.01, (512.0, 306.0))])
    src.sample = PointerSample((512.0, 306.0), (0, 0), True, 0)
    assert src.click_position(0.10, 120) == (500.0, 300.0)         # the hand jerk of the press is ignored
    src.history.clear(); src.history.append((now - 0.10, (100.0, 100.0)))
    assert src.click_position(0.10, 120) == (512.0, 306.0)         # fast deliberate move: keep the current one
    assert src.click_position(0.0, 120) == (512.0, 306.0)


def test_threaded_tracking_follows_the_dot():
    w, h = 960, 540
    cfg, cam, calib, src, state = synthetic_setup(w, h, fps=60)
    from smartboard.vision.calibration import calibration_targets
    tg = calibration_targets(w, h, 0.06, 9)
    src.start()
    cp = []
    for t in tg:
        state["p"] = tuple(t)
        time.sleep(0.35)
        cp.append(src.sample.cam)
    calib.fit(cp, tg, True); src.refresh_roi()
    errs = []
    for p in ((200, 150), (700, 400), (480, 270), (100, 480)):
        state["p"] = p
        time.sleep(0.6)
        s = src.update()
        assert s.tracked
        errs.append(np.hypot(s.board[0] - p[0], s.board[1] - p[1]))
    src.release()
    assert max(errs) < 3.0, errs
    assert src.fps > 8                                     # camera is throttled to 60 fps; slow CI machines are fine


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print("ok ", name)
