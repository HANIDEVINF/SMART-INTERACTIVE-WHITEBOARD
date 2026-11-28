"""Measure how exactly the pipeline follows a moving dot (numbers + picture for the report).

A simulated camera (perspective + barrel lens distortion + sensor noise + a saturated white-core
dot) watches a dot that moves on a figure-8 over the board in real time.  Every processed frame
compares the tracked board position with the TRUE board position of the dot.

    python tools/trajectory_bench.py [seconds] [camera_fps] [speed] [beta] [min_cutoff] [hand]
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cv2
import numpy as np

from smartboard.config import Config
from smartboard.vision.calibration import Calibration, apply_homography, calibration_targets, compute_homography
from smartboard.vision.camera import SyntheticCamera
from smartboard.vision.pointer_source import VisionPointerSource

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
fps = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
speed = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
W, H = 1920, 1080
cfg = Config()
if len(sys.argv) > 4:
    cfg.tracking.beta = float(sys.argv[4])
if len(sys.argv) > 5:
    cfg.tracking.min_cutoff = float(sys.argv[5])
Hbc = compute_homography(np.array([[0, 0], [W, 0], [W, H], [0, H]], float),
                         np.array([[210, 120], [1050, 80], [1120, 640], [140, 600]], float))
lens = Calibration(W, H); lens.set_camera_size(1280, 720); lens.k1 = 0.12
state = {"p": None, "last": None}


def dot():
    return state["p"]


HAND = len(sys.argv) > 6 and sys.argv[6] == "hand"
if HAND:
    cfg.detection.mode = "hand"
cam = SyntheticCamera(1280, 720, (W, H), Hbc, dot, fps=fps, lens=lens, core=True, hand=HAND)
calib = Calibration(W, H)
src = VisionPointerSource(cfg, cam, calib)

# --- calibration: 9 targets, hold each for 12 frames
tg = calibration_targets(W, H, cfg.calibration.target_margin, 9)
cp = []
for t in tg:
    state["p"] = tuple(t)
    n0 = src.frames
    while src.frames - n0 < 12:
        src.update()
    cp.append(src.sample.cam)
calib.fit(cp, tg, True)
src.refresh_roi()
print("calibration: k1 = %+.3f  (true +0.120)" % calib.k1)

# --- moving dot
t0 = time.perf_counter()
truth, est, times = [], [], []
last_frames = src.frames
while time.perf_counter() - t0 < secs:
    t = (time.perf_counter() - t0) * speed
    state["p"] = (W * (0.5 + 0.38 * math.sin(1.3 * t)), H * (0.5 + 0.36 * math.sin(2.6 * t)))
    src.update()
    if src.frames != last_frames and src.sample.board is not None:
        last_frames = src.frames
        truth.append(state["p"]); est.append(src.sample.board); times.append(time.perf_counter() - t0)
truth, est = np.array(truth), np.array(est)
err = np.linalg.norm(truth - est, axis=1)
sp = np.linalg.norm(np.diff(truth, axis=0), axis=1) / np.maximum(np.diff(times), 1e-3)
print("frames %d   camera %.0f fps   pipeline %.1f ms/frame   dot speed ~%.0f px/s"
      % (len(err), src.fps, src.latency_ms, sp.mean()))
print("error (board px, 1920x1080):  mean %.1f   median %.1f   95%% %.1f   max %.1f"
      % (err.mean(), np.median(err), np.percentile(err, 95), err.max()))
# the dot is seen ~1 frame late and the filter adds a little lag: error with the best time shift
best = min(range(0, 6), key=lambda k: np.linalg.norm(truth[:len(truth) - k] - est[k:], axis=1).mean())
e2 = np.linalg.norm(truth[:len(truth) - best] - est[best:], axis=1)
print("after removing a %d-frame delay (= pure lag):  mean %.1f px   -> geometric error without lag" % (best, e2.mean()))

img = np.full((H // 2, W // 2, 3), 20, np.uint8)
pts = lambda a: (a / 2).astype(np.int32).reshape(-1, 1, 2)
cv2.polylines(img, [pts(truth)], False, (90, 220, 90), 2, cv2.LINE_AA)
cv2.polylines(img, [pts(est)], False, (255, 200, 60), 2, cv2.LINE_AA)
cv2.putText(img, "green = true path   blue = tracked path   mean error %.1f px" % err.mean(), (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (230, 230, 230), 2, cv2.LINE_AA)
cv2.imwrite("trajectory_bench.png", img)
print("picture: trajectory_bench.png")
