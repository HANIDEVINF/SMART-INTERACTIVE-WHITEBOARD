"""Hand backend: geometry, gesture clicks, fallback and the full worker pipeline - with a fake MediaPipe landmarker,
so the tests run without the model file or a camera."""
from types import SimpleNamespace

import numpy as np
import pytest

from core import hand_tracker as ht
from core import vision_engine as ve
from core.detector import DetectionParams
from core.tracker import TrackerParams

W, H = 640, 480


def hand(pinch: str = "", tip=(0.60, 0.30)):
    """21 normalised landmarks: wrist (.5,.8), middle knuckle (.5,.55); thumb/middle/ring tips placed by `pinch`."""
    pts = [(0.5, 0.8)] * 21
    pts = list(pts)
    pts[ht.WRIST], pts[ht.MIDDLE_MCP] = (0.5, 0.8), (0.5, 0.55)
    pts[ht.INDEX_TIP] = tip
    pts[ht.THUMB_TIP] = (0.35, 0.60)
    pts[ht.MIDDLE_TIP] = (0.50, 0.25) if pinch != "next" else (0.36, 0.61)
    pts[ht.RING_TIP] = (0.58, 0.30) if pinch != "previous" else (0.36, 0.61)
    return [SimpleNamespace(x=x, y=y) for x, y in pts]


class FakeLandmarker:
    def __init__(self):
        self.script = []
        self.stamps = []

    def detect_for_video(self, image, ts):
        self.stamps.append(ts)
        lm = self.script.pop(0) if self.script else None
        return SimpleNamespace(hand_landmarks=[lm] if lm else [], handedness=[[SimpleNamespace(score=0.93)]])


def frame():
    return np.zeros((H, W, 3), np.uint8)


def test_pinch_ratio_and_hysteresis():
    c = ht.PinchClassifier()
    px = lambda lms: [(p.x * W, p.y * H) for p in lms]
    assert c.update(px(hand())) == ""
    assert c.update(px(hand("next"))) == "next"
    assert c.update(px(hand("previous"))) == "previous" or c.state in ("next", "previous")
    assert c.update(None) == ""
    assert c.update(px(hand("previous"))) == "previous"


def test_clicker_one_event_per_pinch_with_confirmation_and_cooldown():
    g = ht.GestureClicker(confirm_frames=2, cooldown_ms=600)
    assert g.update("next", 0.00) is None                 # needs 2 frames
    assert g.update("next", 0.03) == "next"
    assert g.update("next", 0.06) is None                 # still held: no repeat
    assert g.update("", 0.10) is None
    assert g.update("next", 0.20) is None
    assert g.update("next", 0.23) is None                 # cooldown (600 ms) not over
    g.update("", 0.30)
    g.update("next", 0.80)
    assert g.update("next", 0.83) == "next"
    g.update("", 0.9)
    g.update("previous", 1.5)
    assert g.update("previous", 1.53) == "previous"


def test_detect_returns_fingertip_in_camera_pixels():
    fake = FakeLandmarker()
    fake.script = [hand(tip=(0.60, 0.30))]
    tr = ht.HandTracker(landmarker_factory=lambda: fake)
    r = tr.detect(frame(), 1.0)
    assert r.detection is not None and r.status == "ok"
    assert r.detection.x == pytest.approx(0.60 * W - 0.5) and r.detection.y == pytest.approx(0.30 * H - 0.5)
    assert r.detection.confidence == pytest.approx(0.93)
    assert len(r.landmarks) == 21 and r.mask.any()
    r2 = tr.detect(frame(), 1.0)                          # same timestamp -> still strictly increasing
    assert fake.stamps[1] > fake.stamps[0]
    assert r2.detection is None and r2.status == "no_hand"


def _worker(monkeypatch, fake):
    monkeypatch.setattr(ve, "hand_backend_status", lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(ve, "HandTracker", lambda: ht.HandTracker(landmarker_factory=lambda: fake))
    return ve.VisionWorker(ve.FrameMailbox(), DetectionParams(method="hand"), TrackerParams())


def test_worker_hand_pipeline_emits_single_click_event(monkeypatch):
    fake = FakeLandmarker()
    fake.script = [hand(), hand("next"), hand("next"), hand("next"), hand(), hand()]
    w = _worker(monkeypatch, fake)
    events = []
    for i in range(6):
        res = w.process(frame(), 1.0 + i * 0.04)
        assert res.source == "hand"
        events.append(res.gesture_event)
    assert events == [None, None, "next", None, None, None]
    assert res.detection.detection.x == pytest.approx(0.60 * W - 0.5)      # fingertip is the pointer
    assert res.track.position is not None


def test_worker_falls_back_to_marker_when_backend_missing(monkeypatch):
    monkeypatch.setattr(ve, "hand_backend_status", lambda *a, **k: (False, "Hand model not downloaded yet"))
    w = ve.VisionWorker(ve.FrameMailbox(), DetectionParams(method="hand"), TrackerParams())
    res = w.process(frame(), 1.0)
    assert res.source == "marker" and "colour marker" in res.notice and res.gesture_event is None
    assert "Hand model not downloaded" in res.detection.message


def test_worker_falls_back_when_landmarker_crashes(monkeypatch):
    class Boom(FakeLandmarker):
        def detect_for_video(self, image, ts):
            raise RuntimeError("gpu exploded")
    w = _worker(monkeypatch, Boom())
    res = w.process(frame(), 1.0)
    assert res.source == "marker" and "failed" in res.notice


def test_marker_mode_unchanged():
    w = ve.VisionWorker(ve.FrameMailbox(), DetectionParams(), TrackerParams())
    res = w.process(frame(), 1.0)
    assert res.source == "marker" and res.notice == "" and res.gesture_event is None


def test_method_setting_roundtrip_and_validation():
    assert DetectionParams(method="nonsense").sanitized().method == "color_marker"
    assert DetectionParams(method="hand").sanitized().method == "hand"


def test_status_without_model(tmp_path):
    ok, msg = ht.hand_backend_status(tmp_path / "missing.task")
    assert not ok and msg


def test_download_model_atomic_and_errors(tmp_path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"x" * 1_200_000)
    dest = tmp_path / "m" / "hand_landmarker.task"
    seen = []
    ht.download_model(dest, progress=seen.append, url=src.as_uri())
    assert dest.stat().st_size == 1_200_000 and seen[-1] == 1.0 and not list(dest.parent.glob("*.part"))
    small = tmp_path / "small.bin"
    small.write_bytes(b"tiny")
    bad = tmp_path / "m2" / "x.task"
    with pytest.raises(OSError):
        ht.download_model(bad, url=small.as_uri())
    assert not bad.exists() and not list(bad.parent.glob("*.part"))
    with pytest.raises(OSError):
        ht.download_model(tmp_path / "m3" / "x.task", url=(tmp_path / "nope").as_uri())

