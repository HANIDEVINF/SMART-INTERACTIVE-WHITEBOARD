"""Smart Interactive Whiteboard -- main application.

Owns every subsystem and runs the Pygame event loop:

    camera thread -> detector -> homography -> tracker -> pointer position
    remote/keyboard -> click events -> current screen

Launch with:  python main.py
"""

from __future__ import annotations

import logging
import time

import pygame

# Project imports
from calibration.calibration_manager import CalibrationManager
from calibration.calibration_ui import BoardCalibrationScreen, HSVCalibrationScreen
from camera.camera_manager import CameraManager
from config.settings import load_settings
from detection.color_detector import ColorDetector
from detection.tracker import PointerTracker
from detection.worker import DetectionWorker
from interaction.event_manager import EventManager
from interface.components import COLORS, FONT_S, STATUS_H
from interface.drawing import DrawingScreen
from interface.image_viewer import ImageViewerScreen
from interface.lesson import LessonScreen
from interface.menus import HelpScreen, build_menus
from interface.settings_screen import SettingsScreen
from simulation.simulated_pointer import SimulatedPointer
from utils.file_utils import ensure_dirs

logger = logging.getLogger(__name__)

# A detected marker may sit slightly outside the calibrated board; beyond
# this margin (board pixels) it is treated as "not on the board".
BOARD_MARGIN = 40
FLASH_SECONDS = 0.4


