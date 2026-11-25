"""Main window: dark navigation sidebar + stacked pages + toast notifications + fullscreen."""
from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from core.app_state import AppState
from core.detector import DetectionParams
from core.remote_control import RemoteController, RemoteMapper
from core.settings import Settings
from core.tracker import TrackerParams
from core.vision_engine import VisionController
from ui import brand, icons
from ui.calibration_page import CalibrationPage
from ui.camera_page import CameraPage
from ui.coming_soon import ComingSoonPage
from ui.dashboard import Dashboard
from ui.settings_page import SettingsPage
from ui.styles import APP_NAME, APP_TAGLINE, TEAL
from ui.whiteboard import WhiteboardPage
from ui.widgets import StatusRow, Toast

# (page id, label, icon, phase badge or None)
NAV_ITEMS = [
    ("home", "Home", "home", None),
    ("whiteboard", "Whiteboard", "pen", None),
    ("teaching", "Teaching", "teaching", "Phase 6"),
    ("calibration", "Calibration", "calibrate", None),
    ("camera", "Camera", "camera", None),
    ("settings", "Settings", "settings", None),
]

CAMERA_PAGES = ("camera", "calibration", "settings")   # pages that need the live camera
CAMERA_IDLE_GRACE_MS = 20_000                          # keep the camera warm this long after it is not needed


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, state: AppState, controller: VisionController | None = None) -> None:
        super().__init__()
        self.settings, self.state = settings, state
        # the calibration file lives next to the settings file (so tests with a temp settings file stay isolated)
        self.controller = controller or VisionController(
            settings, state, calibration_path=settings.path.with_name("calibration.json"))
        self.current_page = "home"
        # two-button remote (keyboard simulation): an application-wide key filter, active on the whiteboard only
        self.remote = RemoteController(self._build_mapper(settings), parent=self)
        self._idle_stopped = False        # True when the camera was stopped by the idle timer (not by the user)
        self.setWindowTitle(f"{APP_NAME} - {APP_TAGLINE}")
        self.setWindowIcon(brand.app_icon())
        self.setMinimumSize(1100, 700)
        self.resize(int(settings.get("app.window_width", 1360)), int(settings.get("app.window_height", 840)))

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        layout.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # ---- pages ---------------------------------------------------------------------
        self.dashboard = Dashboard(settings, state)
        self.whiteboard = WhiteboardPage(settings)
        self.pages: dict[str, QWidget] = {
            "home": self.dashboard,
            "whiteboard": self.whiteboard,
            "teaching": ComingSoonPage(
                "teaching", "Teaching Mode", "Phase 6",
                "Organise a lesson as editable pages and present it on the board.",
                ["Lesson pages with titles, text and images", "Previous / Next navigation with page numbers",
                 "Annotate any page, then return to the menu", "A ready-made demonstration lesson"], TEAL),
            "calibration": CalibrationPage(settings, self.controller),
            "camera": CameraPage(self.controller),
            "settings": SettingsPage(settings, self.controller, self.remote),
        }
        self._index: dict[str, int] = {}
        for page_id, page in self.pages.items():
            self._index[page_id] = self.stack.addWidget(page)
            if isinstance(page, ComingSoonPage):
                page.homeRequested.connect(lambda: self.navigate("home"))

        self.toast = Toast(root)

        # ---- wiring --------------------------------------------------------------------
        self.dashboard.navigate.connect(self.navigate)
        self.dashboard.openImageRequested.connect(self._open_image_from_home)
        self.dashboard.openRecentRequested.connect(self._open_recent)
        self.whiteboard.homeRequested.connect(lambda: self.navigate("home"))
        self.whiteboard.fullscreenRequested.connect(self.toggle_fullscreen)
        self.whiteboard.set_remote(self.remote)
        self.whiteboard.navigateRequested.connect(self._on_menu_navigate)
        self.remote.install()
        self.remote.bindingsChanged.connect(self._show_bindings)
        self._show_bindings()
        self.whiteboard.message.connect(self.toast.show_message)
        self.whiteboard.recentChanged.connect(self.dashboard.refresh_recent)
        state.cameraChanged.connect(lambda s, t: self.side_camera.set_state(s, t))
        state.trackingChanged.connect(lambda s, t: self.side_tracking.set_state(s, t))
        self.side_camera.set_state(*state.camera)
        self.side_tracking.set_state(*state.tracking)

        # ---- computer vision <-> pages -------------------------------------------------------
        ctl = self.controller
        self.whiteboard.trackingToggled.connect(self._on_whiteboard_tracking)
        ctl.resultReady.connect(self.whiteboard.show_vision_result)
        ctl.signalLost.connect(lambda: self.whiteboard.clear_tracking("Camera signal lost"))
        ctl.cameraStatusChanged.connect(self._on_camera_status)
        settings_page: SettingsPage = self.pages["settings"]
        settings_page.message.connect(self.toast.show_message)
        settings_page.pointerVisibilityChanged.connect(self.whiteboard.set_pointer_visible)
        settings_page.resetRequested.connect(self.reset_application)
        settings_page.dwellChanged.connect(self.whiteboard.set_dwell_ms)
        self._camera_idle_timer = QTimer(self)
        self._camera_idle_timer.setSingleShot(True)
        self._camera_idle_timer.setInterval(CAMERA_IDLE_GRACE_MS)
        self._camera_idle_timer.timeout.connect(self._stop_idle_camera)

        for seq, fn in (("F11", self.toggle_fullscreen), ("Esc", self._escape),
                        ("Ctrl+H", lambda: self.navigate("home")),
                        ("Ctrl+1", lambda: self.navigate("home")),
                        ("Ctrl+2", lambda: self.navigate("whiteboard"))):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(fn)

        self.navigate("home", animate=False)
        if settings.load_error:
            QTimer.singleShot(400, lambda: self.toast.show_message(settings.load_error, "warn", 5000))

    # ------------------------------------------------------------------ sidebar
    def _build_sidebar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("sidebar")
        bar.setFixedWidth(236)
        col = QVBoxLayout(bar)
        col.setContentsMargins(16, 22, 16, 18)
        col.setSpacing(4)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(11)
        logo = QLabel()
        logo.setPixmap(brand.logo_pixmap(42))
        names = QVBoxLayout()
        names.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setObjectName("brandName")
        tag = QLabel("Smart whiteboard")
        tag.setObjectName("brandTag")
        names.addWidget(name)
        names.addWidget(tag)
        brand_row.addWidget(logo)
        brand_row.addLayout(names)
        brand_row.addStretch(1)
        col.addLayout(brand_row)
        col.addSpacing(26)

        caption = QLabel("WORKSPACE")
        caption.setObjectName("sidebarCaption")
        col.addWidget(caption)
        col.addSpacing(4)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: dict[str, QPushButton] = {}
        for page_id, label, icon_name, phase in NAV_ITEMS:
            btn = QPushButton("  " + label)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setProperty("soon", phase is not None)
            btn.setIcon(icons.icon(icon_name, "#8E97C8", 20, on_color="#FFFFFF"))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{label} (available in {phase})" if phase else label)
            btn.clicked.connect(lambda _=False, pid=page_id: self.navigate(pid))
            self._nav_group.addButton(btn)
            self._nav_buttons[page_id] = btn
            col.addWidget(btn)

        col.addStretch(1)
        caption2 = QLabel("STATUS")
        caption2.setObjectName("sidebarCaption")
        col.addWidget(caption2)
        col.addSpacing(4)
        self.side_camera = StatusRow("Camera", dark=True)
        self.side_tracking = StatusRow("Tracking", dark=True)
        col.addWidget(self.side_camera)
        col.addWidget(self.side_tracking)
        col.addSpacing(12)
        foot = QLabel("v0.1  -  USTHB 2026-2027")
        foot.setObjectName("sidebarFoot")
        col.addWidget(foot)
        return bar

    # --------------------------------------------------------------- navigation
    def navigate(self, page_id: str, animate: bool = True) -> None:
        if page_id not in self._index:
            return
        if page_id != "whiteboard":
            self.whiteboard.cancel_in_progress()
        if page_id != self.current_page:                  # page lifecycle: deactivate old, activate new
            leaving = self.pages.get(self.current_page)
            if hasattr(leaving, "deactivate"):
                leaving.deactivate()
        self.current_page = page_id
        self.remote.set_enabled(page_id == "whiteboard")   # arrow keys keep their normal meaning elsewhere
        self.stack.setCurrentIndex(self._index[page_id])
        self._nav_buttons[page_id].setChecked(True)
        if animate:
            self._fade_in(self.pages[page_id])
        if page_id == "whiteboard":
            self.whiteboard.canvas.setFocus()
        entering = self.pages[page_id]
        if hasattr(entering, "activate"):
            entering.activate()
        self._update_camera_demand()

    @staticmethod
    def _build_mapper(settings: Settings) -> RemoteMapper:
        try:
            return RemoteMapper(settings.get("remote.next_keys"), settings.get("remote.previous_keys"),
                                int(settings.get("remote.debounce_ms", 250)))
        except (ValueError, TypeError):
            return RemoteMapper()                         # corrupt / conflicting settings: use the defaults

    def _show_bindings(self) -> None:
        self.dashboard.set_remote_bindings(self.remote.mapper.next_keys[:1], self.remote.mapper.previous_keys[:1])

    def _on_menu_navigate(self, target: str) -> None:
        """A menu item asked for another page ('remote' opens Settings on the remote tab)."""
        if target == "remote":
            self.navigate("settings")
            self.pages["settings"].show_remote_tab()
        else:
            self.navigate(target)

    # --------------------------------------------------------------- camera lifecycle
    def _camera_wanted(self) -> bool:
        return self.current_page in CAMERA_PAGES or self.whiteboard.tracking_enabled

    def _update_camera_demand(self) -> None:
        """Start the webcam when a page needs it; stop it (after a grace period) when nothing does.

        The camera is not opened on Home: its LED stays off and no CPU is spent until it is needed.
        Pressing *Stop camera* on the Camera page is respected: pages do not restart it behind your back.
        """
        ctl = self.controller
        if self._camera_wanted():
            self._camera_idle_timer.stop()
            user_stopped = ctl.camera_state[1] == "Stopped" and not self._idle_stopped
            if not ctl.running and bool(self.settings.get("camera.autostart", True)) and not user_stopped:
                self._idle_stopped = False
                ctl.start()
        elif ctl.running and not self._camera_idle_timer.isActive():
            self._camera_idle_timer.start()

    def _stop_idle_camera(self) -> None:
        if not self._camera_wanted() and self.controller.running:
            self.controller.stop()
            self._idle_stopped = True

    def _on_whiteboard_tracking(self, on: bool) -> None:
        ctl = self.controller
        if on:
            self._camera_idle_timer.stop()
            if not ctl.running:                           # an explicit request overrides auto-start settings
                self._idle_stopped = False
                ctl.start()
            if ctl.calibration is None:
                self.toast.show_message("Not calibrated yet - open Calibration to map the pointer onto the board",
                                        "warn", 4200)
        else:
            self._update_camera_demand()

    def _on_camera_status(self, state: str, _text: str) -> None:
        if state != "ok":
            self.whiteboard.clear_tracking({"error": "Camera unavailable", "warn": "Connecting to camera...",
                                            "off": "Camera off"}.get(state, "Camera off"))

    # --------------------------------------------------------------- reset application
    def reset_application(self) -> None:
        """Factory-reset settings and the whiteboard. The camera choice, mirror flag and the saved
        calibration are kept (the calibration is only valid for them)."""
        ctl = self.controller
        keep = {k: self.settings.get(k) for k in ("camera.index", "camera.mirror")}
        self.settings.reset()
        for key, value in keep.items():
            self.settings.set(key, value)
        ctl.set_detection_params(DetectionParams.from_settings(self.settings))
        ctl.set_tracker_params(TrackerParams.from_settings(self.settings))
        self.whiteboard.reset()
        self.whiteboard._restore_pen_settings()
        self.whiteboard.set_pointer_visible(bool(self.settings.get("pointer.visible", True)))
        self.remote.mapper = self._build_mapper(self.settings)
        self.remote.bindingsChanged.emit()
        self.whiteboard.interaction.set_dwell_ms(int(self.settings.get("interaction.dwell_ms", 1200)))
        self.whiteboard.set_mode(str(self.settings.get("interaction.mode", "navigation")), announce=False)
        self.pages["settings"].load_from_controller()
        self.dashboard.refresh_recent()
        self.settings.save()
        if ctl.running:
            ctl.restart()                                 # the default resolution may differ
        self.toast.show_message("Application reset to factory settings", "success")

    def _fade_in(self, widget: QWidget) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(170)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(lambda: QTimer.singleShot(0, lambda: widget.setGraphicsEffect(None)))
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _open_image_from_home(self) -> None:
        if self.whiteboard.open_image_dialog():
            self.navigate("whiteboard")

    def _open_recent(self, path: str) -> None:
        if self.whiteboard.open_path(path):
            self.navigate("whiteboard")

    # --------------------------------------------------------------- fullscreen
    def toggle_fullscreen(self) -> None:
        self.set_fullscreen(not self.isFullScreen())

    def set_fullscreen(self, on: bool) -> None:
        if on:
            self.showFullScreen()
        else:
            self.showNormal()
        self.sidebar.setVisible(not on)
        self.whiteboard.set_fullscreen_state(on)
        QTimer.singleShot(0, self.toast.reposition)

    def _escape(self) -> None:
        if self.whiteboard.cancel_in_progress():
            return
        if self.current_page == "whiteboard" and self.whiteboard.close_menu():
            return
        if self.isFullScreen():
            self.set_fullscreen(False)

    # ------------------------------------------------------------------- events
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.toast.reposition()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self.isFullScreen():
            self.settings.set("app.window_width", self.width())
            self.settings.set("app.window_height", self.height())
        self.whiteboard.save_pen_settings()
        self._camera_idle_timer.stop()
        self.remote.uninstall()
        self.controller.shutdown()                        # stops both worker threads, then saves settings
        super().closeEvent(event)
