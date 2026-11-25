"""Tracking stability: EMA smoothing, jump rejection, lost-pointer handling."""
import math

import numpy as np
import pytest

from core.tracker import HOLDING, LOST, TRACKING, PointerTracker, TrackerParams

DIAG = math.hypot(640, 360)


def tracker(**kw):
    return PointerTracker(TrackerParams(**kw))


def test_ema_formula_is_exact():
    t = tracker(alpha=0.4)
    t.update((100.0, 50.0), 0.0, DIAG)
    out = t.update((110.0, 70.0), 0.033, DIAG)
    assert out.position == pytest.approx((0.4 * 110 + 0.6 * 100, 0.4 * 70 + 0.6 * 50))
    assert out.state == TRACKING and out.valid


def test_alpha_one_means_no_smoothing():
    t = tracker(alpha=1.0)
    t.update((10.0, 10.0), 0.0, DIAG)
    assert t.update((20.0, 30.0), 0.03, DIAG).position == (20.0, 30.0)


def test_first_measurement_is_taken_as_is():
    assert tracker().update((5.0, 6.0), 0.0, DIAG).position == (5.0, 6.0)


def test_smoothing_reduces_jitter():
    rng = np.random.default_rng(2)
    t = tracker(alpha=0.4)
    raw, smooth = [], []
    for i in range(400):
        m = (300 + rng.normal(0, 2.0), 200 + rng.normal(0, 2.0))
        raw.append(m[0])
        smooth.append(t.update(m, i / 30, DIAG).position[0])
    assert np.std(smooth[50:]) < 0.65 * np.std(raw[50:])             # theory: sqrt(a/(2-a)) = 0.5


def test_single_outlier_jump_is_ignored():
    t = tracker(confirm_frames=2)
    t.update((100.0, 100.0), 0.0, DIAG)
    out = t.update((600.0, 340.0), 0.03, DIAG)                         # far jump, seen once
    assert out.state == HOLDING and not out.valid and out.position == (100.0, 100.0)
    out = t.update((102.0, 101.0), 0.06, DIAG)                         # back to normal
    assert out.state == TRACKING


def test_confirmed_jump_relocates_without_smoothing_lag():
    t = tracker(confirm_frames=2)
    t.update((100.0, 100.0), 0.0, DIAG)
    t.update((600.0, 340.0), 0.03, DIAG)
    out = t.update((602.0, 341.0), 0.06, DIAG)
    assert out.state == TRACKING and out.position == (602.0, 341.0)


def test_holding_then_lost_after_timeout_and_never_valid_when_stale():
    t = tracker(lost_timeout_ms=500)
    t.update((200.0, 100.0), 1.0, DIAG)
    held = t.update(None, 1.2, DIAG)
    assert held.state == HOLDING and held.position == (200.0, 100.0) and not held.valid
    lost = t.update(None, 1.6, DIAG)
    assert lost.state == LOST and lost.position is None and not lost.valid
    assert t.update(None, 5.0, DIAG).state == LOST


def test_after_lost_the_filter_restarts_at_the_new_position():
    t = tracker(alpha=0.2, lost_timeout_ms=200)
    t.update((10.0, 10.0), 0.0, DIAG)
    t.update(None, 1.0, DIAG)                                          # lost
    out = t.update((500.0, 300.0), 1.1, DIAG)
    assert out.position == (500.0, 300.0)                              # no glide in from (10, 10)


def test_invalid_coordinates_are_never_accepted():
    t = tracker()
    assert t.update((float("nan"), 5.0), 0.0, DIAG).state == LOST
    t.update((50.0, 50.0), 0.1, DIAG)
    out = t.update((float("inf"), 1.0), 0.13, DIAG)
    assert out.state == HOLDING and out.position == (50.0, 50.0)


def test_params_are_sanitized():
    p = TrackerParams(alpha=5, lost_timeout_ms=-1, max_jump_pct=0, confirm_frames=0).sanitized()
    assert p.alpha == 1.0 and p.lost_timeout_ms >= 50 and p.max_jump_pct >= 1 and p.confirm_frames >= 1
    assert TrackerParams(alpha=0).sanitized().alpha == 0.05
