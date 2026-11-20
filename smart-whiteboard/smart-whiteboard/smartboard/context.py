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
        self.manual_cam_click: Optional[tuple] = None   # click in the operator's camera window
        self.calib_path = cfg.calibration.file
        self.build_features()

    # -- features (state that survives navigation) -------------------------------------------
    def build_features(self):
        a = self.cfg.assets_dir
        self.drawing = DrawingCanvas(self.w, self.h)
        self.viewer = ImageViewer(os.path.join(a, "images"))
        self.scene = Scene(self.w, self.h, self.top)
        self.lesson = Lesson(os.path.join(a, "lesson", "lesson.json"))
        self.lesson_ink = {}                       # page index -> DrawingCanvas (annotations)

    def toast(self, msg: str, seconds: float = 2.5):
        self.hud.toast(msg, seconds)

    def sc(self, v: float) -> int:
        """Scale a design value (given for 1920x1080) to the real resolution."""
        return int(round(v * self.scale))
