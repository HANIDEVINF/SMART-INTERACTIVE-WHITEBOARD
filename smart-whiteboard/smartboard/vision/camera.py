"""Camera acquisition (threaded, always returns the NEWEST frame) + a synthetic
camera used for tests / demos without hardware.

Why a thread?  cv2.VideoCapture.read() blocks for a whole frame period and
buffers old frames; reading in a background thread and keeping only the
latest frame removes that latency from the interaction loop.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Tuple

import numpy as np

from ..config import CameraConfig


class Camera:
    def __init__(self, cfg: CameraConfig):
        import cv2  # OpenCV is used ONLY for camera acquisition
        self.cv2 = cv2
        self.cfg = cfg
        backends = {"auto": cv2.CAP_ANY, "dshow": cv2.CAP_DSHOW,
                    "msmf": cv2.CAP_MSMF, "v4l2": cv2.CAP_V4L2}
        if cfg.source:                       # phone / IP camera: network stream URL (or a video file)
            src = int(cfg.source) if cfg.source.isdigit() else cfg.source
            self.cap = cv2.VideoCapture(src) if isinstance(src, str) else cv2.VideoCapture(src, backends.get(cfg.backend, cv2.CAP_ANY))
        else:
            self.cap = cv2.VideoCapture(cfg.index, backends.get(cfg.backend, cv2.CAP_ANY))
        if not self.cap.isOpened():
            raise RuntimeError("cannot open camera %r - for a phone check that the URL opens in a browser "
                               "and that phone and PC are on the same Wi-Fi" % (cfg.source or cfg.index))
        if cfg.fourcc:
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*cfg.fourcc))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
        self.cap.set(cv2.CAP_PROP_FPS, cfg.fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if cfg.exposure is not None:
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)   # manual mode (V4L2 semantics)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, cfg.exposure)
        self._frame: Optional[np.ndarray] = None
        self._stamp = 0
        self._last_read = 0
        self._lock = threading.Lock()
        self._run = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._run:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            if self.cfg.flip_horizontal:
                frame = frame[:, ::-1]
            if self.cfg.flip_vertical:
                frame = frame[::-1]
            with self._lock:
                self._frame = np.ascontiguousarray(frame)
                self._stamp += 1

    def read(self) -> Optional[np.ndarray]:
        """Latest frame, or None if no *new* frame arrived since the last call."""
        with self._lock:
            if self._frame is None or self._stamp == self._last_read:
                return None
            self._last_read = self._stamp
            return self._frame

    @property
    def size(self) -> Tuple[int, int]:
        return (int(self.cap.get(self.cv2.CAP_PROP_FRAME_WIDTH)),
                int(self.cap.get(self.cv2.CAP_PROP_FRAME_HEIGHT)))

    def release(self):
        self._run = False
        self._thread.join(timeout=1.0)
        self.cap.release()


class SyntheticCamera:
    """Renders what a camera would see: a dark room, a slightly brighter
    projected rectangle (the board) and a bright red dot.

    ``board_to_cam`` is a 3x3 homography (board px -> camera px) describing
    the camera pose; ``dot_board`` returns the dot position in board pixels
    (or None = dot off).  Options:
      fps    : deliver at most this many frames per second (like a real camera)
      lens   : a vision.calibration.Calibration whose ``k1`` bends straight lines (barrel distortion)
      core   : the dot has a saturated WHITE centre with a red halo (a strong laser)
      noise  : sensor noise (grey levels)
      hand   : the pointer is a hand (finger + palm + forearm, skin colour) whose fingertip is at the dot position
    Used by the unit tests and ``main.py --synthetic``.
    """

    def __init__(self, width: int, height: int, board_size: Tuple[int, int],
                 board_to_cam: np.ndarray, dot_board: Callable[[], Optional[Tuple[float, float]]],
                 noise: float = 4.0, seed: int = 1, fps: float = 0.0, lens=None, core: bool = False,
                 hand: bool = False, hand_dir=(0.55, 0.83)):
        self.w, self.h = width, height
        self.board_size = board_size
        self.Hbc = board_to_cam
        self.dot_board = dot_board
        self.noise = noise
        self.fps = fps
        self.lens = lens
        self.core = core
        self.hand = hand                 # draw a skin-coloured hand pointing at the dot instead of a red dot
        u = np.asarray(hand_dir, float)
        self.hand_u = u / np.linalg.norm(u)   # unit vector from the fingertip towards the arm
        self._t_last = 0.0
        self.rng = np.random.default_rng(seed)
        self._bg = self._make_background()

    def project(self, pts) -> np.ndarray:
        """board px -> camera px (perspective, then lens distortion)."""
        from .calibration import apply_homography
        p = apply_homography(self.Hbc, pts)
        return self.lens.distort(p) if self.lens is not None else p

    def _make_background(self) -> np.ndarray:
        from .imgproc import polygon_mask
        bg = np.full((self.h, self.w, 3), 25, np.uint8)
        bw, bh = self.board_size
        edge = []
        for a, b in (((0, 0), (bw, 0)), ((bw, 0), (bw, bh)), ((bw, bh), (0, bh)), ((0, bh), (0, 0))):
            edge += [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in np.linspace(0, 1, 24, endpoint=False)]
        inside = polygon_mask((self.h, self.w), self.project(edge))
        bg[inside] = (150, 120, 90)                       # lit projection (bluish-grey)
        # a dim red *projected* patch: must NOT be detected (value below threshold)
        p = self.project([(bw * 0.7, bh * 0.2)])[0]
        x, y = int(p[0]), int(p[1])
        bg[max(0, y - 25):y + 25, max(0, x - 40):x + 40] = (30, 30, 150)
        return bg

    def read(self) -> Optional[np.ndarray]:
        import time
        if self.fps > 0:
            now = time.perf_counter()
            if now - self._t_last < 1.0 / self.fps:
                return None
            self._t_last = now
        frame = self._bg.astype(np.float32)
        if self.noise:
            frame = frame + self.rng.normal(0, self.noise, frame.shape)
        d = self.dot_board()
        if d is not None and self.hand:
            self._draw_hand(frame, self.project([d])[0])
        elif d is not None:
            cx, cy = self.project([d])[0]
            r = 5
            x0, x1 = int(max(0, cx - 3 * r)), int(min(self.w, cx + 3 * r + 1))
            y0, y1 = int(max(0, cy - 3 * r)), int(min(self.h, cy + 3 * r + 1))
            if x1 > x0 and y1 > y0:
                yy, xx = np.mgrid[y0:y1, x0:x1]
                d2 = ((xx - cx) ** 2 + (yy - cy) ** 2)
                g = np.exp(-d2 / (2 * (r * 0.6) ** 2))[..., None]
                dot = np.array([40, 40, 255], np.float32)  # BGR saturated red
                frame[y0:y1, x0:x1] = frame[y0:y1, x0:x1] * (1 - g) + dot * g
                if self.core:                               # saturated white centre
                    g2 = np.exp(-d2 / (2 * (r * 0.28) ** 2))[..., None]
                    frame[y0:y1, x0:x1] = frame[y0:y1, x0:x1] * (1 - g2) + 255.0 * g2
        return np.clip(frame, 0, 255).astype(np.uint8)

    def _draw_hand(self, frame, tip):
        """Finger (rounded tip) + palm + forearm, filled with a skin colour, tip exactly at ``tip``."""
        from .imgproc import polygon_mask
        u = self.hand_u
        v = np.array([-u[1], u[0]])
        tip = np.asarray(tip, float)
        P = lambda a, b: tip + a * u + b * v                 # a along the finger (towards the arm), b across
        arc = [P(11 - 11 * np.cos(t), 11 * np.sin(t)) for t in np.linspace(-np.pi / 2, np.pi / 2, 9)]
        finger = arc + [P(100, 11), P(100, -11)]
        palm = [P(140 + 62 * np.cos(t), 62 * np.sin(t)) for t in np.linspace(0, 2 * np.pi, 20, endpoint=False)]
        arm = [P(180, 44), P(900, 52), P(900, -52), P(180, -44)]
        pts = np.array(finger + palm + arm)
        x0, y0 = np.maximum(0, np.floor(pts.min(axis=0)).astype(int))
        x1, y1 = np.minimum([self.w, self.h], np.ceil(pts.max(axis=0)).astype(int) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        m = np.zeros((y1 - y0, x1 - x0), bool)
        for poly in (finger, palm, arm):
            m |= polygon_mask(m.shape, np.array(poly) - [x0, y0])
        shade = 1.0 + 0.06 * self.rng.standard_normal(m.shape)[..., None]
        skin = np.array([112, 150, 205], np.float32)         # BGR light-brown skin
        reg = frame[y0:y1, x0:x1]
        reg[m] = (skin * shade)[m]

    def release(self):
        pass
