"""Temporal stabilisation of the pointer: One-Euro filter + lost-frame hold."""
from __future__ import annotations

import math
from typing import Optional, Tuple

from ..config import TrackingConfig


class _LowPass:
    def __init__(self):
        self.y: Optional[float] = None

    def __call__(self, x: float, alpha: float) -> float:
        self.y = x if self.y is None else alpha * x + (1 - alpha) * self.y
        return self.y


class OneEuroFilter2D:
    """One-Euro filter (Casiez et al. 2012) applied to x and y.

    The cut-off frequency grows with the speed of the signal:
        fc = min_cutoff + beta * |dx/dt|
    -> strong smoothing when the hand is still (no jitter), little lag
    when it moves quickly (no "rubber band" feeling).
    """

    def __init__(self, min_cutoff=1.5, beta=0.04, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.reset()

    def reset(self):
        self._x = [_LowPass(), _LowPass()]
        self._dx = [_LowPass(), _LowPass()]
        self._prev: Optional[Tuple[float, float]] = None
        self._t: Optional[float] = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, p: Tuple[float, float], t: float) -> Tuple[float, float]:
        if self._prev is None or self._t is None:
            self._prev, self._t = p, t
            return self._x[0](p[0], 1.0), self._x[1](p[1], 1.0)
        dt = max(t - self._t, 1e-3)
        out = []
        for i in (0, 1):
            dx = (p[i] - self._prev[i]) / dt
            edx = self._dx[i](dx, self._alpha(self.d_cutoff, dt))
            fc = self.min_cutoff + self.beta * abs(edx)
            out.append(self._x[i](p[i], self._alpha(fc, dt)))
        self._prev, self._t = p, t
        return out[0], out[1]


class PointerTracker:
    """Wraps a filter and handles short detection dropouts.

    update(point_or_None, t) returns (smoothed_point_or_None, tracked_now, lost_frames).
    After a miss the last position is kept for ``max_lost_frames`` frames
    (the pointer does not flicker); after that the pointer is "lost".
    """

    def __init__(self, cfg: TrackingConfig):
        self.cfg = cfg
        self.filter = OneEuroFilter2D(cfg.min_cutoff, cfg.beta, cfg.d_cutoff)
        self.last: Optional[Tuple[float, float]] = None
        self.lost = 0

    def reset(self):
        self.filter.reset()
        self.last = None
        self.lost = 0

    def update(self, p: Optional[Tuple[float, float]], t: float):
        if p is not None:
            self.lost = 0
            self.last = self.filter(p, t)
            return self.last, True, 0
        self.lost += 1
        if self.lost > self.cfg.max_lost_frames:
            self.filter.reset()          # next sighting starts fresh (no lag trail)
            self.last = None
            return None, False, self.lost
        return self.last, False, self.lost
