"""Remote mapping, debounce, key log and the Qt event filter."""
import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from core.remote_control import (KeyLog, RemoteAction, RemoteController, RemoteMapper, key_name, normalize_key_name)


def test_default_mapping_next_left_click_previous_right_click():
    m = RemoteMapper()
    assert m.map("Right", now_ms=0) is RemoteAction.NEXT
    assert m.map("Left", now_ms=1000) is RemoteAction.PREVIOUS
    assert RemoteAction.NEXT.click == "left" and RemoteAction.PREVIOUS.click == "right"
    assert m.map("x", now_ms=2000) is None


def test_clicker_keys_and_name_normalisation():
    m = RemoteMapper()
    assert m.action_for("PageDown") is RemoteAction.NEXT
    assert m.action_for("pgup") is RemoteAction.PREVIOUS
    assert normalize_key_name("PageDown") == "PgDown"
    assert normalize_key_name("nonsense key") == ""


def test_debounce_per_action_and_auto_repeat():
    m = RemoteMapper(debounce_ms=250)
    assert m.map("Right", now_ms=0) is RemoteAction.NEXT
    assert m.map("Right", now_ms=100) is None and m.last_reason == "debounced"
    assert m.map("Left", now_ms=120) is RemoteAction.PREVIOUS      # independent of Next
    assert m.map("Right", now_ms=300) is RemoteAction.NEXT
    assert m.map("Right", now_ms=900, auto_repeat=True) is None and m.last_reason == "auto-repeat ignored"


def test_conflicting_or_empty_bindings_rejected():
    with pytest.raises(ValueError):
        RemoteMapper(["Right"], ["Right"])
    with pytest.raises(ValueError):
        RemoteMapper([], ["Left"])
    m = RemoteMapper()
    with pytest.raises(ValueError):
        m.configure(["A"], ["A", "B"], 100)
    assert m.next_keys == ("Right", "PgDown")      # failed configure leaves the old binding


def test_rebinding():
    m = RemoteMapper()
    m.configure(["N"], ["P"], 0)
    assert m.map("N", now_ms=0) is RemoteAction.NEXT and m.map("Right", now_ms=1) is None


def test_key_log_summary_and_save(tmp_path):
    log = KeyLog()
    from core.remote_control import KeyRecord
    log.add(KeyRecord(0.1, "press", "Right", 0x01000014, 0x27, 77, "", "", False, "NEXT"))
    log.add(KeyRecord(0.2, "press", "Right", 0x01000014, 0x27, 77, "", "", True, "-"))
    log.add(KeyRecord(0.3, "press", "PgDown", 0x01000017, 0x22, 81, "", "", False, "-"))
    s = log.summary()
    assert s.count("Right") == 1 and "0x27" in s and "PgDown" in s
    p = log.save(tmp_path / "keys.txt")
    assert "vk=0x27" in p.read_text(encoding="utf-8")


def test_key_name():
    assert key_name(int(Qt.Key.Key_Right)) == "Right"
    assert key_name(int(Qt.Key.Key_Left)) == "Left"


def _ctrl(clock):
    return RemoteController(clock=clock)


def test_controller_signals_and_enabled_flag():
    t = [0.0]
    rc = _ctrl(lambda: t[0])
    got = []
    rc.nextTriggered.connect(lambda: got.append("N"))
    rc.previousTriggered.connect(lambda: got.append("P"))
    assert rc.process_key("Right") is False and got == []            # disabled: arrow keeps its normal meaning
    rc.set_enabled(True)
    assert rc.process_key("Right") is True
    t[0] = 1000
    assert rc.process_key("Left") is True
    t[0] = 1010
    assert rc.process_key("Left") is True                           # debounced but still swallowed
    assert got == ["N", "P"]
    assert rc.process_key("Right", modifiers="Ctrl") is False         # Ctrl+Right is not the remote
    assert rc.process_key("q") is False


def test_diagnostics_records_and_does_not_act():
    rc = _ctrl(lambda: 5000.0)
    rc.set_enabled(True)
    rc.set_diagnostics(True)
    got = []
    rc.nextTriggered.connect(lambda: got.append(1))
    rc.process_key("Right", qt_key=0x01000014, native_vk=0x27, scan_code=77)
    rc.process_key("Right", press=False, qt_key=0x01000014, native_vk=0x27, scan_code=77)
    assert got == [] and len(rc.log) == 2
    assert rc.log.records[0].native_vk == 0x27


def test_capture_for_rebinding():
    rc = _ctrl(lambda: 0.0)
    names = []
    rc.captured.connect(names.append)
    rc.start_capture()
    assert rc.process_key("PageDown") is True
    assert names == ["PgDown"] and not rc.capturing


def test_real_key_events_through_event_filter():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    rc = RemoteController()
    rc.set_enabled(True)
    got = []
    rc.nextTriggered.connect(lambda: got.append("N"))
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
    assert rc.eventFilter(None, ev) is True
    rep = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier, 0, 0, 0, "", True)
    assert rc.eventFilter(None, rep) is True
    assert got == ["N"]
    shift = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier)
    assert rc.eventFilter(None, shift) is False
