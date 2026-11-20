"""Presentation-remote input.

How the remote reaches the computer
-----------------------------------
A presentation clicker is a USB (or 2.4 GHz dongle) *HID keyboard*: the
operating system receives ordinary key events.  Most clickers send
    "Next"     -> Page Down   (some: Right arrow or Down)
    "Previous" -> Page Up     (some: Left arrow or Up)
The exact codes depend on the model and on the OpenCV GUI backend, so they
are *measured* with  tools/key_finder.py  and written in config.json
(remote.next_codes / remote.prev_codes).

Mapping required by the project:
    Next      -> LEFT  click at the current pointer position
    Previous  -> RIGHT click at the current pointer position

Two back-ends:
  * "opencv": codes come from cv2.waitKeyEx() -> the projected window must
    have keyboard focus (simple, no extra dependency).
  * "pynput": a global keyboard listener -> works even if another window has
    the focus (pip install pynput).
"""
from __future__ import annotations

import queue
import time
from typing import List, Optional

from ..config import RemoteConfig
from ..events import LEFT, RIGHT


class RemoteInput:
    def __init__(self, cfg: RemoteConfig):
        self.cfg = cfg
        self._q: "queue.Queue[str]" = queue.Queue()
        self._last_t = {LEFT: 0.0, RIGHT: 0.0}
        self._listener = None
        self.last_code: Optional[int] = None     # shown by the debug HUD

    # ---- opencv back-end ---------------------------------------------------------
    def from_key_code(self, code: int) -> Optional[str]:
        """Translate a cv2.waitKeyEx() code into LEFT / RIGHT / None."""
        if code is None or code < 0:
            return None
        if code in self.cfg.next_codes:
            return self._debounced(LEFT)
        if code in self.cfg.prev_codes:
            return self._debounced(RIGHT)
        return None

    # ---- pynput back-end ---------------------------------------------------------
    def start(self) -> None:
        if self.cfg.backend != "pynput":
            return
        try:
            from pynput import keyboard
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("remote.backend = 'pynput' needs:  pip install pynput") from exc

        def name_of(key) -> str:
            if hasattr(key, "char") and key.char:
                return key.char.lower()
            return getattr(key, "name", str(key))

        def on_press(key):
            n = name_of(key)
            if n in self.cfg.next_names:
                self._q.put(LEFT)
            elif n in self.cfg.prev_names:
                self._q.put(RIGHT)

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.daemon = True
        self._listener.start()

    def drain(self) -> List[str]:
        """Buttons pressed since the last call (pynput back-end)."""
        out = []
        while True:
            try:
                b = self._q.get_nowait()
            except queue.Empty:
                return [x for x in out if self._debounced(x)]
            out.append(b)

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()

    # ---- helpers -----------------------------------------------------------------
    def _debounced(self, button: str) -> Optional[str]:
        """Key auto-repeat / double contacts: ignore presses closer than debounce_s."""
        now = time.perf_counter()
        if now - self._last_t[button] < self.cfg.debounce_s:
            return None
        self._last_t[button] = now
        return button
