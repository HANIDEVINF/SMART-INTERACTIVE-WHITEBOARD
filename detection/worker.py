"""Background detection worker.

Marker detection costs ~20 ms per frame (manual NumPy HSV conversion).  If
it ran on the UI thread the interface would stutter every time a camera
frame arrived.  This worker runs it on its own thread instead:

    camera grabber thread  --latest frame-->  DetectionWorker thread
                                                    |
                                          latest (frame_id, Detection)
                                                    |
                                         UI thread (tracker, drawing)

Only the *latest* frame is processed: if detection is slower than the
camera, frames are skipped rather than queued, so the pointer never lags
behind reality.  NumPy releases the GIL inside its large array operations,
so the UI thread keeps drawing while the worker computes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from detection.color_detector import ColorDetector, Detection

logger = logging.getLogger(__name__)


class DetectionWorker:
    def __init__(self, camera, detector: ColorDetector):
        self._camera = camera
        self._detector = detector
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._result: tuple[int, Optional[Detection]] = (0, None)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop,
                                        name="detection-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None

    def latest(self) -> tuple[int, Optional[Detection]]:
        """``(frame_id, detection)`` of the most recently processed frame.
        ``frame_id`` is 0 until the first frame has been processed."""
        with self._lock:
            return self._result

    def _loop(self) -> None:
        last_id = 0
        while not self._stop.is_set():
            frame, frame_id = self._camera.read_latest()
            if frame is None or frame_id == last_id:
                time.sleep(0.004)
                continue
            last_id = frame_id
            try:
                det = self._detector.detect(frame)
            except Exception:  # noqa: BLE001 - never kill the worker
                logger.exception("Detection failed")
                det = None
            with self._lock:
                self._result = (frame_id, det)
