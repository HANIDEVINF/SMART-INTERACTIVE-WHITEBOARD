"""Persistent settings stored as JSON (config/settings.json).

The file is merged on top of DEFAULTS, so a missing or partial file always yields a
complete configuration. Writes are atomic (temp file + os.replace) so a crash while
saving can never leave a corrupted settings file behind.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.json"
DATA_DIR = PROJECT_ROOT / "data"
CALIBRATION_PATH = PROJECT_ROOT / "config" / "calibration.json"

DEFAULTS: dict[str, Any] = {
    "app": {
        "window_width": 1360,
        "window_height": 840,
        "recent_max": 8,
    },
    # Board = the logical whiteboard coordinate system (pixels). The homography maps
    # camera pixels into this rectangle; (0, 0) is the board's upper-left corner.
    "board": {
        "width": 1600,
        "height": 900,
        "paper_color_rgb": [250, 249, 246],
    },
    "pen": {
        "tool": "pen",
        "color": "#1F2937",
        "thickness": 6,
    },
    "camera": {"index": 0, "width": 1280, "height": 720, "fps": 30, "mirror": False, "autostart": True},
    # Pointer detection (HSV colour marker). HSV uses OpenCV's convention: H 0-179, S/V 0-255.
    # If hsv_low[0] > hsv_high[0] the hue range wraps around 0 (needed for red markers).
    "detection": {
        "method": "color_marker",
        "hsv_low": [35, 90, 70],
        "hsv_high": [85, 255, 255],
        "sample_hsv": [60, 200, 200],   # colour picked by the user; sensitivity widens/narrows around it
        "sensitivity": 50,              # 0..100
        "min_area": 150,                # pixels, at camera resolution
        "max_area": 40000,
        "kernel_size": 5,               # morphological structuring element (odd)
        "confidence_min": 0.35,         # blob shape validity threshold, 0..1
        "detect_width": 320,            # frames are shrunk to this width before processing
        "alpha": 0.5,                   # EMA smoothing factor, 0.05 (very smooth) .. 1.0 (raw)
        "lost_timeout_ms": 600,
        "max_jump_pct": 25,             # largest believable jump per frame, % of frame diagonal
        "confirm_frames": 2,            # frames needed to accept a far jump
    },
    "pointer": {"visible": True},      # draw the tracked pointer on the whiteboard
    "interface": {
        "hud": True,                     # mode / pen / pointer-source pill on the board
        "ripples": True,                 # rings drawn at every remote click
        "menu_scale": 1.0,               # size of the on-board menu (0.8 - 1.3)
    },
    "interaction": {
        "mode": "navigation",           # navigation | drawing | selection
        "dwell_ms": 1200,               # selection mode: time on an item before it is confirmed
    },
    "remote": {
        "next_keys": ["Right", "PgDown"],      # Next     = left click
        "previous_keys": ["Left", "PgUp"],     # Previous = right click
        "debounce_ms": 250,
    },
    # Calibration itself is stored in config/calibration.json (see core/calibration.py).
    "calibration": {"edge_margin_px": 12},
    "recent": [],
}


def _merge(base: dict, override: dict) -> None:
    """Recursively copy `override` onto `base` (in place)."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value


class Settings:
    """Dotted-key access to the JSON configuration (``settings.get("pen.color")``)."""

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_SETTINGS_PATH
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load_error: str | None = None
        self.load()

    # ------------------------------------------------------------------ io
    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                _merge(self.data, loaded)
        except FileNotFoundError:
            pass  # first run: defaults are used and the file is created on save()
        except (OSError, json.JSONDecodeError) as exc:
            self.load_error = f"Settings file could not be read ({exc}). Defaults are used."

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False)
            os.replace(tmp_name, self.path)
            return True
        except OSError:
            return False

    # -------------------------------------------------------------- access
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    # ------------------------------------------------------------- recents
    def recent_files(self) -> list[str]:
        """Recent files that still exist on disk (most recent first)."""
        return [p for p in self.data.get("recent", []) if Path(p).is_file()]

    def add_recent(self, path: str | os.PathLike) -> None:
        path = str(Path(path).resolve())
        items = [p for p in self.data.get("recent", []) if p != path]
        items.insert(0, path)
        self.data["recent"] = items[: int(self.get("app.recent_max", 8))]
        self.save()

    def reset(self) -> None:
        """Restore factory defaults (used by *Reset application*)."""
        self.data = copy.deepcopy(DEFAULTS)
        self.save()
