"""Application configuration: defaults, loading and saving.

All tunable values live here so the rest of the code never hard-codes
them.  Settings are persisted to ``config/settings.json``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from utils.file_utils import CONFIG_DIR, load_json, save_json

logger = logging.getLogger(__name__)

SETTINGS_PATH = CONFIG_DIR / "settings.json"
CALIBRATION_PATH = CONFIG_DIR / "calibration.json"

DEFAULT_SETTINGS = {
    # --- camera -----------------------------------------------------------
    "camera_index": 0,
    "camera_width": 1280,
    "camera_height": 720,
    "camera_source": "real",          # "real" | "simulated"
    # --- pointer ----------------------------------------------------------
    "pointer_mode": "auto",           # "camera" | "mouse" | "auto"
    # --- marker HSV thresholds (degrees / 0..1) ---------------------------
    "marker_hsv": {
        "h_min": 60.0, "h_max": 150.0,  # green marker default (hue ~120)
        "s_min": 0.35, "s_max": 1.0,
        "v_min": 0.35, "v_max": 1.0,
    },
    "marker_min_area": 400,           # px^2, rejects noise blobs
    "marker_max_area_ratio": 0.25,    # reject blobs > 25% of frame
    # --- tracking ---------------------------------------------------------
    "tracking_alpha": 0.45,           # EMA smoothing factor (0..1)
    "tracking_max_jump": 250.0,       # px/frame jump rejection threshold
    "tracking_loss_timeout": 1.5,     # s before pointer is reported lost
    # --- remote -----------------------------------------------------------
    "remote_mode": "auto",            # "physical" | "keyboard" | "auto"
    "remote_keys": {
        "left": "page_down",          # presentation remote button 1
        "right": "page_up",           # presentation remote button 2
    },
    "sim_keys": {
        "left": "z",
        "right": "x",
    },
    # --- display ----------------------------------------------------------
    "display_width": 1280,
    "display_height": 720,
    "fullscreen": False,
    # --- drawing ----------------------------------------------------------
    "pen_colors": ["#e53935", "#1e88e5", "#43a047", "#212121"],
    "pen_thicknesses": [3, 6, 10, 16],
    "history_limit": 40,              # max undo steps kept in memory
    # --- export -----------------------------------------------------------
    "export_dir": "output",
}


def load_settings() -> dict:
    """Load settings.json merged over the defaults (deep-merged)."""
    data = load_json(SETTINGS_PATH, default={})
    settings = _deep_merge(DEFAULT_SETTINGS, data if isinstance(data, dict) else {})
    return settings


def save_settings(settings: dict) -> bool:
    return save_json(SETTINGS_PATH, settings)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into ``base`` without mutating base."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_calibration():
    """Return saved board calibration dict or None."""
    data = load_json(CALIBRATION_PATH, default=None)
    if not isinstance(data, dict):
        return None
    required = {"camera_points", "board_size", "homography"}
    if not required.issubset(data.keys()):
        logger.warning("Calibration file incomplete, ignoring it.")
        return None
    return data


def save_calibration(camera_points, board_size, homography) -> bool:
    """Persist calibration: clicked camera points, board size and the
    homography matrix (stored as nested lists for JSON)."""
    import numpy as np
    data = {
        "camera_points": [list(map(float, p)) for p in camera_points],
        "board_size": list(map(int, board_size)),
        "homography": np.asarray(homography, dtype=float).tolist(),
    }
    return save_json(CALIBRATION_PATH, data)
