"""Environment check: verifies dependencies, camera and imports.

Run:  python tools/check_env.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check_import(name: str) -> bool:
    try:
        importlib.import_module(name)
        print(f"  OK   {name}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL {name}: {exc}")
        return False


def main() -> int:
    print(f"Python {sys.version.split()[0]} on {sys.platform}")
    print("Dependencies:")
    ok = all([
        check_import("numpy"),
        check_import("cv2"),
        check_import("pygame"),
        check_import("pynput"),
        check_import("pytest"),
    ])

    print("\nProject imports:")
    for mod in ["utils.image_processing", "utils.geometry",
                "detection.color_detector", "detection.tracker",
                "calibration.calibration_manager", "interaction.event_manager",
                "interface.app"]:
        ok = check_import(mod) and ok

    print("\nCamera probe:")
    try:
        import cv2
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            print(f"  Camera opened, frame={'OK' if ret else 'FAILED'}"
                  f" shape={None if frame is None else frame.shape}")
            cap.release()
        else:
            print("  No camera detected (simulated source still works).")
    except Exception as exc:  # noqa: BLE001
        print(f"  Camera probe error: {exc}")

    print("\n" + ("Environment OK" if ok else "Some checks FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
