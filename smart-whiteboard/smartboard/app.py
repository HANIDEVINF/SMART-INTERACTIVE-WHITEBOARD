"""Application: wires camera/pointer, remote, screens and rendering together.

Main interaction pipeline (see project figure):

    camera frame -> red-dot detection -> image->board mapping   (PointerSource)
        -> remote key event (RemoteInput) -> click at current pointer position
        -> screen logic (Navigator / Screen.on_click)  -> render -> projector
"""
from __future__ import annotations

import time
from typing import List, Optional

import numpy as np

from .graphics.widgets import hit

from .config import Config
from .context import AppContext
from .events import ClickEvent, LEFT, RIGHT, PointerSample
from .graphics.canvas import Canvas
from .graphics import theme
from .graphics.hud import Hud
from .remote.remote_input import RemoteInput
from .screens.base import Screen
from .screens.calibration import CalibrationScreen
from .screens.draw import DrawScreen
from .screens.images import ImageScreen
from .screens.lesson import LessonScreen
from .screens.menu import MenuScreen
from .screens.menu_tree import build_menu
from .screens.navigator import Navigator
from .screens.objects import ObjectsScreen
from .screens.pointer_test import PointerTestScreen
from .screens.skin_learn import SkinLearnScreen
from .screens.timer import TimerScreen
from .vision.calibration import Calibration
from .vision.debug_view import build_debug_image

ESC = 27
HOTKEYS = {ord("q"): "quit", ESC: "quit", ord("h"): "home", ord("r"): "reset",
           ord("c"): "calibrate", ord("d"): "debug"}


