"""Camera acquisition module.

Wraps OpenCV's VideoCapture (OpenCV is used here because reliable
multi-platform webcam access is exactly what it is good at) behind a small
interface that the rest of the application depends on:

    frame = camera.read()        # BGR uint8 array or None
    camera.release()             # always call on shutdown

The module handles:
  * configurable camera index and resolution
  * initialization failure (returns a status instead of crashing)
  * lost/dropped frames (returns None, never raises)
  * FPS measurement
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class Camera:
    """Live webcam capture with graceful failure handling."""

    def __init__(self, index: int = 0, width: int = 1280, height: int = 720):
        self.index = index
        self.width = width
        self.height = height
        self._cap: Optional[cv2.VideoCapture] = None
        self._fps = 0.0
        self._fps_time = time.time()
        self._fps_frames = 0
        self.last_error: Optional[str] = None

    # -- lifecycle ---------------------------------------------------------

    def open(self) -> bool:
        """Try to open the camera.  Returns True on success."""
        try:
            self._cap = None
            if sys.platform.startswith("win"):
                # DirectShow starts faster on Windows; elsewhere the
                # default backend is the right one.
                self._cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
            if self._cap is None or not self._cap.isOpened():
                # Fallback without the DirectShow backend (some drivers).
                self._cap = cv2.VideoCapture(self.index)
            if not self._cap.isOpened():
                self.last_error = f"Could not open camera index {self.index}"
                logger.error(self.last_error)
                return False
            # Low latency: MJPEG reaches 30 fps at 720p on USB2 webcams and
            # a 1-frame buffer avoids displaying stale images.
            self._cap.set(cv2.CAP_PROP_FOURCC,
                          cv2.VideoWriter_fourcc(*"MJPG"))
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            # Warm up: the first frames of many webcams are garbage.
            for _ in range(5):
                self._cap.read()
            self.last_error = None
            logger.info("Camera %d opened (%dx%d)",
                        self.index, self.width, self.height)
            return True
        except Exception as exc:  # noqa: BLE001 - never crash on camera errors
            self.last_error = f"Camera error: {exc}"
            logger.exception("Camera.open failed")
            return False

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> Optional[np.ndarray]:
        """Return the next BGR frame, or None if the frame was lost."""
        if not self.is_open():
            return None
        try:
            ok, frame = self._cap.read()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Camera read failed: %s", exc)
            return None
        if not ok or frame is None:
            return None
        self._update_fps()
        return frame

    def release(self) -> None:
        """Release the camera device.  Safe to call multiple times."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:  # noqa: BLE001
                pass
            self._cap = None
        logger.info("Camera released")

    # -- stats -------------------------------------------------------------

    def _update_fps(self) -> None:
        self._fps_frames += 1
        now = time.time()
        elapsed = now - self._fps_time
        if elapsed >= 0.5:
            self._fps = self._fps_frames / elapsed
            self._fps_frames = 0
            self._fps_time = now

    @property
    def fps(self) -> float:
        return self._fps
