"""Event-loop helpers for tests that involve worker threads.

QTest.qWait() keeps the Python GIL while it spins, which starves Python worker threads (the camera
and vision threads) and makes timing-based assertions meaningless. A real QEventLoop.exec() - which is
what QApplication.exec() does in the running application - releases the GIL, so these helpers use it.
"""
from PySide6.QtCore import QEventLoop, QTimer


def run_loop(msec: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(msec, loop.quit)
    loop.exec()


def wait_until(condition, timeout_ms: int = 4000, poll_ms: int = 10) -> bool:
    if condition():
        return True
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(poll_ms)
    poll.timeout.connect(lambda: loop.quit() if condition() else None)
    poll.start()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    poll.stop()
    return bool(condition())