class App:
    def __init__(self, cfg: Config, source, calib: Calibration, mouse_mode: bool = False):
        self.cfg = cfg
        self.source = source
        self.calib = calib
        self.mouse_mode = mouse_mode
        scale = min(cfg.display.width / 1920.0, cfg.display.height / 1080.0)
        self.hud = Hud(cfg.display.width, cfg.display.height, scale,
                       on_home=lambda c: c.nav.home(), on_reset=lambda c: c.nav.reset())
        self.ctx = AppContext(cfg, calib, source, self.hud, mouse_mode)
        self.canvas = Canvas(cfg.display.width, cfg.display.height)
        self.remote = RemoteInput(cfg.remote)
        factories = {
            "menu": lambda: MenuScreen(build_menu()),
            "draw": DrawScreen, "images": ImageScreen, "objects": ObjectsScreen,
            "lesson": LessonScreen, "calibration": CalibrationScreen,
            "timer": TimerScreen, "pointer_test": PointerTestScreen,
            "skin_learn": SkinLearnScreen,
        }
        self.nav = Navigator(self.ctx, factories, root="menu")
        if not calib.calibrated and not mouse_mode:
            self.nav.push("calibration")          # first start: calibrate before anything else
        self._t_last = time.perf_counter()
        self._fps = 0.0
        self.last_click: Optional[str] = None
        self._prev = None                  # previous frame, for the cross-fade between screens
        self._cur_screen = self.nav.current
        self._fade = 1.0
        self._dwell_t = 0.0
        self._dwell_anchor = None
        self._dwell_lock = None

    # ------------------------------------------------------------------ one frame
    def frame(self, extra_clicks: Optional[List[ClickEvent]] = None,
              remote_buttons: Optional[List[str]] = None):
        """Process one iteration (no GUI calls) and return the canvas image.

        ``extra_clicks`` / ``remote_buttons`` let tests inject events."""
        now = time.perf_counter()
        dt = max(now - self._t_last, 1e-3)
        self._t_last = now
        self._fps = 0.9 * self._fps + 0.1 / dt if self._fps else 1.0 / dt

        ctx = self.ctx
        ctx.pointer = self.source.update()
        pos = ctx.pointer.board

        clicks = list(self.source.pop_clicks()) + list(extra_clicks or [])
        buttons = list(remote_buttons or []) + self.remote.drain()
        for b in buttons:
            self.hud.flash_key(b)
            cp = self._click_pos()
            if cp is None:
                ctx.toast("Pointer not detected - click ignored", 1.5)
            else:
                clicks.append(ClickEvent(b, cp, "remote"))
        for ev in clicks:
            self._dispatch(ev)

        scr = self.nav.current
        self._dwell(scr, pos, dt)
        scr.update(ctx, pos, dt)
        self.hud.update(dt)

        scr.render(ctx, self.canvas, pos)
        ctx.overlays.apply(self.canvas.img, pos, ctx.scale)        # spotlight / magnifier on ANY screen
        if scr.show_bar:
            self.hud.draw_bar(self.canvas, scr.title, pos, scr.status(ctx), ctx.pointer,
                              getattr(self.source, "fps", 0.0) or self._fps)
        self.hud.draw_toast(self.canvas)
        self.hud.draw_cursor(self.canvas, ctx.pointer, ctx.show_trail)
        return self._transition(dt)

    def _dwell(self, scr: Screen, pos, dt: float):
        """Optional hold-to-click: the pointer rests on a button for ``dwell_click_s`` -> left click.
        After a dwell click the pointer must leave the button before the next one (no click storms)."""
        self.hud.dwell = 0.0
        if not self.ctx.dwell_click or pos is None or not self.ctx.pointer.tracked or scr.show_bar is False:
            self._dwell_t, self._dwell_anchor = 0.0, None
            return
        btn = self.hud.hit(pos) or hit(scr.buttons, pos)
        if btn is None or btn is self._dwell_lock and btn.contains(pos[0], pos[1], 20):
            if btn is None:
                self._dwell_lock = None
            self._dwell_t, self._dwell_anchor = 0.0, None
            return
        if self._dwell_anchor is None or np.hypot(pos[0] - self._dwell_anchor[0], pos[1] - self._dwell_anchor[1]) > 40:
            self._dwell_anchor, self._dwell_t = pos, 0.0
        self._dwell_t += dt
        self.hud.dwell = self._dwell_t / self.cfg.display.dwell_click_s
        if self._dwell_t >= self.cfg.display.dwell_click_s:
            self._dwell_t, self._dwell_anchor, self._dwell_lock = 0.0, None, btn
            self._dispatch(ClickEvent(LEFT, pos, "dwell"))

    def _transition(self, dt: float):
        """Short cross-fade when the screen changes (out = prev (1-t) + cur t)."""
        img = self.canvas.img
        if not self.cfg.display.ui_transitions:
            return img
        if self.nav.current is not self._cur_screen:
            self._cur_screen, self._fade = self.nav.current, 0.0
        if self._fade < 1.0 and self._prev is not None:
            self._fade = min(1.0, self._fade + dt / 0.18)
            t = int(255 * self._fade)
            out = (self._prev.astype(np.uint16) * (255 - t) + img.astype(np.uint16) * t + 127) // 255
            img[:] = out.astype(np.uint8)
        if self._prev is None:
            self._prev = img.copy()
        else:
            np.copyto(self._prev, img)
        return img

    def _click_pos(self):
        """Where a remote click happens: the pointer in board coordinates.
        Before the first calibration no board position exists, so the click
        carries the camera position (only the calibration screen uses it)."""
        p = self.ctx.pointer
        if p.board is not None:
            c = self.cfg.tracking
            return self.source.click_position(c.click_lookback_s, c.click_lookback_max_px) or p.board
        if not self.calib.calibrated:
            return p.cam if p.tracked else None
        return None

    def _status(self, scr: Screen) -> str:
        s = scr.status(self.ctx)
        p = self.ctx.pointer
        state = "tracking" if p.tracked else ("holding" if p.board else "no pointer")
        return f"{s}   |   {self._fps:.0f} fps  {state}"

    def _dispatch(self, ev: ClickEvent):
        ctx = self.ctx
        self.last_click = f"{ev.button} @ ({ev.pos[0]:.0f},{ev.pos[1]:.0f}) from {ev.source}"
        self.ctx.last_click = self.last_click
        if self.calib.calibrated:
            self.hud.flash_click(ev.pos, ev.button == LEFT)
        scr = self.nav.current
        if ev.button == LEFT and scr.show_bar:
            b = self.hud.hit(ev.pos)
            if b is not None:
                b.activate(ctx)
                return
        scr.on_click(ctx, ev)

    # --------------------------------------------------------------------- GUI loop
    def run(self):
        import cv2
        d = self.cfg.display
        cv2.namedWindow(d.window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(d.window_name, d.window_x, d.window_y)
        if d.fullscreen:
            cv2.setWindowProperty(d.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        else:
            cv2.resizeWindow(d.window_name, d.width, d.height)
        if self.mouse_mode:
            self.source.attach(d.window_name)
        dbg_name = "Camera (operator view)"
        if not self.mouse_mode:
            cv2.namedWindow(dbg_name, cv2.WINDOW_NORMAL)
            self._dbg_scale = 1.0
            cv2.setMouseCallback(dbg_name, self._on_debug_mouse)
        self.remote.start()
        if self.cfg.tracking.threaded and hasattr(self.source, "start"):
            self.source.start()           # camera + detection in their own thread
        try:
            while not self.ctx.quit:
                img = self.frame()
                cv2.imshow(d.window_name, img)
                if not self.mouse_mode and self.ctx.show_debug:
                    self._show_debug(cv2, dbg_name)
                key = cv2.waitKeyEx(1)
                if key >= 0:
                    self._on_key(key)
        finally:
            self.remote.stop()
            self.source.release()
            cv2.destroyAllWindows()

    def _on_key(self, key: int):
        self.remote.last_code = key
        btn = self.remote.from_key_code(key)
        if btn is not None:                     # remote button (checked first)
            self.hud.flash_key(btn)
            pos = self._click_pos()
            if pos is None:
                self.ctx.toast("Pointer not detected - click ignored", 1.5)
            else:
                self._dispatch(ClickEvent(btn, pos, f"key {key}"))
            return
        action = HOTKEYS.get(key & 0xFF) if key < 256 else None
        if action == "quit":
            self.ctx.quit = True
        elif action == "home":
            self.nav.home()
        elif action == "reset":
            self.nav.reset()
        elif action == "calibrate" and not self.mouse_mode:
            self.nav.push("calibration")
        elif action == "debug":
            self.ctx.show_debug = not self.ctx.show_debug

    def _show_debug(self, cv2, name):
        s = self.ctx.pointer
        status = (f"dot cam=({s.cam[0]:.0f},{s.cam[1]:.0f}) " if s.cam else "dot: none ") + \
                 f"| last click: {self.last_click or '-'} | last key: {self.remote.last_code}"
        img, self._dbg_scale = build_debug_image(self.source.last_frame, self.source.last_detection,
                                                 self.calib, s, status)
        cv2.imshow(name, img)

    def _on_debug_mouse(self, event, x, y, flags, param):
        import cv2
        if event == cv2.EVENT_LBUTTONDOWN and getattr(self, "_dbg_scale", 0):
            self.ctx.manual_cam_click = (x / self._dbg_scale, y / self._dbg_scale)
