"""Event manager: unified click-event source for the whole application.

Merges two input paths into one interface:

  * physical remote  -> RemoteListener (pynput, global, threaded)
  * keyboard sim     -> KeyboardSimulator (Pygame events, window-focused)

The app calls ``poll()`` once per frame and receives a list of button
names ("left" / "right") that were pressed since the last frame.  Clicks
are dispatched to the current screen together with the current pointer
position, so screens never care where the click came from.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import pygame

from interaction.keyboard_simulator import KeyboardSimulator
from interaction.remote import RemoteListener

logger = logging.getLogger(__name__)


class EventManager:
    def __init__(self, settings: dict):
        self.settings = settings
        self.simulator = KeyboardSimulator(settings.get("sim_keys",
                                                         {"left": "z",
                                                          "right": "x"}))
        self.remote: Optional[RemoteListener] = None
        self.remote_enabled = False
        self._sim_enabled = True   # keyboard sim is always available as fallback

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        """Start the physical remote listener if configured/enabled."""
        mode = self.settings.get("remote_mode", "auto")
        if mode in ("physical", "auto"):
            self.remote = RemoteListener(self.settings.get("remote_keys", {}))
            if self.remote.start():
                self.remote_enabled = True
            elif mode == "physical":
                logger.warning("Physical remote requested but listener failed; "
                               "falling back to keyboard simulation.")
        logger.info("Input mode: remote=%s sim=%s",
                    self.remote_enabled, self._sim_enabled)

    def stop(self):
        if self.remote is not None:
            self.remote.stop()

    # -- per-frame ---------------------------------------------------------

    def poll(self) -> list[str]:
        """Return click buttons pressed since the last call.

        Pygame events must already have been pumped (pygame.event.pump()
        happens in the main loop before this call).
        """
        events: list[str] = []
        # Physical remote (thread-safe queue).
        if self.remote_enabled and self.remote is not None:
            events.extend(self.remote.poll())
        # Keyboard simulation: scan this frame's key events.  We re-scan
        # pygame.event.get() is NOT possible here (events are consumed by
        # the app loop), so the app forwards KEYDOWN events via
        # ``handle_pygame_event`` instead -- see app.py.
        return events

    def handle_pygame_event(self, event: pygame.event.Event) -> Optional[str]:
        """Forward a Pygame event to the keyboard simulator."""
        if not self._sim_enabled:
            return None
        return self.simulator.handle_event(event)

    # -- status ------------------------------------------------------------

    @property
    def remote_active(self) -> bool:
        """True if the physical remote produced an event recently."""
        if self.remote is None:
            return False
        return (time.time() - self.remote.last_event_time) < 5.0
