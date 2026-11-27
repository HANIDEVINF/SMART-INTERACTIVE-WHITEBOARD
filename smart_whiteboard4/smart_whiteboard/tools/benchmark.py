"""Measures the vision pipeline on synthetic frames: pointer accuracy against ground truth and processing time.

Run from the project root:   python -m tools.benchmark
Prints a small Markdown table (used in docs/REPORT_MATERIAL.md). Needs no webcam.
"""
from __future__ import annotations

import platform
import time

import numpy as np

from core.calibration import Calibration
from core.coordinate_mapping import CoordinateMapper
from core.detector import DetectionParams, detect
from tests.synthetic import BOARD_H, BOARD_W, CAM_H, CAM_QUAD, CAM_W, render_scene


def main(n: int = 300, seed: int = 5) -> None:
    mapper = CoordinateMapper(Calibration.from_corners(CAM_QUAD, (CAM_W, CAM_H), (BOARD_W, BOARD_H)), edge_margin=12)
    params = DetectionParams()
    rng = np.random.default_rng(seed)
    errors, times, missed = [], [], 0
    for bx, by in rng.uniform([120, 90], [BOARD_W - 120, BOARD_H - 90], (n, 2)):
        frame = render_scene((bx, by), noise=3)
        t0 = time.perf_counter()
        res = detect(frame, params)
        times.append((time.perf_counter() - t0) * 1000)
        det = res.detection
        if det is None:
            missed += 1
            continue
        p = mapper.camera_to_board(det.x, det.y)
        errors.append(float(np.hypot(p.x - bx, p.y - by)))
    e, t = np.array(errors), np.array(times)
    print(f"Synthetic benchmark: {n} frames {CAM_W}x{CAM_H}, random marker positions, noise sigma 3, "
          f"Python {platform.python_version()} on {platform.system()}")
    print("| Metric | Value |\n|---|---|")
    print(f"| Marker found | {n - missed} / {n} |")
    print(f"| Board error, mean | {e.mean():.2f} px (board {BOARD_W}x{BOARD_H}) |")
    print(f"| Board error, median | {np.median(e):.2f} px |")
    print(f"| Board error, 95th percentile | {np.percentile(e, 95):.2f} px |")
    print(f"| Board error, max | {e.max():.2f} px |")
    print(f"| Detection time, mean | {t.mean():.1f} ms ({1000 / t.mean():.0f} frames/s) |")
    print(f"| Detection time, 95th percentile | {np.percentile(t, 95):.1f} ms |")


if __name__ == "__main__":
    main()
