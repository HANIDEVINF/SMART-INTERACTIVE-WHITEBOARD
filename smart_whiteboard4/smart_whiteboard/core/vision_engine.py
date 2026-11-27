"""Vision engine: camera thread -> vision thread -> Qt signals -> GUI.

    CameraWorker (thread 1)  --FrameMailbox (latest frame only)-->  VisionWorker (thread 2)
        read frames, mirror                                          detect -> track -> map
                                                                         |
                                           resultReady(VisionResult)  (queued signal)
                                                                         v
                                                           GUI thread (widgets, AppState)

Neither thread touches a widget; everything reaches the GUI as a queued Qt signal. The VisionController
lives in the GUI thread and is the only object the UI talks to.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from core.app_state import AppState
from core.calibration import Calibration, check_compatibility, load_calibration, save_calibration
from core.camera import CameraScanner, CameraWorker, CaptureFactory, FrameMailbox
from core.coordinate_mapping import BoardPoint, CoordinateMapper
from core.detector import DetectionParams, DetectionResult, detect
from core.hand_tracker import GestureClicker, HandTracker, hand_backend_status
from core.settings import CALIBRATION_PATH, Settings
from core.tracker import HOLDING, LOST, TRACKING, PointerTracker, TrackerParams, TrackOutput


@dataclass
class VisionResult:
    frame: np.ndarray                      # the frame this result was computed from (do not modify)
    frame_size: tuple[int, int]
    timestamp: float
    detection: DetectionResult
    track: TrackOutput
    board: BoardPoint | None               # pointer in board coordinates (None: lost / outside / uncalibrated)
    calib_state: str                       # none | ok | scaled | mismatch
    calib_message: str
    mask: np.ndarray | None                # cleaned binary mask, only when a page asked for it
    tracking_fps: float
    process_ms: float
    gesture_event: str | None = None       # hand backend: "next" | "previous" (one event per pinch)
    source: str = "marker"                 # "marker" | "hand"
    notice: str = ""                       # e.g. why the hand backend fell back to the marker

    @property
    def raw_position(self) -> tuple[float, float] | None:
        d = self.detection.detection
        return (d.x, d.y) if d else None


class VisionWorker(QThread):
    resultReady = Signal(object)
    signalLost = Signal()
    failed = Signal(str)

    def __init__(self, mailbox: FrameMailbox, params: DetectionParams, tracker_params: TrackerParams,
                 parent=None) -> None:
        super().__init__(parent)
        self.mailbox = mailbox
        self._lock = threading.Lock()
        self._params = params
        self._tracker_params = tracker_params
        self._mapper: CoordinateMapper | None = None
        self._mirror = False
        self._want_mask = False
        self._stop = threading.Event()
        self.tracker = PointerTracker(tracker_params)
        self._fps = 0.0
        self._last_t: float | None = None
        self._hand: HandTracker | None = None
        self._hand_error, self._hand_try_t = "", -1e9
        self.clicker = GestureClicker()

    # -------- configuration (called from the GUI thread; values are immutable, so swapping is atomic)
    def set_params(self, params: DetectionParams) -> None:
        with self._lock:
            self._params = params

    def set_tracker_params(self, params: TrackerParams) -> None:
        with self._lock:
            self._tracker_params = params

    def set_mapper(self, mapper: CoordinateMapper | None) -> None:
        with self._lock:
            self._mapper = mapper

    def set_mirror(self, mirror: bool) -> None:
        with self._lock:
            self._mirror = bool(mirror)

    def set_want_mask(self, want: bool) -> None:
        with self._lock:
            self._want_mask = bool(want)

    def stop(self, timeout_ms: int = 3000) -> None:
        self._stop.set()
        self.wait(timeout_ms)

    # -------- processing (also called directly by tests, without a thread)
    def process(self, frame: np.ndarray, t: float) -> VisionResult:
        with self._lock:
            params, tparams, mapper = self._params, self._tracker_params, self._mapper
            mirror, want_mask = self._mirror, self._want_mask
        t0 = time.perf_counter()
        h, w = frame.shape[:2]

        det, source, notice, event = self._detect(frame, params, t)
        measurement = (det.detection.x, det.detection.y) if det.detection else None
        self.tracker.set_params(tparams)
        track = self.tracker.update(measurement, t, math.hypot(w, h))

        board, calib_state, calib_msg = None, "none", ""
        if mapper is not None:
            calib_state, calib_msg = check_compatibility(mapper.calibration, (w, h), mirror)
            if calib_state != "mismatch" and track.position is not None:
                board = mapper.camera_to_board(track.position[0], track.position[1], (w, h))

        if self._last_t is not None and t > self._last_t:
            inst = 1.0 / (t - self._last_t)
            self._fps = inst if self._fps == 0.0 else 0.9 * self._fps + 0.1 * inst
        self._last_t = t

        return VisionResult(frame=frame, frame_size=(w, h), timestamp=t, detection=det, track=track,
                            board=board, calib_state=calib_state, calib_message=calib_msg,
                            mask=det.mask if want_mask else None, tracking_fps=self._fps,
                            process_ms=(time.perf_counter() - t0) * 1000.0, gesture_event=event,
                            source=source, notice=notice)

    def _detect(self, frame, params: DetectionParams, t: float):
        """-> (DetectionResult, source, notice, gesture_event). Hand backend with automatic marker fallback."""
        if params.method != "hand":
            self._close_hand()
            return detect(frame, params), "marker", "", None
        if self._hand is None and time.monotonic() - self._hand_try_t > 2.0:
            self._hand_try_t = time.monotonic()
            ok, msg = hand_backend_status()
            self._hand_error = "" if ok else msg
            if ok:
                self._hand = HandTracker()
                self.clicker.reset()
        if self._hand is not None:
            try:
                det = self._hand.detect(frame, t)
                return det, "hand", "", self.clicker.update(det.gesture_state, t)
            except Exception as exc:               # broken model / library: fall back instead of freezing
                self._hand_error = f"Hand tracking failed ({exc})"
                self._close_hand()
        det = detect(frame, params)
        note = f"{self._hand_error or 'Hand tracking unavailable'} - using the colour marker"
        det.message = note + ". " + det.message
        return det, "marker", note, None

    def _close_hand(self) -> None:
        if self._hand is not None:
            self._hand.close()
            self._hand = None

    def run(self) -> None:
        last_seq = 0
        idle_since = time.perf_counter()
        announced = False
        while not self._stop.is_set():
            item = self.mailbox.get(last_seq, 0.2)
            if item is None:
                if not announced and time.perf_counter() - idle_since > 1.0:
                    announced = True
                    self.tracker.reset()
                    self._fps, self._last_t = 0.0, None
                    self.signalLost.emit()
                continue
            frame, ts, last_seq = item
            idle_since, announced = time.perf_counter(), False
            try:
                self.resultReady.emit(self.process(frame, ts))
            except Exception as exc:             # never let one bad frame kill tracking
                self.failed.emit(f"Vision processing error: {exc}")
        self._close_hand()


class VisionController(QObject):
    """GUI-thread facade: owns both worker threads, the settings, the calibration and the AppState updates."""

    resultReady = Signal(object)
    signalLost = Signal()
    cameraStatusChanged = Signal(str, str)
    cameraOpened = Signal(int, int)
    cameraFpsChanged = Signal(float)
    camerasFound = Signal(list)
    calibrationChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(self, settings: Settings, state: AppState, capture_factory: CaptureFactory | None = None,
                 calibration_path=None, parent=None) -> None:
        super().__init__(parent)
        self.settings, self.state = settings, state
        self._factory = capture_factory
        self._calibration_path = calibration_path or CALIBRATION_PATH
        self.mailbox = FrameMailbox()
        self._camera: CameraWorker | None = None
        self._vision: VisionWorker | None = None
        self._scanner: CameraScanner | None = None

        self.detection_params = DetectionParams.from_settings(settings)
        self.tracker_params = TrackerParams.from_settings(settings)
        self.camera_index = int(settings.get("camera.index", 0))
        self.mirror = bool(settings.get("camera.mirror", False))
        self.resolution: tuple[int, int] | None = None
        self.camera_fps = 0.0
        self.camera_state = ("off", "Not started")
        self.want_mask = False

        self.calibration: Calibration | None = None
        self.mapper: CoordinateMapper | None = None
        self.calibration_error: str | None = None
        self._last_tracking_text: tuple[str, str] | None = None

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self.settings.save)

        cal, err = load_calibration(self._calibration_path)
        self.calibration_error = err
        if cal is not None:
            self._install_calibration(cal)
        else:
            self.mapper = None
            self.state.set_calibration("error" if err else "warn", "Invalid - recalibrate" if err else "Not calibrated")

    # ------------------------------------------------------------------ lifecycle
    @property
    def running(self) -> bool:
        return self._camera is not None and self._camera.isRunning()

    def start(self, index: int | None = None) -> None:
        if index is not None:
            self.camera_index = int(index)
            self.settings.set("camera.index", self.camera_index)
            self._save_timer.start()
        self.stop(quiet=True)
        s = self.settings.get
        self.mailbox = FrameMailbox()
        self._vision = VisionWorker(self.mailbox, self.detection_params, self.tracker_params, self)
        self._vision.set_mapper(self.mapper)
        self._vision.set_mirror(self.mirror)
        self._vision.set_want_mask(self.want_mask)
        self._vision.resultReady.connect(self._on_result)
        self._vision.signalLost.connect(self._on_signal_lost)
        self._vision.failed.connect(self.errorOccurred)
        self._camera = CameraWorker(self.mailbox, self.camera_index, int(s("camera.width", 1280)),
                                    int(s("camera.height", 720)), int(s("camera.fps", 30)), self.mirror,
                                    self._factory, self)
        self._camera.statusChanged.connect(self._on_camera_status)
        self._camera.opened.connect(self._on_opened)
        self._camera.fpsChanged.connect(self._on_fps)
        self._vision.start()
        self._camera.start()

    def stop(self, quiet: bool = False) -> None:
        camera, vision = self._camera, self._vision
        self._camera = self._vision = None
        if camera is not None:
            camera.stop()
            camera.deleteLater()
        if vision is not None:
            vision.stop()
            vision.deleteLater()
        self.resolution, self.camera_fps = None, 0.0
        self.mailbox.clear()
        if not quiet:
            self._set_camera_state("off", "Stopped")
            self._set_tracking("off", "Idle")
            self.signalLost.emit()

    def restart(self) -> None:
        self.start()

    def shutdown(self) -> None:
        self.stop(quiet=True)
        if self._scanner is not None:
            self._scanner.wait(3000)
        self.settings.save()

    # ------------------------------------------------------------------ configuration
    def set_detection_params(self, params: DetectionParams) -> None:
        self.detection_params = params.sanitized()
        if self._vision:
            self._vision.set_params(self.detection_params)
        self.detection_params.write_to(self.settings)
        self._save_timer.start()

    def set_tracker_params(self, params: TrackerParams) -> None:
        self.tracker_params = params.sanitized()
        if self._vision:
            self._vision.set_tracker_params(self.tracker_params)
        self.tracker_params.write_to(self.settings)
        self._save_timer.start()

    def set_method(self, method: str) -> None:
        """"color_marker" or "hand" (MediaPipe fingertip). Persisted."""
        self.set_detection_params(self.detection_params.with_(method=method))

    def set_mirror(self, mirror: bool) -> None:
        self.mirror = bool(mirror)
        self.settings.set("camera.mirror", self.mirror)
        self._save_timer.start()
        if self._camera:
            self._camera.set_mirror(self.mirror)
        if self._vision:
            self._vision.set_mirror(self.mirror)

    def set_want_mask(self, want: bool) -> None:
        self.want_mask = bool(want)
        if self._vision:
            self._vision.set_want_mask(self.want_mask)

    def scan_cameras(self) -> None:
        if self._scanner is not None and self._scanner.isRunning():
            return
        self._scanner = CameraScanner(4, self._factory, self)
        self._scanner.found.connect(self._on_cameras_found)
        self._scanner.start()

    def latest_frame(self) -> np.ndarray | None:
        return self.mailbox.latest()

    # ------------------------------------------------------------------ calibration
    def _install_calibration(self, cal: Calibration | None) -> None:
        self.calibration = cal
        self.mapper = (CoordinateMapper(cal, float(self.settings.get("calibration.edge_margin_px", 12)))
                       if cal else None)
        if self._vision:
            self._vision.set_mapper(self.mapper)
        if cal:
            w, h = cal.camera_size
            self.state.set_calibration("ok", f"Calibrated - {w}x{h}")
        else:
            self.state.set_calibration("warn", "Not calibrated")
        self.calibrationChanged.emit()

    def set_calibration(self, cal: Calibration) -> None:
        """Activate and persist a new calibration (raises OSError if it cannot be written)."""
        save_calibration(self._calibration_path, cal)
        self.calibration_error = None
        self._install_calibration(cal)

    def clear_calibration(self) -> None:
        try:
            import os
            os.unlink(self._calibration_path)
        except FileNotFoundError:
            pass
        self._install_calibration(None)

    # ------------------------------------------------------------------ worker slots (GUI thread)
    def _set_camera_state(self, state: str, text: str) -> None:
        self.camera_state = (state, text)
        self.state.set_camera(state, text)
        self.cameraStatusChanged.emit(state, text)

    def _set_tracking(self, state: str, text: str) -> None:
        self.state.set_tracking(state, text)

    def _on_camera_status(self, state: str, text: str) -> None:
        if state == "ok" and self.resolution:
            text = f"{self.resolution[0]}x{self.resolution[1]}"
        self._set_camera_state(state, text)
        if state != "ok":
            self.resolution = None
            self._set_tracking("off", "Idle")

    def _on_opened(self, w: int, h: int) -> None:
        self.resolution = (w, h)
        self.cameraOpened.emit(w, h)

    def _on_fps(self, fps: float) -> None:
        self.camera_fps = fps
        if self.resolution and fps > 0:
            self._set_camera_state("ok", f"{self.resolution[0]}x{self.resolution[1]} - {fps:.0f} FPS")
        self.cameraFpsChanged.emit(fps)

    def _on_cameras_found(self, cams: list) -> None:
        self.camerasFound.emit(cams)

    def _on_signal_lost(self) -> None:
        self._set_tracking("off", "Idle")
        self.signalLost.emit()

    def _on_result(self, res: VisionResult) -> None:
        calibrated = res.calib_state in ("ok", "scaled")
        if res.track.state == TRACKING:
            if not calibrated:
                self._set_tracking("warn", "Tracking - not calibrated")
            elif res.board is None:
                self._set_tracking("warn", "Outside the board")
            else:
                self._set_tracking("ok", "Tracking")
        elif res.track.state == HOLDING:
            self._set_tracking("warn", "Searching...")
        else:
            self._set_tracking("warn", "Pointer lost")
        if res.calib_state == "mismatch":
            self.state.set_calibration("error", "Recalibration needed")
        elif res.calib_state == "scaled":
            self.state.set_calibration("warn", "Rescaled - recalibrate")
        elif res.calib_state == "ok" and self.calibration:
            w, h = self.calibration.camera_size
            self.state.set_calibration("ok", f"Calibrated - {w}x{h}")
        self.resultReady.emit(res)
