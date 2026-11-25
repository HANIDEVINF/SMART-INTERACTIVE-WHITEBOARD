"""LuminaBoard - Smart Interactive Whiteboard (USTHB Computer Vision project).

Run:    python main.py
Check:  python main.py --smoke      (builds the window offscreen, then exits with code 0)
"""
from __future__ import annotations

import os
import sys

MIN_PYTHON = (3, 10)


def _fail(message: str) -> None:
    print(f"\n[LuminaBoard] {message}\n", file=sys.stderr)
    sys.exit(1)


def main(argv: list[str]) -> int:
    smoke = "--smoke" in argv
    if smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    if sys.version_info < MIN_PYTHON:
        _fail(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required (found {sys.version.split()[0]}).")

    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import PIL  # noqa: F401
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # missing dependency -> clear instruction instead of a traceback
        _fail(f"A required package is missing: {exc.name}.\n"
              "Activate the virtual environment and run:  pip install -r requirements.txt")

    from core.app_state import AppState
    from core.settings import Settings
    from ui.main_window import MainWindow
    from ui.styles import APP_NAME, STYLESHEET

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("USTHB")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)

    settings = Settings()
    state = AppState()
    window = MainWindow(settings, state)
    window.show()

    if smoke:
        QTimer.singleShot(600, app.quit)
        code = app.exec()
        print(f"[LuminaBoard] smoke test OK (Python {sys.version.split()[0]}, "
              f"OpenCV {cv2.__version__}, NumPy {numpy.__version__}, Qt platform: "
              f"{app.platformName()})")
        return code
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
