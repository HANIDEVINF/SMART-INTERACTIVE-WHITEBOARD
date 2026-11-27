"""Pointer tracker: smoothing, jump rejection and loss handling.

Receives raw detections (camera pixels), maps them to board coordinates
through the homography, and produces a stable board-space pointer.

Smoothing: exponential moving average (EMA)

    p_smooth = alpha * p_new + (1 - alpha) * p_smooth

alpha close to 1 follows the marker tightly (more jitter), alpha close to
0 is very smooth but laggy.  The value is configurable.

Jump rejection: if a new sample is farther than ``max_jump`` pixels from
the current estimate it is ignored for one frame; if the *next* sample is
also far away the tracker accepts the new position (the marker really did
teleport, e.g. the teacher moved quickly).  This rejects single-frame
false detections without making fast motion impossible.

Loss handling: when the marker disappears the tracker keeps reporting the
last position for ``loss_timeout`` seconds (the pointer stays visible but
stops updating), then reports the pointer as lost.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np


class PointerTracker:
    def __init__(self, alpha: float = 0.45, max_jump: float = 250.0,
                 loss_timeout: float = 1.5):
        self.alpha = float(alpha)
        self.max_jump = float(max_jump)
        self.loss_timeout = float(loss_timeout)

        self._pos: Optional[np.ndarray] = None      # smoothed board pos
        self._pending_far: Optional[np.ndarray] = None
        self._last_seen: float = 0.0
        self._initialized = False

    # -- configuration -----------------------------------------------------

    def configure(self, alpha=None, max_jump=None, loss_timeout=None) -> None:
        if alpha is not None:
            self.alpha = float(alpha)
        if max_jump is not None:
            self.max_jump = float(max_jump)
        if loss_timeout is not None:
            self.loss_timeout = float(loss_timeout)

    # -- main API ----------------------------------------------------------

    def update(self, board_point, now: Optional[float] = None) -> Optional[tuple[float, float]]:
        """Feed one board-space detection (or None) and get the pointer.

        Returns (x, y) in board coordinates, or None when the pointer is
        lost.  ``board_point`` may be a tuple/list/ndarray of 2 floats.
        """
        now = time.time() if now is None else now

        if board_point is None:
            return self._handle_loss(now)

        new = np.asarray(board_point, dtype=np.float64)

        if not self._initialized:
            self._pos = new.copy()
            self._initialized = True
            self._last_seen = now
            self._pending_far = None
            return self._as_tuple(self._pos)

        dist = float(np.linalg.norm(new - self._pos))

        # Jump rejection: a single implausibly large step is ignored; two
        # consecutive far samples mean the marker really moved.
        if dist > self.max_jump:
            if self._pending_far is not None and \
                    float(np.linalg.norm(new - self._pending_far)) < self.max_jump:
                # Confirmed teleport: accept and re-anchor.
                self._pos = new.copy()
                self._pending_far = None
            else:
                self._pending_far = new.copy()
                self._last_seen = now
                return self._as_tuple(self._pos)
        else:
            self._pending_far = None

        # Exponential moving average.
        self._pos = self.alpha * new + (1.0 - self.alpha) * self._pos
        self._last_seen = now
        return self._as_tuple(self._pos)

    def current(self, now: Optional[float] = None) -> Optional[tuple[float, float]]:
        """Current estimate without feeding a new sample.

        Used on UI ticks where no new camera frame has arrived: returns the
        last position, or None once ``loss_timeout`` has elapsed.
        """
        now = time.time() if now is None else now
        return self._handle_loss(now)

    def reset(self) -> None:
        """Forget the current position (e.g. after recalibration)."""
        self._pos = None
        self._pending_far = None
        self._initialized = False
        self._last_seen = 0.0

    # -- internals ---------------------------------------------------------

    def _handle_loss(self, now: float) -> Optional[tuple[float, float]]:
        if not self._initialized:
            return None
        if now - self._last_seen <= self.loss_timeout:
            # Grace period: keep showing the last position.
            return self._as_tuple(self._pos)
        return None

    @staticmethod
    def _as_tuple(pos: np.ndarray) -> tuple[float, float]:
        return (float(pos[0]), float(pos[1]))
