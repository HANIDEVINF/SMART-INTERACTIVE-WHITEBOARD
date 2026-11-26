"""Two-button remote control, simulated by the keyboard.

The project's remote has two buttons:

    Next      -> LEFT  mouse click at the current pointer position
    Previous  -> RIGHT mouse click at the current pointer position

Until the physical remote exists, two keyboard keys stand in for it (default: Right arrow = Next, Left arrow = Previous;
PageDown / PageUp are also accepted because presentation clickers send exactly those codes).  Because the real
remote may send other codes, the module contains a *key diagnostic mode* that records the name, Qt key code, the
native Windows virtual-key code and the scan code of every key press, so the real codes can be identified and
documented, then bound in Settings > Remote.

Layers (so that the logic is testable without any window):

* :class:`RemoteMapper`  - pure logic: key name -> NEXT / PREVIOUS, with auto-repeat suppression and debounce.
* :class:`KeyLog`        - ring buffer of :class:`KeyRecord` (what the diagnostic mode shows and saves).
* :class:`RemoteController` - QObject installed as an application-wide event filter; turns real key events into
  the ``nextTriggered`` / ``previousTriggered`` signals.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QTextEdit

DEFAULT_NEXT_KEYS = ("Right", "PgDown")
DEFAULT_PREVIOUS_KEYS = ("Left", "PgUp")
DEFAULT_DEBOUNCE_MS = 250

_MODIFIER_KEYS = {Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
                  Qt.Key.Key_CapsLock, Qt.Key.Key_NumLock, Qt.Key.Key_ScrollLock}


class RemoteAction(str, Enum):
    NEXT = "NEXT"          # = left click
    PREVIOUS = "PREVIOUS"  # = right click

    @property
    def click(self) -> str:
        return "left" if self is RemoteAction.NEXT else "right"


_ALIASES = {"pagedown": "PgDown", "page down": "PgDown", "pageup": "PgUp", "page up": "PgUp", "escape": "Esc",
            "spacebar": "Space"}


def normalize_key_name(name: str) -> str:
    """Canonical Qt spelling of a key ("PageDown" -> "PgDown", "right" -> "Right"); "" if unknown."""
    name = (name or "").strip()
    if not name:
        return ""
    name = _ALIASES.get(name.lower(), name)
    seq = QKeySequence.fromString(name, QKeySequence.SequenceFormat.PortableText)
    if seq.count() != 1 or seq[0].key() == Qt.Key.Key_unknown:
        return ""
    return seq.toString(QKeySequence.SequenceFormat.PortableText)


def key_name(qt_key: int, modifiers: int = 0) -> str:
    """Readable name of a Qt key, without modifiers ("Right", "PgDown", "F5", "A", "Space")."""
    if qt_key == Qt.Key.Key_unknown:
        return "Unknown"
    return QKeySequence(int(qt_key)).toString(QKeySequence.SequenceFormat.PortableText) or f"0x{int(qt_key):X}"


# ---------------------------------------------------------------------------------------------------------------
# pure logic
# ---------------------------------------------------------------------------------------------------------------
class RemoteMapper:
    """Maps key names to remote actions.

    * Auto-repeat events (key held down) never trigger anything.
    * Debounce: a second trigger of the *same* action within ``debounce_ms`` is ignored (contact bounce of a real
      remote, or a double tap).  NEXT and PREVIOUS are debounced independently so that a quick Next then Previous works.
    * A key cannot be bound to both actions.
    """

    def __init__(self, next_keys: Iterable[str] = DEFAULT_NEXT_KEYS, previous_keys: Iterable[str] = DEFAULT_PREVIOUS_KEYS,
                 debounce_ms: int = DEFAULT_DEBOUNCE_MS) -> None:
        self.next_keys: tuple[str, ...] = ()
        self.previous_keys: tuple[str, ...] = ()
        self.debounce_ms = DEFAULT_DEBOUNCE_MS
        self._last: dict[RemoteAction, float] = {}
        self.last_reason = ""
        self.configure(next_keys, previous_keys, debounce_ms)

    def configure(self, next_keys: Iterable[str], previous_keys: Iterable[str], debounce_ms: int) -> None:
        nxt = tuple(dict.fromkeys(k for k in (normalize_key_name(k) for k in next_keys) if k))
        prv = tuple(dict.fromkeys(k for k in (normalize_key_name(k) for k in previous_keys) if k))
        clash = set(nxt) & set(prv)
        if clash:
            raise ValueError(f"The key(s) {', '.join(sorted(clash))} cannot be both Next and Previous")
        if not nxt or not prv:
            raise ValueError("Both Next and Previous need at least one key")
        self.next_keys, self.previous_keys = nxt, prv
        self.debounce_ms = max(0, int(debounce_ms))
        self._last.clear()

    def action_for(self, name: str) -> RemoteAction | None:
        name = normalize_key_name(name)
        if name in self.next_keys:
            return RemoteAction.NEXT
        if name in self.previous_keys:
            return RemoteAction.PREVIOUS
        return None

    def map(self, name: str, auto_repeat: bool = False, now_ms: float | None = None) -> RemoteAction | None:
        """Return the action to perform for this key press, or None (and set ``last_reason``)."""
        action = self.action_for(name)
        if action is None:
            self.last_reason = "not a remote key"
            return None
        if auto_repeat:
            self.last_reason = "auto-repeat ignored"
            return None
        now = time.monotonic() * 1000.0 if now_ms is None else now_ms
        last = self._last.get(action)
        if last is not None and 0 <= now - last < self.debounce_ms:
            self.last_reason = "debounced"
            return None
        self._last[action] = now
        self.last_reason = "ok"
        return action


@dataclass
class KeyRecord:
    """One keyboard event as shown by the diagnostic mode."""
    time_s: float            # seconds since the log started
    event: str               # "press" | "release"
    name: str                # Qt name, e.g. "Right", "PgDown"
    qt_key: int              # Qt::Key value, e.g. 0x01000014
    native_vk: int           # Windows virtual-key code (e.g. 0x27 for Right), 0 if not available
    scan_code: int           # hardware scan code
    modifiers: str           # "Ctrl+Shift" or ""
    text: str                # printable text, "" for non-printing keys
    auto_repeat: bool
    result: str = "-"        # what the app did: NEXT / PREVIOUS / "debounced" / "auto-repeat ignored" / "-"

    def line(self) -> str:
        mod = f" +{self.modifiers}" if self.modifiers else ""
        rep = " (repeat)" if self.auto_repeat else ""
        txt = f" text={self.text!r}" if self.text and self.text.isprintable() else ""
        return (f"{self.time_s:8.3f}s  {self.event:<7} {self.name:<10} qt=0x{self.qt_key:08X}  "
                f"vk=0x{self.native_vk:02X} ({self.native_vk})  scan={self.scan_code}{mod}{txt}{rep}  -> {self.result}")


class KeyLog:
    """Bounded record of keyboard events with plain-text / CSV export."""

    def __init__(self, max_records: int = 500) -> None:
        self._records: deque[KeyRecord] = deque(maxlen=max_records)
        self.started = time.monotonic()

    def add(self, record: KeyRecord) -> None:
        self._records.append(record)

    def clear(self) -> None:
        self._records.clear()
        self.started = time.monotonic()

    def __len__(self) -> int:
        return len(self._records)

    @property
    def records(self) -> list[KeyRecord]:
        return list(self._records)

    def presses(self) -> list[KeyRecord]:
        return [r for r in self._records if r.event == "press" and not r.auto_repeat]

    def to_text(self) -> str:
        head = ["LuminaBoard key diagnostics", "time        event   key        qt code        vk (win)   scan", "-" * 78]
        return "\n".join(head + [r.line() for r in self._records]) + "\n"

    def summary(self) -> str:
        """Distinct keys pressed, with their codes - the table to copy into the report."""
        seen: dict[tuple, KeyRecord] = {}
        for r in self.presses():
            seen.setdefault((r.name, r.qt_key, r.native_vk, r.scan_code), r)
        if not seen:
            return "No key pressed yet."
        rows = ["Key        Qt key code    Windows VK   Scan code"]
        for (name, qt, vk, scan) in seen:
            rows.append(f"{name:<10} 0x{qt:08X}   0x{vk:02X} ({vk:>3})   {scan}")
        return "\n".join(rows)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_text() + "\nDistinct keys:\n" + self.summary() + "\n", encoding="utf-8")
        return path


# ---------------------------------------------------------------------------------------------------------------
# Qt side
# ---------------------------------------------------------------------------------------------------------------
def _modifier_text(mods) -> str:
    parts = []
    for flag, label in ((Qt.KeyboardModifier.ControlModifier, "Ctrl"), (Qt.KeyboardModifier.ShiftModifier, "Shift"),
                        (Qt.KeyboardModifier.AltModifier, "Alt"), (Qt.KeyboardModifier.MetaModifier, "Meta")):
        if mods & flag:
            parts.append(label)
    return "+".join(parts)


class RemoteController(QObject):
    """Application-wide key filter that turns the two remote keys into ``nextTriggered`` / ``previousTriggered``.

    ``enabled``      the remote acts only while True (the whiteboard page turns it on; elsewhere the arrow keys keep
                     their normal meaning).
    ``diagnostics``  every key is recorded in ``log`` and *no* action is performed, so the physical remote can be
                     tested safely.
    ``capture``      the next key press is delivered to a callback (used by the "rebind" buttons) and swallowed.
    """

    nextTriggered = Signal()
    previousTriggered = Signal()
    keyLogged = Signal(object)         # KeyRecord
    bindingsChanged = Signal()
    captured = Signal(str)             # key name captured for rebinding

    def __init__(self, mapper: RemoteMapper | None = None, parent: QObject | None = None,
                 clock: Callable[[], float] | None = None) -> None:
        super().__init__(parent)
        self.mapper = mapper or RemoteMapper()
        self.log = KeyLog()
        self._enabled = False
        self._diagnostics = False
        self._capturing = False
        self._clock = clock or (lambda: time.monotonic() * 1000.0)
        self._installed = False
        self.counts = {RemoteAction.NEXT: 0, RemoteAction.PREVIOUS: 0}

    # -- state ----------------------------------------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, on: bool) -> None:
        self._enabled = bool(on)

    @property
    def diagnostics(self) -> bool:
        return self._diagnostics

    def set_diagnostics(self, on: bool) -> None:
        self._diagnostics = bool(on)

    def start_capture(self) -> None:
        self._capturing = True

    def cancel_capture(self) -> None:
        self._capturing = False

    @property
    def capturing(self) -> bool:
        return self._capturing

    def install(self, app: QApplication | None = None) -> None:
        app = app or QApplication.instance()
        if app is not None and not self._installed:
            app.installEventFilter(self)
            self._installed = True

    def uninstall(self, app: QApplication | None = None) -> None:
        app = app or QApplication.instance()
        if app is not None and self._installed:
            app.removeEventFilter(self)
            self._installed = False

    def configure(self, next_keys, previous_keys, debounce_ms) -> None:
        self.mapper.configure(next_keys, previous_keys, debounce_ms)
        self.bindingsChanged.emit()

    # -- programmatic triggers (on-screen buttons, tests) ----------------------------------------------------------
    def trigger(self, action: RemoteAction) -> None:
        self.counts[action] += 1
        (self.nextTriggered if action is RemoteAction.NEXT else self.previousTriggered).emit()

    # -- core: one key event -------------------------------------------------------------------------------------
    def process_key(self, name: str, *, press: bool = True, qt_key: int = 0, native_vk: int = 0, scan_code: int = 0,
                    modifiers: str = "", text: str = "", auto_repeat: bool = False) -> bool:
        """Handle one key event; returns True when the event must be swallowed."""
        if self._capturing and press and not auto_repeat:
            self._capturing = False
            self.captured.emit(normalize_key_name(name) or name)
            return True

        result = "-"
        consumed = False
        action = None
        if press and self._enabled and not self._diagnostics and not modifiers.replace("Shift", "").strip("+"):
            action = self.mapper.map(name, auto_repeat, self._clock())
            if action is not None:
                result = action.value
                consumed = True
            elif self.mapper.last_reason in ("debounced", "auto-repeat ignored"):
                result = self.mapper.last_reason
                consumed = True   # still a remote key: do not let it scroll a list or move a slider
        elif not press and self._enabled and not self._diagnostics and self.mapper.action_for(name):
            consumed = True

        if self._diagnostics:
            would = self.mapper.action_for(name)
            verdict = f"bound to {would.value} ({would.click} click)" if would else "not bound"
            rec = KeyRecord(self._clock() / 1000.0 - self.log.started, "press" if press else "release", name, qt_key,
                            native_vk, scan_code, modifiers, text, auto_repeat, verdict)
            self.log.add(rec)
            self.keyLogged.emit(rec)
            consumed = True
        if action is not None:
            self.trigger(action)
        return consumed

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt API)
        et = event.type()
        if et not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False
        if not (self._enabled or self._diagnostics or self._capturing):
            return False
        if not isinstance(event, QKeyEvent):
            return False
        key = event.key()
        if key in _MODIFIER_KEYS and not self._diagnostics:
            return False
        # never steal keys from a modal dialog or a text field
        if not (self._diagnostics or self._capturing):
            if QApplication.activeModalWidget() is not None:
                return False
            focus = QApplication.focusWidget()
            if isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit)):
                return False
        return self.process_key(
            key_name(key), press=(et == QEvent.Type.KeyPress), qt_key=int(key),
            native_vk=int(event.nativeVirtualKey()), scan_code=int(event.nativeScanCode()),
            modifiers=_modifier_text(event.modifiers()), text=event.text(), auto_repeat=event.isAutoRepeat())
