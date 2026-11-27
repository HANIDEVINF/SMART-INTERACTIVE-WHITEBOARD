"""Threaded webcam acquisition.

The CameraWorker thread does nothing but read frames and drop the newest one into a FrameMailbox
(a one-slot "latest frame" buffer). Consumers - the vision thread - always get the most recent frame;
if they are slower than the camera, older frames are simply skipped, so latency never builds up and
the GUI thread is never involved in blocking camera I/O.

Windows notes: DirectShow (CAP_DSHOW) opens fastest and honours resolution requests best, so it is
tried first, then Media Foundation, then OpenCV's default. MJPG is requested because many webcams
only reach 30 FPS at 720p in MJPG (the default YUY2 is often limited to 5-15 FPS).
"""
from __future__ import annotations

import sys
import threading
import time
from typing import Callable

import cv2
from PySide6.QtCore import QThread, Signal

NOT_FOUND_MESSAGE = ("Camera could not be opened. Close other apps that use it and check Windows "
                     "Settings > Privacy & security > Camera (allow desktop apps).")

CaptureFactory = Callable[[int, int], "cv2.VideoCapture"]
_graveyard: list[QThread] = []       # threads that did not stop in time must not be garbage collected


def default_capture_factory(index: int, backend: int) -> "cv2.VideoCapture":
    return cv2.VideoCapture(index, backend)


def backends() -> list[int]:
    if sys.platform.startswith("win"):
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
    return [cv2.CAP_ANY]


class FrameMailbox:
    """Thread-safe single-slot buffer holding the latest frame."""

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._frame = None
        self._ts = 0.0
        self._seq = 0

    def put(self, frame, ts: float) -> None:
        with self._cv:
            self._frame, self._ts = frame, ts
            self._seq += 1
            self._cv.notify_all()

    def get(self, last_seq: int, timeout: float):
        """Wait up to `timeout` s for a frame newer than `last_seq`; returns (frame, ts, seq) or None."""
        with self._cv:
            if self._seq == last_seq:
                self._cv.wait(timeout)
            if self._seq == last_seq:
                return None
            return self._frame, self._ts, self._seq

    def latest(self):
        with self._cv:
            return self._frame

    def clear(self) -> None:
        with self._cv:
            self._frame = None


class CameraWorker(QThread):
    statusChanged = Signal(str, str)     # (state: ok|warn|error, message)
    opened = Signal(int, int)            # actual frame width, height
    fpsChanged = Signal(float)

    FAILS_BEFORE_DISCONNECT = 15
    RETRY_SECONDS = 2.0

    def __init__(self, mailbox: FrameMailbox, index: int = 0, width: int = 1280, height: int = 720,
                 fps: int = 30, mirror: bool = False, capture_factory: CaptureFactory | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.mailbox = mailbox
        self.index, self.width, self.height, self.fps = int(index), int(width), int(height), int(fps)
        self._mirror = bool(mirror)
        self._factory = capture_factory or default_capture_factory
        self._stop = threading.Event()
        self._last_status: tuple[str, str] | None = None

    def set_mirror(self, mirror: bool) -> None:
        self._mirror = bool(mirror)

    def stop(self, timeout_ms: int = 4000) -> None:
        self._stop.set()
        if not self.wait(timeout_ms):
            _graveyard.append(self)       # blocked inside cap.read(): let it die on its own

    # ------------------------------------------------------------------ thread body
    def run(self) -> None:
        self._status("warn", "Connecting...")
        cap = None
        fails = 0
        frames, window_start = 0, time.perf_counter()
        while not self._stop.is_set():
            if cap is None:
                cap = self._open()
                if cap is None:
                    self._status("error", NOT_FOUND_MESSAGE)
                    self._stop.wait(self.RETRY_SECONDS)
                    continue
                fails, frames, window_start = 0, 0, time.perf_counter()

            ok, frame = cap.read()
            if not ok or frame is None or getattr(frame, "size", 0) == 0:
                fails += 1
                if fails >= self.FAILS_BEFORE_DISCONNECT:
                    cap.release()
                    cap = None
                    self.mailbox.clear()
                    self._status("warn", "Camera disconnected - trying to reconnect...")
                    self.fpsChanged.emit(0.0)
                    self._stop.wait(1.0)
                else:
                    self._stop.wait(0.02)
                continue
            fails = 0
            self._publish(frame)
            frames += 1
            now = time.perf_counter()
            if now - window_start >= 1.0:
                self.fpsChanged.emit(frames / (now - window_start))
                frames, window_start = 0, now
        if cap is not None:
            cap.release()

    def _publish(self, frame) -> None:
        if self._mirror:
            frame = cv2.flip(frame, 1)
        self.mailbox.put(frame, time.perf_counter())

    def _open(self):
        for backend in backends():
            if self._stop.is_set():
                return None
            try:
                cap = self._factory(self.index, backend)
            except Exception:             # some backends raise instead of returning a closed capture
                continue
            if cap is not None and cap.isOpened():
                for prop, value in ((cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG")),
                                    (cv2.CAP_PROP_FRAME_WIDTH, self.width),
                                    (cv2.CAP_PROP_FRAME_HEIGHT, self.height),
                                    (cv2.CAP_PROP_FPS, self.fps),
                                    (cv2.CAP_PROP_BUFFERSIZE, 1)):
                    cap.set(prop, value)
                ok, frame = cap.read()                       # a camera that opens but gives no frames is unusable
                if ok and frame is not None and frame.size:
                    h, w = frame.shape[:2]
                    self.opened.emit(w, h)
                    self._status("ok", f"Connected - {w}x{h}")
                    self._publish(frame)
                    return cap
            if cap is not None:
                cap.release()
        return None

    def _status(self, state: str, text: str) -> None:
        if (state, text) != self._last_status:
            self._last_status = (state, text)
            self.statusChanged.emit(state, text)


# ----------------------------------------------------------------------------- discovery
def probe_cameras(max_index: int = 4, factory: CaptureFactory | None = None) -> list[tuple[int, str]]:
    """Try camera indices 0..max_index and return [(index, label)] for those that deliver a frame."""
    factory = factory or default_capture_factory
    found = []
    for i in range(max_index + 1):
        for backend in backends():
            try:
                cap = factory(i, backend)
            except Exception:
                continue
            try:
                if cap is not None and cap.isOpened():
                    ok, frame = cap.read()
                    if ok and frame is not None and frame.size:
                        h, w = frame.shape[:2]
                        found.append((i, f"Camera {i}  ({w}x{h})"))
                        break
            finally:
                if cap is not None:
                    cap.release()
    return found


class CameraScanner(QThread):
    """Runs probe_cameras() off the GUI thread (opening devices can take seconds)."""

    found = Signal(list)

    def __init__(self, max_index: int = 4, factory: CaptureFactory | None = None, parent=None) -> None:
        super().__init__(parent)
        self.max_index, self.factory = max_index, factory

    def run(self) -> None:
        self.found.emit(probe_cameras(self.max_index, self.factory))
