"""Settings > "Remote & Pointer": key bindings for the two-button remote, key diagnostics, dwell and debounce."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from core.remote_control import (DEFAULT_DEBOUNCE_MS, DEFAULT_NEXT_KEYS, DEFAULT_PREVIOUS_KEYS, KeyRecord,
                                 RemoteAction, RemoteController)
from core.settings import DATA_DIR, Settings
from ui.widgets import ParamSlider


def _panel(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("panel")
    col = QVBoxLayout(frame)
    col.setContentsMargins(18, 14, 18, 16)
    col.setSpacing(8)
    t = QLabel(title)
    t.setObjectName("panelTitle")
    col.addWidget(t)
    return frame, col


class RemotePanel(QWidget):
    message = Signal(str, str)
    dwellChanged = Signal(int)

    def __init__(self, settings: Settings, remote: RemoteController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings, self.remote = settings, remote
        self._capture_for: RemoteAction | None = None
        self._capture_add = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 4, 8, 4)
        col.setSpacing(12)

        # ---- bindings -------------------------------------------------------------------------------
        frame, f = _panel("Remote buttons")
        intro = QLabel("The remote has two buttons. Until the physical remote exists, two keys simulate it. "
                       "<b>Next</b> performs a <b>left click</b> and <b>Previous</b> a <b>right click</b> at the pointer "
                       "position (the tracked marker, or the mouse when tracking is off). The keys work on the "
                       "Whiteboard page only.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        f.addWidget(intro)
        self.next_label, self.prev_label = QLabel(), QLabel()
        self._capture_status = QLabel("")
        self._capture_status.setStyleSheet("color: #D97706; font-weight: 700;")
        for action, label, text in ((RemoteAction.NEXT, self.next_label, "Next  (left click)"),
                                    (RemoteAction.PREVIOUS, self.prev_label, "Previous  (right click)")):
            row = QHBoxLayout()
            name = QLabel(text)
            name.setFixedWidth(170)
            name.setStyleSheet("font-weight: 700;")
            label.setObjectName("mono")
            change = QPushButton("Change key...")
            change.setToolTip("Press the new key (or the remote button) after clicking")
            change.clicked.connect(lambda _=False, a=action: self._begin_capture(a, add=False))
            add = QPushButton("Add key...")
            add.setToolTip("Accept an additional key for this button (e.g. the code of your real remote)")
            add.clicked.connect(lambda _=False, a=action: self._begin_capture(a, add=True))
            row.addWidget(name)
            row.addWidget(label, 1)
            row.addWidget(change)
            row.addWidget(add)
            f.addLayout(row)
        f.addWidget(self._capture_status)
        reset = QPushButton("Restore default keys")
        reset.clicked.connect(self._restore_defaults)
        reset_row = QHBoxLayout()
        reset_row.addWidget(reset)
        reset_row.addStretch(1)
        f.addLayout(reset_row)
        self.debounce = ParamSlider("Debounce", 0, 800, int(settings.get("remote.debounce_ms", DEFAULT_DEBOUNCE_MS)),
                                    fmt="{:.0f} ms",
                                    tooltip="A second press of the same button within this time is ignored")
        self.debounce.valueChanged.connect(self._on_debounce)
        f.addWidget(self.debounce)
        col.addWidget(frame)

        # ---- interaction ----------------------------------------------------------------------------
        frame, f = _panel("Selection mode")
        self.dwell = ParamSlider("Dwell time", 300, 3000, int(settings.get("interaction.dwell_ms", 1200)),
                                 fmt="{:.0f} ms", tooltip="Selection mode: how long the pointer must rest on a menu "
                                 "item before it is confirmed")
        self.dwell.valueChanged.connect(self._on_dwell)
        f.addWidget(self.dwell)
        hint = QLabel("Modes (keys 1 / 2 / 3 or the buttons above the board):  <b>Navigation</b> - Next clicks the "
                      "item under the pointer.  <b>Drawing</b> - Next lowers / lifts the pen; moving the marker "
                      "draws.  <b>Selection</b> - resting on an item confirms it (progress ring); Next confirms at "
                      "once.  Previous always means <i>back</i>: lift the pen, up one menu level, or open the menu.")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        f.addWidget(hint)
        col.addWidget(frame)

        # ---- diagnostics ----------------------------------------------------------------------------
        frame, f = _panel("Key diagnostics")
        d = QLabel("Switch it on, then press the remote's buttons. Every key is recorded with its name, Qt key code, "
                   "Windows virtual-key code and scan code - nothing is executed. Use the codes to bind the real "
                   "remote above and to document it in the report.")
        d.setWordWrap(True)
        d.setObjectName("muted")
        f.addWidget(d)
        bar = QHBoxLayout()
        self.diag_btn = QPushButton("Start diagnostics")
        self.diag_btn.setCheckable(True)
        self.diag_btn.toggled.connect(self._on_diag_toggled)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear_log)
        save = QPushButton("Save log...")
        save.clicked.connect(self._save_log)
        bar.addWidget(self.diag_btn)
        bar.addWidget(clear)
        bar.addWidget(save)
        bar.addStretch(1)
        f.addLayout(bar)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("mono")
        self.log_view.setMinimumHeight(150)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setPlaceholderText("Pressed keys appear here...")
        self.log_view.setStyleSheet("font-family: Consolas, 'Cascadia Mono', monospace; font-size: 12px;")
        f.addWidget(self.log_view)
        self.summary = QLabel("")
        self.summary.setObjectName("mono")
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        f.addWidget(self.summary)
        col.addWidget(frame)
        col.addStretch(1)

        remote.keyLogged.connect(self._on_key_logged)
        remote.captured.connect(self._on_captured)
        remote.bindingsChanged.connect(self._refresh)
        self._refresh()

    # ------------------------------------------------------------------ lifecycle
    def deactivate(self) -> None:
        """Leaving the tab/page: stop diagnostics and any pending capture."""
        if self.diag_btn.isChecked():
            self.diag_btn.setChecked(False)
        self.remote.cancel_capture()
        self._capture_status.setText("")
        self._capture_for = None

    def hideEvent(self, e) -> None:  # noqa: N802
        super().hideEvent(e)
        self.deactivate()

    # ------------------------------------------------------------------ bindings
    def _refresh(self) -> None:
        m = self.remote.mapper
        self.next_label.setText("   ".join(m.next_keys))
        self.prev_label.setText("   ".join(m.previous_keys))

    def _save_bindings(self) -> None:
        m = self.remote.mapper
        self.settings.set("remote.next_keys", list(m.next_keys))
        self.settings.set("remote.previous_keys", list(m.previous_keys))
        self.settings.set("remote.debounce_ms", m.debounce_ms)
        self.settings.save()

    def _begin_capture(self, action: RemoteAction, add: bool) -> None:
        if self.diag_btn.isChecked():
            self.diag_btn.setChecked(False)
        self._capture_for, self._capture_add = action, add
        self._capture_status.setText(f"Press the key for {action.value.title()} ...  (Esc cancels)")
        self.remote.start_capture()

    def _on_captured(self, name: str) -> None:
        action = self._capture_for
        self._capture_for = None
        self._capture_status.setText("")
        if action is None:
            return
        if name == "Esc":
            return
        m = self.remote.mapper
        nxt, prv = list(m.next_keys), list(m.previous_keys)
        target, other = (nxt, prv) if action is RemoteAction.NEXT else (prv, nxt)
        if name in other:                                  # moving a key from the other button
            other.remove(name)
        if self._capture_add:
            if name not in target:
                target.append(name)
        else:
            target[:] = [name]
        try:
            self.remote.configure(nxt, prv, m.debounce_ms)
        except ValueError as exc:
            self.message.emit(str(exc), "error")
            return
        self._save_bindings()
        self.message.emit(f"{action.value.title()} is now: {name}", "success")

    def _restore_defaults(self) -> None:
        self.remote.configure(DEFAULT_NEXT_KEYS, DEFAULT_PREVIOUS_KEYS, int(self.debounce.value()))
        self._save_bindings()
        self.message.emit("Default remote keys restored", "info")

    def _on_debounce(self, value: float) -> None:
        m = self.remote.mapper
        try:
            self.remote.configure(m.next_keys, m.previous_keys, int(value))
        except ValueError:
            return
        self._save_bindings()

    def _on_dwell(self, value: float) -> None:
        self.dwellChanged.emit(int(value))

    # ------------------------------------------------------------------ diagnostics
    def _on_diag_toggled(self, on: bool) -> None:
        self.remote.set_diagnostics(on)
        self.diag_btn.setText("Stop diagnostics" if on else "Start diagnostics")
        if on:
            self.log_view.setFocus()
            self.log_view.appendPlainText("-- diagnostics on: press the remote buttons --")

    def _on_key_logged(self, rec: KeyRecord) -> None:
        self.log_view.appendPlainText(rec.line())
        self.summary.setText(self.remote.log.summary())

    def _clear_log(self) -> None:
        self.remote.log.clear()
        self.log_view.clear()
        self.summary.setText("")

    def _save_log(self) -> None:
        folder = DATA_DIR / "logs"
        default = folder / f"key_diagnostics_{datetime.now():%Y%m%d_%H%M%S}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Save the key log", str(default), "Text file (*.txt)")
        if not path:
            return
        try:
            self.remote.log.save(path)
        except OSError as exc:
            self.message.emit(f"Could not save the log: {exc}", "error")
            return
        self.message.emit(f"Key log saved: {Path(path).name}", "success")
