"""Shared application state handed to every screen (no globals)."""
from __future__ import annotations

import os
from typing import Optional

from .config import Config
from .events import PointerSample
from .features.drawing import DrawingCanvas
from .features.image_viewer import ImageViewer
from .features.lesson import Lesson
from .features.objects import Scene
from .features.overlays import Overlays
from .features.timer import Countdown
from .vision.calibration import Calibration


class AppContext:
    def __init__(self, cfg: Config, calib: Calibration, source, hud, mouse_mode: bool = False):
        self.cfg = cfg
        self.calib = calib
        self.source = source
        self.hud = hud
        self.mouse_mode = mouse_mode
        self.w, self.h = cfg.display.width, cfg.display.height
        self.scale = min(self.w / 1920.0, self.h / 1080.0)
        self.top = hud.bar_h                       # first usable row under the top bar
        self.pointer = PointerSample()
        self.nav = None                            # set by the Navigator
        self.quit = False
        self.show_trail = cfg.show_trail
        self.show_debug = cfg.display.show_debug
        self.dwell_click = cfg.display.dwell_click       # hold still on a button = click (no remote needed)
        self.cfg_path = None                             # set by main.py: where learned settings are saved
        self.manual_cam_click: Optional[tuple] = None   # click in the operator's camera window
        self.calib_path = cfg.calibration.file
        self.overlays = Overlays()                 # spotlight / magnifier (survive Reset: they are tools)
        self.last_click = ""                       # text of the last click (HUD / camera window)
        self.build_features()

    # -- features (state that survives navigation) -------------------------------------------
    def build_features(self):
        a = self.cfg.assets_dir
        self.drawing = DrawingCanvas(self.w, self.h)
        self.board_idx = 0                         # 0 dark | 1 light | 2 grid
        self.viewer = ImageViewer(os.path.join(a, "images"))
        self.scene = Scene(self.w, self.h, self.top)
        self.lesson = Lesson(os.path.join(a, "lesson", "lesson.json"))
        self.lesson_ink = {}                       # page index -> DrawingCanvas (annotations)
        self.timer = Countdown(300)

    def toast(self, msg: str, seconds: float = 2.5):
        self.hud.toast(msg, seconds)

    def sc(self, v: float) -> int:
        """Scale a design value (given for 1920x1080) to the real resolution."""
        return int(round(v * self.scale))

    # -- drawing board ---------------------------------------------------------------------------
    def board_background(self):
        """Background of the drawing board (0 dark | 1 light | 2 grid), cached."""
        import numpy as np
        from .graphics import theme
        key = (self.board_idx, self.w, self.h)
        if getattr(self, "_board_key", None) != key:
            if self.board_idx == 1:
                img = np.empty((self.h, self.w, 3), np.uint8)
                img[:] = theme.BOARD_LIGHT
            elif self.board_idx == 2:
                img = theme.make_grid_board(self.w, self.h, theme.rgb(14, 20, 44))
            else:
                img = theme.make_background(self.w, self.h)
            self._board_img, self._board_key = img, key
        return self._board_img

    def save_snapshot(self) -> str:
        """Write the current drawing (board + ink, no interface) to ./snapshots/*.png."""
        import os
        import time
        import cv2                     # image file encoding = justified use of OpenCV
        img = self.board_background().copy()
        self.drawing.render_onto(img)
        os.makedirs("snapshots", exist_ok=True)
        path = os.path.join("snapshots", time.strftime("board_%Y%m%d_%H%M%S.png"))
        cv2.imwrite(path, img)
        return path

    @property
    def pointer_name(self) -> str:
        return "finger" if self.cfg.detection.mode == "hand" else "red dot"