class SmartBoardApp:
    def __init__(self):
        ensure_dirs()
        self.settings = load_settings()
        self._restart_requested = False
        self._quit_requested = False
        self.width = int(self.settings["display_width"])
        self.height = int(self.settings["display_height"])

        # --- display -------------------------------------------------------
        flags = pygame.FULLSCREEN if self.settings.get("fullscreen") else 0
        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        pygame.display.set_caption("Smart Interactive Whiteboard")
        self.clock = pygame.time.Clock()

        # --- subsystems ----------------------------------------------------
        self.camera = CameraManager(self.settings)
        self.detector = ColorDetector(
            self.settings["marker_hsv"],
            min_area=int(self.settings.get("marker_min_area", 400)),
            max_area_ratio=float(self.settings.get("marker_max_area_ratio",
                                                   0.25)))
        self.tracker = PointerTracker(
            alpha=float(self.settings.get("tracking_alpha", 0.45)),
            max_jump=float(self.settings.get("tracking_max_jump", 250.0)),
            loss_timeout=float(self.settings.get("tracking_loss_timeout",
                                                 1.5)))
        self.worker = DetectionWorker(self.camera, self.detector)
        self.calibration = CalibrationManager((self.width, self.height))
        self.events = EventManager(self.settings)
        self.mouse_pointer = SimulatedPointer()

        # --- state ---------------------------------------------------------
        self.pointer_pos = None          # (x, y) board coords or None
        self.pointer_visible = False
        self.pointer_source = "none"     # "camera" | "mouse" | "none"
        self.last_frame = None           # latest BGR frame (for screens)
        self.last_detection = None       # latest raw Detection (camera px)
        self._last_frame_id = 0
        self.click_flashes: list[tuple] = []   # (pos, button, t0)
        self.screen_stack: list[str] = []
        self.current_screen_name = "menu"

        # --- screens -------------------------------------------------------
        self.screens = build_menus(self)
        self.screens.update({
            "lesson": LessonScreen(self),
            "drawing": DrawingScreen(self),
            "image": ImageViewerScreen(self),
            "calibration": BoardCalibrationScreen(self),
            "hsv_calib": HSVCalibrationScreen(self),
            "settings": SettingsScreen(self),
            "help": HelpScreen(self),
        })

        # --- startup -------------------------------------------------------
        self.camera_ok = self.camera.open()
        if not self.camera_ok:
            logger.warning("Camera unavailable: %s", self.camera.last_error)
        else:
            self.worker.start()
        self.calibration.load_saved()
        self.events.start()

    # ------------------------------------------------------------------
    # Screen navigation
    # ------------------------------------------------------------------

    @property
    def current_screen(self):
        return self.screens[self.current_screen_name]

    def go_to(self, name: str) -> None:
        if name not in self.screens:
            logger.warning("Unknown screen: %s", name)
            return
        if name == self.current_screen_name:
            return
        self.screen_stack.append(self.current_screen_name)
        self.current_screen_name = name
        logger.info("Screen -> %s", name)
        self.current_screen.on_enter()

    def go_back(self) -> None:
        if self.screen_stack:
            self.current_screen_name = self.screen_stack.pop()
            self.current_screen.on_enter()

    def go_home(self) -> None:
        """Return to the main menu from anywhere."""
        self.screen_stack.clear()
        self.current_screen_name = "menu"
        self.current_screen.on_enter()

    def quit(self) -> None:
        self._quit_requested = True

    def request_restart(self) -> None:
        self._restart_requested = True

    # ------------------------------------------------------------------
    # Pointer pipeline
    # ------------------------------------------------------------------

    def _camera_pointer(self):
        """Fetch the latest detection from the worker thread and return the
        smoothed board-space point, or None when the marker is lost."""
        self.last_frame, _ = self.camera.read_latest()
        frame_id, det = self.worker.latest()
        if frame_id == 0 or frame_id == self._last_frame_id:
            # No new result this tick: keep the tracker's current estimate
            # (it handles the loss timeout itself).
            return self.tracker.current()
        self._last_frame_id = frame_id
        self.last_detection = det

        board_point = None
        if det is not None and self.calibration.mapper.is_calibrated:
            x, y = self.calibration.mapper.camera_to_board((det.x, det.y))
            m = BOARD_MARGIN
            if -m <= x <= self.width + m and -m <= y <= self.height + m:
                board_point = (min(max(x, 0.0), self.width - 1.0),
                               min(max(y, 0.0), self.height - 1.0))
        return self.tracker.update(board_point)

    def _update_pointer(self) -> None:
        """One frame of the pointer pipeline."""
        smoothed = self._camera_pointer()

        mode = self.settings.get("pointer_mode", "auto")
        mouse_pos = self.mouse_pointer.read()

        if mode == "mouse":
            self.pointer_pos, self.pointer_source = mouse_pos, "mouse"
        elif mode == "camera":
            self.pointer_pos = smoothed
            self.pointer_source = "camera" if smoothed is not None else "none"
        else:  # auto: prefer camera, fall back to mouse
            if smoothed is not None:
                self.pointer_pos, self.pointer_source = smoothed, "camera"
            else:
                self.pointer_pos, self.pointer_source = mouse_pos, "mouse"

        self.pointer_visible = self.pointer_pos is not None

    # ------------------------------------------------------------------
    # Input dispatch
    # ------------------------------------------------------------------

    def _collect_clicks(self) -> list[tuple[str, tuple[float, float]]]:
        """Gather (button, position) click events for this frame."""
        clicks = []
        pos = self.pointer_pos if self.pointer_visible else None

        # Physical remote (global listener).
        for button in self.events.poll():
            if pos is not None:
                clicks.append((button, pos))

        raw_mouse = getattr(self.current_screen, "raw_mouse", False)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.go_back()
                    continue
                button = self.events.handle_pygame_event(event)
                if button and pos is not None:
                    clicks.append((button, pos))
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Only the real left/right buttons: the scroll wheel also
                # produces MOUSEBUTTONDOWN (buttons 4/5) and must not click.
                if event.button not in (1, 3):
                    continue
                name = "left" if event.button == 1 else "right"
                if raw_mouse:
                    # Calibration screens: the operator clicks the camera
                    # image with the real mouse, whatever the pointer mode.
                    clicks.append((name, event.pos))
                elif self.pointer_source == "mouse" and pos is not None:
                    clicks.append((name, pos))
        return clicks

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _draw_status_bar(self) -> None:
        s = self.screen
        w, h = self.width, self.height
        y = h - STATUS_H
        pygame.draw.rect(s, COLORS["toolbar"], (0, y, w, STATUS_H))
        pygame.draw.line(s, COLORS["border"], (0, y), (w, y), 1)

        if self.camera_ok:
            cam_txt = f"CAM OK {self.camera.fps:.0f}fps"
            cam_color = COLORS["success"]
        else:
            cam_txt, cam_color = "CAM ERR", COLORS["danger"]
        calibrated = self.calibration.mapper.is_calibrated
        cal_txt = "BOARD CALIBRATED" if calibrated else "NOT CALIBRATED"
        cal_color = COLORS["success"] if calibrated else COLORS["warn"]
        rem_txt = "REMOTE" if self.events.remote_active else "KEYS Z/X"
        ptr_txt = {"camera": "POINTER: CAMERA", "mouse": "POINTER: MOUSE",
                   "none": "POINTER: LOST"}[self.pointer_source]
        ptr_color = COLORS["success"] if self.pointer_visible else COLORS["warn"]

        items = [
            ("HOME" if self.current_screen_name == "menu"
             else self.current_screen.title.upper(), COLORS["text"]),
            (cam_txt, cam_color),
            (cal_txt, cal_color),
            (rem_txt, COLORS["text_dim"]),
            (ptr_txt, ptr_color),
        ]
        x = 12
        for text, color in items:
            surf = FONT_S.render(text, True, color)
            s.blit(surf, (x, y + (STATUS_H - surf.get_height()) // 2))
            x += surf.get_width() + 26
        fps = FONT_S.render(f"UI {self.clock.get_fps():.0f} fps", True,
                            COLORS["text_dim"])
        s.blit(fps, (w - fps.get_width() - 12,
                     y + (STATUS_H - fps.get_height()) // 2))

    def _draw_pointer(self) -> None:
        s = self.screen
        now = time.time()

        # Click feedback: an expanding ring at the click position.
        alive = []
        for pos, button, t0 in self.click_flashes:
            age = now - t0
            if age < FLASH_SECONDS:
                k = age / FLASH_SECONDS
                color = COLORS["success"] if button == "left" else COLORS["warn"]
                pygame.draw.circle(s, color, (int(pos[0]), int(pos[1])),
                                   int(18 + 40 * k), max(1, int(5 * (1 - k))))
                alive.append((pos, button, t0))
        self.click_flashes = alive

        if not self.pointer_visible:
            return
        x, y = int(self.pointer_pos[0]), int(self.pointer_pos[1])
        # Two-tone ring so the pointer is visible on light AND dark boards.
        pygame.draw.circle(s, (10, 12, 20), (x, y), 18, 6)
        pygame.draw.circle(s, COLORS["accent"], (x, y), 18, 3)
        pygame.draw.circle(s, (10, 12, 20), (x, y), 7)
        pygame.draw.circle(s, COLORS["accent"], (x, y), 5)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def step(self, dt: float) -> None:
        """One iteration of the main loop (also used by the tests)."""
        self._update_pointer()
        clicks = self._collect_clicks()

        screen = self.current_screen
        if self.pointer_visible:
            screen.on_hover(self.pointer_pos)
        for button, pos in clicks:
            self.click_flashes.append((pos, button, time.time()))
            screen.on_click(pos, button)
            screen = self.current_screen   # a click may change the screen

        screen.update(dt)
        screen.draw()
        self._draw_status_bar()
        self._draw_pointer()
        pygame.display.flip()

    def run(self) -> None:
        logger.info("Smart Whiteboard starting")
        while not self._quit_requested and not self._restart_requested:
            dt = self.clock.tick(60) / 1000.0
            self.step(dt)
        self._shutdown()

    def _shutdown(self) -> None:
        """Release devices.  Does NOT quit Pygame: a restart re-creates the
        app in the same process and needs Pygame (and its fonts) alive."""
        logger.info("Shutting down")
        self.events.stop()
        self.worker.stop()
        self.camera.release()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    pygame.init()
    try:
        while True:
            app = SmartBoardApp()
            app.run()
            if not app._restart_requested:
                break
            logger.info("Restarting application (new settings)")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
