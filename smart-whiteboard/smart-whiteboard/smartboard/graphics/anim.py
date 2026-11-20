"""Small animation helpers (easing + a value that glides towards a target)."""
from __future__ import annotations

import math


def clamp01(t: float) -> float:
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def ease_out(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    return 3 * t * t - 2 * t * t * t


class Glide:
    """value that moves exponentially towards ``target`` (speed in 1/s)."""

    def __init__(self, value: float = 0.0, speed: float = 14.0):
        self.v, self.target, self.speed = value, value, speed

    def update(self, dt: float) -> float:
        self.v += (self.target - self.v) * (1 - math.exp(-self.speed * dt))
        if abs(self.target - self.v) < 1e-3:
            self.v = self.target
        return self.v
