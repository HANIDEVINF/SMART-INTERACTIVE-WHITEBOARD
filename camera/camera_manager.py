"""Camera manager: chooses between the real webcam and the simulated
camera source, and exposes a non-blocking interface to the app.

Frames are grabbed on a background thread.  ``cap.read()`` blocks until the
next frame arrives (about 33 ms at 30 fps); doing that on the UI thread
capped the whole interface at the camera frame rate.  Now the UI thread
just asks for the *latest* frame and keeps drawing at 60 fps.

    frame = manager.read()                  # latest frame (may repeat)
    frame, frame_id = manager.read_latest() # id changes on every new frame
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import numpy as np

from camera.camera import Camera
from simulation.fake_camera import FakeCamera

logger = logging.getLogger(__name__)


class CameraManager:
    """Unified camera source.

    ``source`` is "real" or "simulated".  The simulated source generates a
    synthetic scene with a moving coloured marker so the whole detection
    and calibration pipeline can be exercised without hardware.
    """

    def __init__(self, settings: dict):
        self.settings = settings
        self._real: Optional[Camera] = None
        self._fake: Optional[FakeCamera] = None
        self._source = settings.get("camera_source", "real")
        self.last_error: Optional[str] = None

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._frame_id = 0

    # -- lifecycle ---------------------------------------------------------

    def open(self) -> bool:
        if self._source == "simulated":
            self._fake = FakeCamera(width=640, height=480)
            logger.info("Using simulated camera source")
            ok = True
        else:
            self._real = Camera(
                index=int(self.settings.get("camera_index", 0)),
                width=int(self.settings.get("camera_width", 1280)),
                height=int(self.settings.get("camera_height", 720)),
            )
            ok = self._real.open()
            if not ok:
                self.last_error = self._real.last_error
        if ok:
            self._start_thread()
        return ok

    def _source_obj(self):
        return self._fake if self._fake is not None else self._real

    def _start_thread(self) -> None:
        self._stop.clear()
        # Make the first frame available immediately.
        first = self._source_obj().read()
        if first is not None:
            self._publish(first)
        self._thread = threading.Thread(target=self._grab_loop,
                                        name="camera-grabber", daemon=True)
        self._thread.start()

    def _publish(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame
            self._frame_id += 1

    def _grab_loop(self) -> None:
        src = self._source_obj()
        simulated = self._fake is not None
        while not self._stop.is_set():
            try:
                frame = src.read()
            except Exception:  # noqa: BLE001 - never kill the grabber
                logger.exception("Camera grab failed")
                frame = None
            if frame is None:
                time.sleep(0.01)
                continue
            self._publish(frame)
            if simulated:
                time.sleep(1 / 30)    # the fake camera returns instantly

    # -- reading -----------------------------------------------------------

    def read_latest(self):
        """Return ``(frame, frame_id)``; the id changes on each new frame."""
        with self._lock:
            return self._frame, self._frame_id

    def read(self) -> Optional[np.ndarray]:
        """Latest frame (non-blocking; the same frame may be returned
        again if the camera has not produced a new one yet)."""
        return self.read_latest()[0]

    @property
    def fps(self) -> float:
        src = self._source_obj()
        return src.fps if src is not None else 0.0

    @property
    def source_name(self) -> str:
        return self._source

    def release(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None
        if self._real is not None:
            self._real.release()
            self._real = None
        self._fake = None
        with self._lock:
            self._frame = None
