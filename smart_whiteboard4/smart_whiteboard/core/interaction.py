"""Pointer interaction logic: modes, dwell confirmation, pen control, remote clicks.

Pure Python (no Qt) so it can be unit tested.  The engine receives pointer positions (board coordinates) and
remote clicks, and returns a list of :class:`Command` for the page to execute.

Modes
-----
NAVIGATION  the pointer only moves and highlights menu items; Next (left click) activates the item under it.
DRAWING     Next on empty board toggles the pen down/up at the pointer (draw by moving the marker); Next on a menu
            item activates it.  Losing the pointer lifts the pen.
SELECTION   hovering a menu item for ``dwell_ms`` confirms it automatically (progress ring); Next confirms at once.

Previous (right click) is "back": it lifts the pen if it is down, otherwise goes back / opens-closes the menu.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    NAVIGATION = "navigation"
    DRAWING = "drawing"
    SELECTION = "selection"

    @property
    def label(self) -> str:
        return self.value.capitalize()


@dataclass(frozen=True)
class Command:
    kind: str                 # pen_down | pen_move | pen_up | activate | back | click | pointer_lost
    x: float = 0.0
    y: float = 0.0
    target: str | None = None
    button: str = ""          # "left" | "right" for click


class DwellSelector:
    """Confirms a target after the pointer rests on it.

    * ``dwell_ms``   time on the same target before it fires.
    * ``grace_ms``   hysteresis: leaving the target for less than this does not reset the timer (marker jitter at
                     the edge of an item).
    * After firing, the same target cannot fire again until the pointer has left it (no repeats while resting).
    """

    def __init__(self, dwell_ms: int = 1200, grace_ms: int = 200) -> None:
        self.dwell_ms = max(100, int(dwell_ms))
        self.grace_ms = max(0, int(grace_ms))
        self.reset()

    def reset(self) -> None:
        self.target: str | None = None
        self._since = 0.0
        self._away_since: float | None = None
        self._locked: str | None = None
        self.progress = 0.0

    def update(self, target: str | None, now_ms: float) -> str | None:
        """Feed the current hover target; returns the target id when it is confirmed."""
        if self._locked is not None:
            if target == self._locked:
                return None            # still resting on the item that just fired
            self._locked = None
        if self.target is not None:
            if target == self.target:
                self._away_since = None
            else:
                if self._away_since is None:
                    self._away_since = now_ms
                if now_ms - self._away_since < self.grace_ms:
                    return None        # jitter at the edge: keep the timer
                self.target, self._away_since, self.progress = None, None, 0.0
        if self.target is None:
            if target is not None:
                self.target, self._since, self._away_since, self.progress = target, now_ms, None, 0.0
            return None
        self.progress = min(1.0, (now_ms - self._since) / self.dwell_ms)
        if self.progress >= 1.0:
            fired = self.target
            self._locked = fired
            self.target, self.progress, self._away_since = None, 0.0, None
            return fired
        return None


class InteractionEngine:
    def __init__(self, dwell_ms: int = 1200) -> None:
        self.mode = Mode.NAVIGATION
        self.dwell = DwellSelector(dwell_ms)
        self.pen_down = False
        self.valid = False
        self.x = 0.0
        self.y = 0.0
        self.hover: str | None = None

    # -- configuration ---------------------------------------------------------------------------------------------
    def set_dwell_ms(self, ms: int) -> None:
        self.dwell.dwell_ms = max(100, int(ms))

    def set_mode(self, mode: Mode) -> list[Command]:
        cmds: list[Command] = []
        if mode != self.mode:
            if self.pen_down:
                cmds.append(self._pen_up())
            self.dwell.reset()
        self.mode = mode
        return cmds

    # -- pointer ---------------------------------------------------------------------------------------------------
    def _pen_up(self) -> Command:
        self.pen_down = False
        return Command("pen_up", self.x, self.y)

    def pointer(self, x: float, y: float, valid: bool, now_ms: float, hover: str | None = None) -> list[Command]:
        """New pointer sample. ``hover`` is the id of the menu item under it (None if no menu / not over one)."""
        cmds: list[Command] = []
        if not valid:
            if self.valid or self.pen_down:
                self.valid = False
                self.hover = None
                self.dwell.reset()
                if self.pen_down:
                    cmds.append(self._pen_up())
                cmds.append(Command("pointer_lost"))
            return cmds
        self.valid = True
        self.x, self.y, self.hover = float(x), float(y), hover
        if self.pen_down:
            cmds.append(Command("pen_move", self.x, self.y))
        if self.mode is Mode.SELECTION:
            fired = self.dwell.update(hover, now_ms)
            if fired is not None:
                cmds.append(Command("activate", self.x, self.y, fired))
        else:
            self.dwell.reset()
        return cmds

    @property
    def dwell_progress(self) -> float:
        return self.dwell.progress if self.mode is Mode.SELECTION else 0.0

    # -- remote clicks ---------------------------------------------------------------------------------------------
    def left_click(self) -> list[Command]:
        """Next button."""
        if not self.valid:
            return []
        cmds: list[Command] = []
        if self.hover is not None:
            if self.pen_down:
                cmds.append(self._pen_up())
            cmds.append(Command("activate", self.x, self.y, self.hover, "left"))
            self.dwell.reset()
            return cmds
        if self.mode is Mode.DRAWING:
            if self.pen_down:
                cmds.append(self._pen_up())
            else:
                self.pen_down = True
                cmds.append(Command("pen_down", self.x, self.y))
            return cmds
        return [Command("click", self.x, self.y, None, "left")]

    def right_click(self) -> list[Command]:
        """Previous button."""
        if self.pen_down:
            return [self._pen_up()]
        return [Command("back", self.x, self.y, None, "right")]

    def release_all(self) -> list[Command]:
        """Called when the page is left or tracking is switched off."""
        cmds = [self._pen_up()] if self.pen_down else []
        self.valid = False
        self.hover = None
        self.dwell.reset()
        return cmds
