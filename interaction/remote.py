"""Physical presentation-remote support via ``pynput``.

A two-button presentation remote is a standard HID keyboard: each button
sends a key press (commonly Page_Down / Page_Up, but this varies by
model).  This module listens for *global* key events and translates the
configured keys into click events.

The listener runs on its own thread and pushes events into a thread-safe
queue; the main Pygame loop drains the queue once per frame, so the GUI
thread never blocks on input.

Use ``tools/remote_key_detector.py`` to discover which key names your
remote actually sends, then put them in ``config/settings.json`` under
``remote_keys``.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

logger = logging.getLogger(__name__)


def _key_name(key) -> Optional[str]:
    """Normalise a pynput key object to a lowercase name string."""
    try:
        if hasattr(key, "name") and key.name:
            return str(key.name).lower()
        if hasattr(key, "char") and key.char:
            return str(key.char).lower()
    except Exception:  # noqa: BLE001
        pass
    return None


class RemoteListener:
    """Global keyboard listener that emits left/right click events."""

    def __init__(self, key_map: dict):
        """key_map: {"left": "page_down", "right": "page_up"}"""
        self.key_map = {k: str(v).lower() for k, v in key_map.items()}
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._pressed: set[str] = set()
        self._listener = None
        self._running = False
        self.last_event_time = 0.0
        self.error: Optional[str] = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> bool:
        """Start the global listener thread.  Returns True on success."""
        try:
            from pynput import keyboard
        except ImportError:
            self.error = "pynput is not installed"
            logger.error(self.error)
            return False
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release)
            self._listener.daemon = True
            self._listener.start()
            self._running = True
            logger.info("Remote listener started (keys: %s)", self.key_map)
            return True
        except Exception as exc:  # noqa: BLE001 - e.g. no display on Linux
            self.error = f"Could not start global listener: {exc}"
            logger.error(self.error)
            return False

    def stop(self) -> None:
        self._running = False
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:  # noqa: BLE001
                pass
            self._listener = None

    # -- pynput callbacks --------------------------------------------------

    def _on_press(self, key):
        name = _key_name(key)
        if name is None:
            return
        import time
        self.last_event_time = time.time()
        # Debounce: ignore auto-repeat while the button is held.
        if name in self._pressed:
            return
        self._pressed.add(name)
        for button, configured in self.key_map.items():
            if name == configured:
                self._queue.put(button)
                return

    def _on_release(self, key):
        name = _key_name(key)
        if name is not None:
            self._pressed.discard(name)

    # -- main-thread API ---------------------------------------------------

    def poll(self) -> list[str]:
        """Drain pending click events.  Called once per frame."""
        events = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    @property
    def is_running(self) -> bool:
        return self._running
