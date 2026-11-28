#!/usr/bin/env python3
"""Smart Interactive Whiteboard - entry point.

    python main.py                  real setup: camera + red dot + remote
    python main.py --mouse          develop the UI without hardware (mouse = pointer + remote)
    python main.py --synthetic      full vision pipeline on a simulated camera (self-test / demo)
    python main.py --windowed       do not use fullscreen
"""
import argparse
import math
import os
import sys
import time

import numpy as np

from smartboard.app import App
from smartboard.config import load_config
from smartboard.vision.calibration import (Calibration, apply_homography, calibration_targets,
                                           compute_homography)
from smartboard.vision.pointer_source import MousePointerSource, VisionPointerSource


def parse_args():
    ap = argparse.ArgumentParser(description="Smart Interactive Whiteboard")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--mouse", action="store_true", help="mouse simulates pointer and remote buttons")
    ap.add_argument("--synthetic", action="store_true", help="simulated camera with a moving red dot")
    ap.add_argument("--windowed", action="store_true")
    ap.add_argument("--camera", type=int, help="camera index (overrides config)")
    ap.add_argument("--source", help="phone / IP camera stream URL, e.g. http://192.168.1.20:8080/video")
    ap.add_argument("--hand", action="store_true", help="pointer = your fingertip (skin detection) instead of a red dot")
    ap.add_argument("--reddot", action="store_true", help="pointer = red dot (default from config.json)")
    ap.add_argument("--recalibrate", action="store_true", help="ignore the saved calibration")
    return ap.parse_args()


def build_synthetic(cfg, calib):
    """Simulated camera looking obliquely at the board through a slightly distorted lens;
    the dot (with a saturated white core, like a strong laser) follows a Lissajous curve."""
    from smartboard.vision.camera import SyntheticCamera
    W, H = cfg.display.width, cfg.display.height
    board = np.array([[0, 0], [W, 0], [W, H], [0, H]], float)
    cam_quad = np.array([[210, 120], [1050, 80], [1120, 640], [140, 600]], float)
    Hbc = compute_homography(board, cam_quad)
    lens = Calibration(W, H)
    lens.set_camera_size(1280, 720)
    lens.k1 = 0.10
    t0 = time.perf_counter()

    def dot():
        t = time.perf_counter() - t0
        return (W * (0.5 + 0.35 * math.sin(0.7 * t)), H * (0.5 + 0.3 * math.sin(1.1 * t + 1)))

    cam = SyntheticCamera(1280, 720, (W, H), Hbc, dot, fps=30, lens=lens, core=True,
                          hand=(cfg.detection.mode == "hand"))
    # pre-calibrate: where the calibration targets appear in the simulated camera
    tg = calibration_targets(W, H, cfg.calibration.target_margin, 9)
    calib.set_camera_size(1280, 720)
    calib.fit(cam.project(tg), tg, True)
    return cam


def main():
    args = parse_args()
    cfg = load_config(args.config)
    if args.windowed:
        cfg.display.fullscreen = False
    if args.camera is not None:
        cfg.camera.index = args.camera
    if args.source:
        cfg.camera.source = args.source
    if args.hand:
        cfg.detection.mode = "hand"
    if args.reddot:
        cfg.detection.mode = "red_dot"
    calib = Calibration(cfg.display.width, cfg.display.height)

    if args.mouse:
        calib.fit([(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 0), (1, 0), (1, 1), (0, 1)])
        source = MousePointerSource()
    elif args.synthetic:
        cam = build_synthetic(cfg, calib)
        source = VisionPointerSource(cfg, cam, calib)
    else:
        from smartboard.vision.camera import Camera
        if not args.recalibrate:
            calib.load(cfg.calibration.file)
        source = VisionPointerSource(cfg, Camera(cfg.camera), calib)

    app = App(cfg, source, calib, mouse_mode=args.mouse)
    app.ctx.cfg_path = args.config
    app.run()


if __name__ == "__main__":
    sys.exit(main())
