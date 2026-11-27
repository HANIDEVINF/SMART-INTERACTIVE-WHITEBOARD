"""Remote key detector.

Press the buttons of your presentation remote (or any keys) and this tool
prints the key names pynput receives.  Use the printed names in
config/settings.json under "remote_keys" ("left" / "right").

Run:  python tools/remote_key_detector.py
Stop: Ctrl+C
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _key_name(key) -> str:
    name = getattr(key, "name", None)
    if name:
        return f"name={name}"
    char = getattr(key, "char", None)
    if char:
        return f"char={char!r}"
    return f"vk={getattr(key, 'vk', '?')}"


def main() -> None:
    try:
        from pynput import keyboard
    except ImportError:
        print("pynput is not installed. Run: pip install pynput")
        sys.exit(1)

    print("Remote key detector running. Press your remote buttons now.")
    print("Press Ctrl+C to stop.\n")

    def on_press(key):
        print(f"[{time.strftime('%H:%M:%S')}] PRESS  {_key_name(key)}")

    def on_release(key):
        print(f"[{time.strftime('%H:%M:%S')}] RELEASE {_key_name(key)}")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
