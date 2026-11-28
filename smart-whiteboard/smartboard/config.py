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
    index: int = 0                 # /dev/video<index> or DirectShow index (USB webcam, DroidCam/Iriun client)
    source: str = ""               # phone over Wi-Fi: stream URL, e.g. "http://192.168.1.20:8080/video"
    #                                (overrides index when not empty)
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
    ui_transitions: bool = True    # cross-fade between screens
    dwell_click: bool = False      # hold the pointer still on a button for dwell_click_s = left click (no remote)
    dwell_click_s: float = 1.3


@dataclass
class DetectionConfig:
    mode: str = "red_dot"          # "red_dot" (laser/marker) | "hand" (skin colour + fingertip)
    # ---- hand mode: skin segmentation in YCrCb (own conversion), pointer = fingertip -----------
    skin_cr_min: float = 135.0     # defaults fit many skin tones; Settings > Learn skin colour adapts them
    skin_cr_max: float = 175.0     # to the real hand under the projector light
    skin_cb_min: float = 80.0
    skin_cb_max: float = 128.0
    skin_y_min: float = 45.0       # reject dark pixels (shadows, hair, black clothes)
    hand_downscale: int = 3        # a hand is big: decimate 3x for speed
    hand_min_area: int = 80        # blob limits in downscaled pixels
    hand_max_frac: float = 0.25    # a blob larger than this fraction of the frame is not a hand (face, wall)
    tip_radius: int = 4            # fingertip = mean of the pixels this close to the farthest point
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
    search_window_px: int = 130    # once tracking, search only +-this many camera px around the last
    #                                position (3x faster); the whole board is searched if nothing is found
    core_v_min: float = 0.93       # a laser saturates the sensor: its centre is WHITE with a red halo;
    core_s_max: float = 0.35       # white pixels (V >= core_v_min, S <= core_s_max) touching red ones
    #                                are added to the dot


@dataclass
class TrackingConfig:
    min_cutoff: float = 1.5        # One-Euro filter: lower = smoother when still
    beta: float = 0.15             # higher = less lag when moving fast (0.04 -> 0.15 cut the lag error 3x)
    d_cutoff: float = 1.0
    max_lost_frames: int = 8       # keep the last position this many frames after a miss
    click_lookback_s: float = 0.10  # a click uses the pointer position this long BEFORE the key press
    #                                (pressing the remote button shakes the hand)
    click_lookback_max_px: float = 120.0   # ...unless the pointer moved further than this since then
    threaded: bool = True          # run camera + detection in their own thread


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
    points: int = 9                # 4 (corners) or 9 (3x3 grid: lens distortion can be estimated)
    estimate_distortion: bool = True   # radial distortion k1 chosen by leave-one-out cross-validation
    validation_points: int = 3
    dwell_s: float = 1.2           # hold the dot/finger still this long on a target = automatic capture (0 = off)
    dwell_px: float = 6.0          # ...'still' means moving less than this many camera pixels
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
