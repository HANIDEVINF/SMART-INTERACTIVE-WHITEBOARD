"""Tests for pointer tracking: smoothing, jump rejection, loss handling."""

import numpy as np

from detection.tracker import PointerTracker


def test_first_detection_initialises():
    t = PointerTracker(alpha=0.5)
    pos = t.update((100.0, 100.0), now=0.0)
    assert pos == (100.0, 100.0)


def test_ema_smoothing_converges():
    t = PointerTracker(alpha=0.5)
    t.update((0.0, 0.0), now=0.0)
    # Feed a constant new position; the estimate should approach it.
    pos = None
    for i in range(1, 20):
        pos = t.update((100.0, 100.0), now=float(i) * 0.016)
    assert abs(pos[0] - 100.0) < 1.0
    assert abs(pos[1] - 100.0) < 1.0


def test_smoothing_reduces_jitter():
    t = PointerTracker(alpha=0.3)
    t.update((100.0, 100.0), now=0.0)
    # Alternating jitter around 100.
    positions = [t.update((100 + d, 100), now=i * 0.016)[0]
                 for i, d in enumerate([5, -5, 5, -5, 5, -5])]
    # The smoothed output must vary less than the raw +/-5 jitter.
    assert max(positions) - min(positions) < 5.0


def test_jump_rejection_single_frame():
    t = PointerTracker(alpha=0.5, max_jump=50.0)
    t.update((100.0, 100.0), now=0.0)
    # A single far-away sample must be ignored.
    pos = t.update((500.0, 500.0), now=0.016)
    assert pos == (100.0, 100.0)


def test_jump_accept_after_confirmation():
    t = PointerTracker(alpha=0.5, max_jump=50.0)
    t.update((100.0, 100.0), now=0.0)
    t.update((500.0, 500.0), now=0.016)   # first far sample: pending
    pos = t.update((505.0, 505.0), now=0.032)  # second far sample: accept
    assert pos is not None
    assert abs(pos[0] - 505.0) < 60.0  # EMA pulls toward new position


def test_loss_grace_period():
    t = PointerTracker(loss_timeout=1.0)
    t.update((100.0, 100.0), now=0.0)
    # Within the timeout the last position is still reported.
    pos = t.update(None, now=0.5)
    assert pos == (100.0, 100.0)


def test_loss_after_timeout():
    t = PointerTracker(loss_timeout=1.0)
    t.update((100.0, 100.0), now=0.0)
    pos = t.update(None, now=2.0)
    assert pos is None


def test_recovery_after_loss():
    t = PointerTracker(loss_timeout=1.0)
    t.update((100.0, 100.0), now=0.0)
    assert t.update(None, now=2.0) is None
    pos = t.update((200.0, 200.0), now=2.1)
    assert pos is not None
    assert abs(pos[0] - 200.0) < 60.0


def test_reset():
    t = PointerTracker()
    t.update((100.0, 100.0), now=0.0)
    t.reset()
    assert t.update(None, now=0.1) is None
