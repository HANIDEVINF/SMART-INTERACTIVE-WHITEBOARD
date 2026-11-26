"""Pointer tracking: smoothing, jump rejection and lost-pointer handling.

Exponential moving average (EMA)
--------------------------------
For every accepted measurement m_t the filtered position is

        p_t = alpha * m_t + (1 - alpha) * p_{t-1}          0 < alpha <= 1

alpha = 1 returns the raw measurement (no smoothing, no lag); small alpha averages over many
frames (very smooth, but the pointer lags). The filter is a first-order low-pass with time
constant  tau = -dt / ln(1 - alpha)  (alpha = 0.5 at 30 FPS -> tau ~ 48 ms). Jitter with standard
deviation sigma is reduced to about  sigma * sqrt(alpha / (2 - alpha))  (alpha = 0.5 -> 0.58 sigma).

Robustness rules (what makes it "stable" and never shows stale data as valid)
---------------------------------------------------------------------------
* Jump rejection: a measurement farther than `max_jump_pct` % of the frame diagonal from the
  current position is NOT accepted at once. It must be seen `confirm_frames` times in a row at
  (nearly) the same place - then it is a genuine relocation (the filter restarts there, without
  smoothing); a single wild outlier is ignored.
* Holding: when there is no usable measurement the last position is kept for up to
  `lost_timeout_ms`, but flagged valid=False so nothing can draw with it.
* Lost: after the timeout the position becomes None and the filter is reset, so the next
  detection starts fresh instead of gliding in from the old place.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

TRACKING = "tracking"
HOLDING = "holding"
LOST = "lost"


@dataclass(frozen=True)
class TrackerParams:
    alpha: float = 0.5
    lost_timeout_ms: int = 600
    max_jump_pct: float = 25.0
    confirm_frames: int = 2

    def sanitized(self) -> "TrackerParams":
        return TrackerParams(
            alpha=min(max(float(self.alpha), 0.05), 1.0),
            lost_timeout_ms=int(min(max(int(self.lost_timeout_ms), 50), 10_000)),
            max_jump_pct=min(max(float(self.max_jump_pct), 1.0), 100.0),
            confirm_frames=int(min(max(int(self.confirm_frames), 1), 10)))

    @classmethod
    def from_settings(cls, settings) -> "TrackerParams":
        d = cls()
        try:
            g = settings.get
            return cls(alpha=float(g("detection.alpha", d.alpha)),
                       lost_timeout_ms=int(g("detection.lost_timeout_ms", d.lost_timeout_ms)),
                       max_jump_pct=float(g("detection.max_jump_pct", d.max_jump_pct)),
                       confirm_frames=int(g("detection.confirm_frames", d.confirm_frames))).sanitized()
        except (TypeError, ValueError):
            return d

    def write_to(self, settings) -> None:
        settings.set("detection.alpha", round(self.alpha, 3))
        settings.set("detection.lost_timeout_ms", self.lost_timeout_ms)
        settings.set("detection.max_jump_pct", round(self.max_jump_pct, 1))
        settings.set("detection.confirm_frames", self.confirm_frames)


@dataclass(frozen=True)
class TrackOutput:
    state: str                                   # tracking | holding | lost
    position: tuple[float, float] | None         # filtered position, None when lost
    valid: bool                                  # True only for a fresh, accepted measurement
    since_valid_ms: float                        # time since the last accepted measurement


class PointerTracker:
    def __init__(self, params: TrackerParams | None = None) -> None:
        self.params = (params or TrackerParams()).sanitized()
        self.reset()

    def set_params(self, params: TrackerParams) -> None:
        self.params = params.sanitized()

    def reset(self) -> None:
        self._pos: tuple[float, float] | None = None
        self._last_valid_t: float | None = None
        self._pending: tuple[float, float] | None = None
        self._pending_count = 0

    def update(self, measurement: tuple[float, float] | None, t: float, frame_diag: float) -> TrackOutput:
        """Feed one frame. `t` is a monotonic time in seconds, `frame_diag` the frame diagonal in px."""
        p = self.params
        if measurement is not None and not all(math.isfinite(v) for v in measurement):
            measurement = None

        accepted = False
        if measurement is not None:
            if self._pos is None:
                self._pos, accepted = measurement, True
            else:
                limit = p.max_jump_pct / 100.0 * frame_diag
                if math.dist(measurement, self._pos) <= limit:
                    a = p.alpha
                    self._pos = (a * measurement[0] + (1 - a) * self._pos[0],
                                 a * measurement[1] + (1 - a) * self._pos[1])
                    self._pending, self._pending_count = None, 0
                    accepted = True
                else:                              # suspicious jump: wait for confirmation
                    if self._pending is not None and math.dist(measurement, self._pending) <= limit:
                        self._pending_count += 1
                    else:
                        self._pending_count = 1
                    self._pending = measurement
                    if self._pending_count >= p.confirm_frames:
                        self._pos, accepted = measurement, True
                        self._pending, self._pending_count = None, 0

        if accepted:
            self._last_valid_t = t
            return TrackOutput(TRACKING, self._pos, True, 0.0)

        elapsed = (t - self._last_valid_t) * 1000.0 if self._last_valid_t is not None else math.inf
        if self._pos is None or elapsed > p.lost_timeout_ms:
            self.reset()
            return TrackOutput(LOST, None, False, elapsed)
        return TrackOutput(HOLDING, self._pos, False, elapsed)
