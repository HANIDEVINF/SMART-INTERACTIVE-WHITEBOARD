"""Generate the sample images shown in the image-viewer gallery.

Run:  python tools/make_sample_images.py

Writes three teaching images to assets/images/.  They are produced with
NumPy only (no external files), so the project stays self-contained.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pygame

OUT = Path(__file__).resolve().parent.parent / "assets" / "images"
W, H = 1280, 800


def _save(arr: np.ndarray, name: str) -> None:
    # arr is (H, W, 3) uint8 -> pygame wants (W, H) surfarray order.
    surf = pygame.image.frombuffer(arr.tobytes(), (arr.shape[1], arr.shape[0]),
                                   "RGB")
    OUT.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(OUT / name))
    print("wrote", OUT / name)


def hsv_hue_bands() -> np.ndarray:
    """Hue sweep (0-360 degrees) with saturation falling top -> bottom."""
    x = np.linspace(0, 360, W)[None, :].repeat(H, 0)
    sat = np.linspace(1.0, 0.0, H)[:, None].repeat(W, 1)
    val = np.ones_like(sat)
    c = val * sat
    hp = x / 60.0
    xx = c * (1 - np.abs(hp % 2 - 1))
    z = np.zeros_like(c)
    sector = hp.astype(int) % 6
    rgb = np.zeros((H, W, 3))
    table = [(c, xx, z), (xx, c, z), (z, c, xx), (z, xx, c), (xx, z, c),
             (c, z, xx)]
    for k, (r, g, b) in enumerate(table):
        m = sector == k
        rgb[m] = np.stack([r[m], g[m], b[m]], axis=1)
    rgb += (val - c)[..., None]
    return (rgb * 255).astype(np.uint8)


def perspective_grid() -> np.ndarray:
    """A chessboard seen in perspective: why a homography is needed.

    Each pixel below the horizon is mapped back to the floor plane
    (x = column offset / depth, z = 1 / depth): equal squares on the floor
    appear smaller and more squeezed with distance.  The depth is limited
    so the far squares stay larger than a pixel (no moire).
    """
    horizon = 200.0
    v, u = np.mgrid[0:H, 0:W].astype(float)
    depth = np.maximum(v - horizon, 1.0)
    X = (u - W / 2) / depth * 1.6          # floor x, in tiles
    Z = 520.0 / (depth + 30.0)             # floor z, in tiles
    tile = ((np.floor(X) + np.floor(Z)) % 2).astype(bool)
    floor = np.where(tile[..., None], 40, 232).astype(np.uint8).repeat(3, 2)
    img = floor
    sky = np.linspace(150, 225, int(horizon))[:, None, None]
    sky_rgb = np.concatenate([sky * 0.7, sky * 0.85, sky], 2).repeat(W, 1)
    img[: int(horizon)] = sky_rgb.astype(np.uint8)
    return img


def rgb_channels() -> np.ndarray:
    """Three overlapping discs: an image is the sum of R, G and B."""
    v, u = np.mgrid[0:H, 0:W].astype(float)
    img = np.zeros((H, W, 3), dtype=np.uint8)
    for ch, (cx, cy) in enumerate([(W * .38, H * .40), (W * .62, H * .40),
                                   (W * .50, H * .62)]):
        disc = (u - cx) ** 2 + (v - cy) ** 2 < (H * .27) ** 2
        img[..., ch][disc] = 255
    return img


if __name__ == "__main__":
    pygame.init()
    _save(hsv_hue_bands(), "hsv_colour_map.png")
    _save(perspective_grid(), "perspective_chessboard.png")
    _save(rgb_channels(), "rgb_channels.png")
