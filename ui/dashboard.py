"""Home dashboard: brand header, six action cards, live status and recent files."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                               QWidget)

from core.app_state import AppState
from core.settings import Settings
from ui import brand
from ui.styles import ACCENT, AMBER, APP_NAME, APP_TAGLINE, BLUE, ROSE, TEAL
from ui.widgets import ActionCard, StatusRow


def _panel(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("panel")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(10)
    label = QLabel(title)
    label.setObjectName("panelTitle")
    lay.addWidget(label)
    return frame, lay


class Dashboard(QWidget):
    navigate = Signal(str)          # page id
    openImageRequested = Signal()
    openRecentRequested = Signal(str)

    def __init__(self, settings: Settings, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self.settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(44, 34, 44, 30)
        root.setSpacing(22)

        # ---- header -------------------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(16)
        logo = QLabel()
        logo.setPixmap(brand.logo_pixmap(64))
        header.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("h1")
        sub = QLabel(APP_TAGLINE + "  -  USTHB Computer Vision project")
        sub.setObjectName("muted")
        names.addWidget(title)
        names.addWidget(sub)
        header.addLayout(names)
        header.addStretch(1)
        self.camera_pill = self._pill("Camera")
        self.tracking_pill = self._pill("Tracking")
        header.addWidget(self.camera_pill[0])
        header.addWidget(self.tracking_pill[0])
        root.addLayout(header)

        greeting = QLabel(self._greeting())
        greeting.setObjectName("h2")
        root.addWidget(greeting)

        # ---- body ---------------------------------------------------------------------
        body = QHBoxLayout()
        body.setSpacing(22)
        root.addLayout(body, 1)

        grid = QGridLayout()
        grid.setSpacing(16)
        cards = [
            ("pen", "Start Whiteboard", "Draw, annotate and teach on the interactive board.",
             ACCENT, None, lambda: self.navigate.emit("whiteboard")),
            ("image", "Open Image", "Place an image on the board and annotate over it.",
             BLUE, None, self.openImageRequested.emit),
            ("teaching", "Teaching Mode", "Build and present a multi-page lesson.",
             TEAL, "PHASE 6", lambda: self.navigate.emit("teaching")),
            ("calibrate", "Calibration", "Map the camera view onto the board corners.",
             AMBER, None, lambda: self.navigate.emit("calibration")),
            ("camera", "Camera Diagnostics", "Live feed, resolution, FPS and detection status.",
             ROSE, None, lambda: self.navigate.emit("camera")),
            ("settings", "Settings", "Marker colour tuning, tracking and preferences.",
             "#64748B", None, lambda: self.navigate.emit("settings")),
        ]
        self.cards: list[ActionCard] = []
        for i, (icon_name, name, text, accent, badge, action) in enumerate(cards):
            card = ActionCard(icon_name, name, text, accent, badge)
            card.clicked.connect(action)
            grid.addWidget(card, i // 2, i % 2)
            self.cards.append(card)
        grid.setRowStretch(3, 1)
        body.addLayout(grid, 3)

        side = QVBoxLayout()
        side.setSpacing(16)
        body.addLayout(side, 2)

        status_panel, status_lay = _panel("System status")
        self.row_camera = StatusRow("Camera")
        self.row_tracking = StatusRow("Pointer tracking")
        self.row_calibration = StatusRow("Calibration")
        self.row_board = StatusRow("Board")
        self.row_remote = StatusRow("Remote")
        for r in (self.row_camera, self.row_tracking, self.row_calibration, self.row_board, self.row_remote):
            status_lay.addWidget(r)
        self.row_board.set_state("ok", f"{settings.get('board.width')} x {settings.get('board.height')} px")
        self.row_remote.set_state("ok", "Keyboard simulation (Right = Next, Left = Previous)")
        side.addWidget(status_panel)

        recent_panel, self.recent_lay = _panel("Recent files")
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(2)
        self.recent_lay.addLayout(self.recent_box)
        side.addWidget(recent_panel)
        side.addStretch(1)

        state.cameraChanged.connect(self._on_camera)
        state.trackingChanged.connect(self._on_tracking)
        state.calibrationChanged.connect(self.row_calibration.set_state)
        self._on_camera(*state.camera)
        self._on_tracking(*state.tracking)
        self.row_calibration.set_state(*state.calibration)
        self.refresh_recent()

    def set_remote_bindings(self, next_keys, previous_keys) -> None:
        """Home status row: the keys currently standing in for the two remote buttons."""
        self.row_remote.set_state("ok", f"Keyboard: {' / '.join(next_keys)} = Next, {' / '.join(previous_keys)} = Previous")

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _greeting() -> str:
        hour = datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        return f"Good {part}. What will you teach today?"

    def _pill(self, name: str) -> tuple[QFrame, StatusRow]:
        frame = QFrame()
        frame.setObjectName("statusPill")
        row = QHBoxLayout(frame)
        row.setContentsMargins(14, 7, 14, 7)
        status = StatusRow(name)
        status.setMinimumWidth(170)
        row.addWidget(status)
        return frame, status

    def _on_camera(self, state: str, text: str) -> None:
        self.camera_pill[1].set_state(state, text)
        self.row_camera.set_state(state, text)

    def _on_tracking(self, state: str, text: str) -> None:
        self.tracking_pill[1].set_state(state, text)
        self.row_tracking.set_state(state, text)

    def refresh_recent(self) -> None:
        while self.recent_box.count():
            item = self.recent_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        files = self.settings.recent_files()[:5]
        if not files:
            empty = QLabel("Opened and saved images appear here.")
            empty.setObjectName("muted")
            empty.setWordWrap(True)
            self.recent_box.addWidget(empty)
            return
        for path in files:
            p = Path(path)
            btn = QPushButton(f"{p.name}\n{p.parent}")
            btn.setObjectName("recent")
            btn.setToolTip(path)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, f=path: self.openRecentRequested.emit(f))
            self.recent_box.addWidget(btn)
