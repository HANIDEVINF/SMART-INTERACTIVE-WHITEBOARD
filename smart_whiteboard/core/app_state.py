"""Shared application state, observable through Qt signals.

The camera / vision threads never touch widgets: they report to the VisionController, which
updates this object from the GUI thread, and widgets subscribe to the signals.

States are plain strings: "ok" | "warn" | "error" | "off".
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AppState(QObject):
    cameraChanged = Signal(str, str)       # (state, human readable text)
    trackingChanged = Signal(str, str)
    calibrationChanged = Signal(str, str)
    modeChanged = Signal(str)              # "navigation" | "drawing" | "selection"

    def __init__(self) -> None:
        super().__init__()
        self.camera = ("off", "Not started")
        self.tracking = ("off", "Idle")
        self.calibration = ("warn", "Not calibrated")
        self.mode = "drawing"

    def set_camera(self, state: str, text: str) -> None:
        if (state, text) != self.camera:
            self.camera = (state, text)
            self.cameraChanged.emit(state, text)

    def set_tracking(self, state: str, text: str) -> None:
        if (state, text) != self.tracking:
            self.tracking = (state, text)
            self.trackingChanged.emit(state, text)

    def set_calibration(self, state: str, text: str) -> None:
        if (state, text) != self.calibration:
            self.calibration = (state, text)
            self.calibrationChanged.emit(state, text)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.modeChanged.emit(mode)
