"""Simulated pointer source.

When the physical marker is unavailable the pointer can be driven by the
mouse.  The mouse position (in screen pixels) is used directly as the
board coordinate because the board coordinate system is defined to be the
application window size.
"""

from __future__ import annotations

from typing import Optional

import pygame


class SimulatedPointer:
    """Returns the current mouse position as a board-space point."""

    def __init__(self):
        self._last: Optional[tuple[float, float]] = None

    def read(self) -> Optional[tuple[float, float]]:
        pos = pygame.mouse.get_pos()
        self._last = (float(pos[0]), float(pos[1]))
        return self._last

    @property
    def last(self):
        return self._last
