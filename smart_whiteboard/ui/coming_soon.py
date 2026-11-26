"""Roadmap page shown for sections that are implemented in a later development phase.

It is deliberately *not* a fake feature: it states which phase delivers the section and what
it will contain, and offers a working way back.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui import icons


class ComingSoonPage(QWidget):
    homeRequested = Signal()

    def __init__(self, icon_name: str, title: str, phase: str, summary: str, items: list[str],
                 accent: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(44, 34, 44, 30)
        outer.addStretch(1)

        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMaximumWidth(640)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(36, 32, 36, 30)
        lay.setSpacing(14)

        chip = QLabel()
        chip.setFixedSize(64, 64)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setPixmap(icons.pixmap(icon_name, "#FFFFFF", 30))
        chip.setStyleSheet(f"background: {accent}; border-radius: 20px;")
        lay.addWidget(chip)

        head = QHBoxLayout()
        name = QLabel(title)
        name.setObjectName("h2")
        pill = QLabel(phase)
        pill.setObjectName("pill")
        head.addWidget(name)
        head.addWidget(pill, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addStretch(1)
        lay.addLayout(head)

        text = QLabel(summary)
        text.setObjectName("muted")
        text.setWordWrap(True)
        lay.addWidget(text)

        for entry in items:
            row = QLabel(f"-  {entry}")
            row.setWordWrap(True)
            lay.addWidget(row)

        back = QPushButton("  Back to Home")
        back.setObjectName("primary")
        back.setIcon(icons.icon("arrow-left", "#FFFFFF", 18))
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self.homeRequested)
        lay.addSpacing(8)
        lay.addWidget(back, 0, Qt.AlignmentFlag.AlignLeft)

        outer.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(2)
