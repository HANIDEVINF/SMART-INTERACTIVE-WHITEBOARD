"""FEATURE: classroom countdown timer (pure logic)."""
from __future__ import annotations

import time


class Countdown:
    def __init__(self, seconds: int = 300):
        self.total = float(seconds)
        self.left = float(seconds)
        self.running = False
        self._t = time.perf_counter()

    def tick(self):
        now = time.perf_counter()
        if self.running:
            self.left = max(0.0, self.left - (now - self._t))
            if self.left <= 0:
                self.running = False
        self._t = now

    def toggle(self):
        self.tick()
        if self.left <= 0:
            self.left = self.total
        self.running = not self.running

    def add(self, seconds: float):
        self.tick()
        self.total = max(10.0, self.total + seconds)
        self.left = min(max(0.0, self.left + seconds), 99 * 60 + 59)
        if self.left > self.total:
            self.total = self.left

    def set(self, seconds: int):
        self.total = self.left = float(seconds)
        self.running = False

    def reset(self):
        self.left = self.total
        self.running = False

    @property
    def finished(self) -> bool:
        return self.left <= 0 and not self.running

    @property
    def fraction(self) -> float:
        return self.left / self.total if self.total else 0.0

    def text(self) -> str:
        s = int(self.left + 0.999)
        return "%02d:%02d" % (s // 60, s % 60)
