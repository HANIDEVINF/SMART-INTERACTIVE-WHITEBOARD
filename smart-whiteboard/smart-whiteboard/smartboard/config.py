"""Central configuration (loaded from config.json, every field has a default).

Edit config.json - never the source - to adapt the system to a new room,
camera, projector or remote.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields, is_dataclass, asdict
from typing import List, Optional


@dataclass
class CameraConfig:
    index: int = 0                 # /dev/video<index> or DirectShow index
    width: int = 1280
    height: int = 720
    fps: int = 30
    fourcc: str = "MJPG"           # MJPG is needed for 720p@30 on most USB cams
    backend: str = "auto"          # auto | dshow | msmf | v4l2
    flip_horizontal: bool = False  # mirror image if the camera is mounted facing back
    flip_vertical: bool = False
    exposure: Optional[float] = None  # set a LOW manual exposure: makes the dot stand out
    # (value depends on driver; on Linux/V4L2 try -6..-2, on Windows -8..-3)


@dataclass
class DisplayConfig:
    width: int = 1920              # board coordinate system = projected screen pixels
    height: int = 1080
    fullscreen: bool = True
    window_x: int = 0              # move the window to the projector monitor (e.g. 1920)
    window_y: int = 0
    window_name: str = "Smart Whiteboard"
    show_debug: bool = True        # secondary window with the camera view / mask


@dataclass
class DetectionConfig:
    hue_tolerance: float = 22.0    # degrees around pure red (hue 0)
    sat_min: float = 0.45          # 0..1  min saturation
    val_min: float = 0.75          # 0..1  min brightness (the dot must be brighter than the slide)
    downscale: int = 2             # process every k-th pixel (speed)
    min_area: int = 3              # blob area limits, in downscaled pixels
    max_area: int = 900
    denoise_neighbors: int = 3     # 3x3 majority filter (1 = off)
    merge_radius: int = 1          # dilation used only to link pieces of one blob
    roi_margin: float = 0.04       # enlarge the calibrated board region by 4 % when masking
    prior_gate_px: float = 150.0   # prefer blobs close to the previous position


@dataclass
class TrackingConfig:
    min_cutoff: float = 1.5        # One-Euro filter: lower = smoother when still
    beta: float = 0.04             # higher = less lag when moving fast
    d_cutoff: float = 1.0
    max_lost_frames: int = 8       # keep the last position this many frames after a miss


@dataclass
class RemoteConfig:
    backend: str = "opencv"        # opencv (window focus needed) | pynput (global keyboard hook)
    # Codes returned by cv2.waitKeyEx().  Run  python tools/key_finder.py  to see yours.
    # PageDown / Right / n   -> "Next"      -> LEFT click
    next_codes: List[int] = field(default_factory=lambda: [2228224, 65366, 2555904, 65363, ord("n")])
    # PageUp / Left / p      -> "Previous"  -> RIGHT click
    prev_codes: List[int] = field(default_factory=lambda: [2162688, 65365, 2424832, 65361, ord("p")])
    # names used only by the pynput backend (pynput.keyboard.Key.<name> or a single character)
    next_names: List[str] = field(default_factory=lambda: ["page_down", "right", "n"])
    prev_names: List[str] = field(default_factory=lambda: ["page_up", "left", "p"])
    debounce_s: float = 0.15       # ignore repeated codes closer than this


@dataclass
class CalibrationConfig:
    file: str = "calibration.json"
    target_margin: float = 0.06    # targets are placed this fraction inside the screen edges
    validation_points: int = 3
    ok_error_px: float = 25.0      # mean error (board pixels) considered "good"


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    remote: RemoteConfig = field(default_factory=RemoteConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    assets_dir: str = "assets"
    show_trail: bool = True


def _merge(obj, data: dict) -> None:
    """Recursively copy values of ``data`` into the dataclass ``obj``."""
    for f in fields(obj):
        if f.name not in data:
            continue
        cur = getattr(obj, f.name)
        if is_dataclass(cur) and isinstance(data[f.name], dict):
            _merge(cur, data[f.name])
        else:
            setattr(obj, f.name, data[f.name])


def load_config(path: str = "config.json") -> Config:
    cfg = Config()
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            _merge(cfg, json.load(fh))
    return cfg


def save_config(cfg: Config, path: str = "config.json") -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(asdict(cfg), fh, indent=2)
