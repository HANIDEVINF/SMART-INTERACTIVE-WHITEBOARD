"""Render every screen to PNG files (for the report / README) and print the frame times.

    python tools/screenshots.py [output_dir]
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cv2
import numpy as np

from smartboard.app import App
from smartboard.config import load_config
from smartboard.vision.calibration import Calibration
from smartboard.vision.pointer_source import MousePointerSource

out = sys.argv[1] if len(sys.argv) > 1 else "screenshots"
os.makedirs(out, exist_ok=True)
cfg = load_config("config.json")
cfg.display.ui_transitions = False
calib = Calibration(cfg.display.width, cfg.display.height)
calib.fit([(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 0), (1, 0), (1, 1), (0, 1)])
src = MousePointerSource()
app = App(cfg, src, calib, mouse_mode=True)


def shot(name, pos=(900.0, 600.0)):
    src.pos = pos
    for _ in range(4):
        img = app.frame()
    t = time.perf_counter()
    for _ in range(8):
        img = app.frame()
    print("%-14s %5.1f ms/frame" % (name, (time.perf_counter() - t) / 8 * 1000))
    cv2.imwrite(os.path.join(out, name + ".png"), img)


shot("menu")
app.nav.reset() if False else None
d = app.ctx.drawing
d.lower((700, 300))
for i in range(120):
    d.move((700 + i * 8, 300 + 90 * np.sin(i / 8)))
d.lift()
d.set_color(1); d.set_tool("rect"); d.toggle_pen((800, 600)); d.move((1200, 800)); d.toggle_pen((1200, 800))
d.set_color(4); d.set_tool("arrow"); d.toggle_pen((1300, 300)); d.move((1700, 420)); d.toggle_pen((1700, 420))
d.set_tool("pen")
for name in ("draw", "images", "objects", "lesson", "timer", "pointer_test"):
    app.nav.push(name)
    shot(name, (1000.0, 700.0))
    if name == "lesson":
        app.ctx.lesson.goto_first("quiz")
        app.nav.back(); app.nav.push("lesson")
        shot("lesson_quiz", (900.0, 560.0))
    app.nav.back()
app.ctx.overlays.spotlight = True
shot("overlay_spotlight", (900.0, 600.0))
app.ctx.overlays.spotlight = False
app.ctx.overlays.magnifier = True
shot("overlay_magnifier", (700.0, 330.0))
app.ctx.overlays.magnifier = False
