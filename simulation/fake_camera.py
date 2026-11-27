"""Simulated camera: generates synthetic BGR frames for testing.

The fake scene is a dark background with a bright green circular marker
that moves along a Lissajous path, plus a few static coloured distractor
blobs.  This lets the detection pipeline, calibration and tracking be
tested end-to-end without a physical webcam or marker.
"""

from __future__ import annotations

import math
import time

import cv2
import numpy as np


class FakeCamera:
    """Drop-in replacement for :class:`camera.camera.Camera`."""

    def __init__(self, width: int = 640, height: int = 480, fps: float = 30.0):
        self.width = width
        self.height = height
        self._fps = fps
        self._start = time.time()
        self.last_error = None

    def open(self) -> bool:
        return True

    def is_open(self) -> bool:
        return True

    def read(self) -> np.ndarray:
        t = time.time() - self._start
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Dark blue-ish background with a subtle gradient so the scene is
        # not perfectly uniform.
        frame[..., 0] = 40
        frame[..., 1] = 40
        frame[..., 2] = 60

        # Static distractor blobs (red, small) that the detector must
        # reject thanks to colour + area filtering.
        cv2.circle(frame, (80, 80), 12, (0, 0, 200), -1)
        cv2.circle(frame, (self.width - 90, self.height - 70), 18,
                   (200, 0, 0), -1)  # blue distractor (outside green range)

        # Moving green marker on a Lissajous trajectory.
        cx = self.width / 2 + 0.35 * self.width * math.sin(0.7 * t)
        cy = self.height / 2 + 0.30 * self.height * math.sin(1.3 * t + 1.0)
        cv2.circle(frame, (int(cx), int(cy)), 22, (0, 255, 0), -1)
        cv2.circle(frame, (int(cx), int(cy)), 22, (255, 255, 255), 2)

        # A faint grid to make the scene look like a camera view.
        for x in range(0, self.width, 80):
            cv2.line(frame, (x, 0), (x, self.height), (50, 50, 60), 1)
        for y in range(0, self.height, 80):
            cv2.line(frame, (0, y), (self.width, y), (50, 50, 60), 1)

        return frame

    @property
    def fps(self) -> float:
        return self._fps

    def release(self) -> None:
        pass
