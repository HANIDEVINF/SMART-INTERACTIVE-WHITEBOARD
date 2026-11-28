"""Visual theme (colours are BGR tuples).

IMPORTANT: the detector looks for a RED dot, so nothing projected may have a
red hue (hue within ~35 degrees of 0/360 with high saturation).  Every
colour below is blue / cyan / green / yellow / violet; tests/test_app.py
runs the red-dot detector on every rendered screen to prove it.
"""
import numpy as np


def rgb(r, g, b):
    return (b, g, r)


# ---- surfaces ---------------------------------------------------------------------------
BG_TOP = rgb(8, 12, 28)
BG_BOT = rgb(22, 30, 64)
BG = rgb(14, 20, 44)                  # flat fallback
PANEL = rgb(16, 23, 50)
PANEL_LIGHT = rgb(36, 48, 92)
LINE = rgb(58, 74, 130)
CARD_TOP, CARD_BOT = rgb(44, 58, 108), rgb(28, 38, 78)
CARD_HOVER_TOP, CARD_HOVER_BOT = rgb(70, 92, 168), rgb(46, 62, 124)

# ---- text -------------------------------------------------------------------------------
TEXT = rgb(241, 245, 255)
TEXT_DIM = rgb(148, 163, 200)
WHITE = (255, 255, 255)

# ---- accents (all hue >= 40 deg) --------------------------------------------------------
CYAN = rgb(34, 211, 238)
SKY = rgb(56, 189, 248)
VIOLET = rgb(139, 112, 250)
EMERALD = rgb(52, 211, 153)
AMBER = rgb(251, 191, 36)
LIME = rgb(163, 230, 53)
SLATE = rgb(148, 163, 184)
ACCENT = CYAN
GOOD = EMERALD
WARN = AMBER

# one accent per main-menu card
CARD_ACCENTS = [SKY, VIOLET, EMERALD, AMBER, CYAN, SLATE]

# ---- drawing ----------------------------------------------------------------------------
PEN_COLORS = [
    ("Amber", AMBER), ("Cyan", CYAN), ("Green", EMERALD),
    ("White", WHITE), ("Violet", rgb(167, 139, 250)), ("Ink", rgb(15, 23, 42)),
]
PEN_SIZES = [("Thin", 3), ("Medium", 7), ("Thick", 14)]
BOARDS = [("Dark", None), ("Light", rgb(244, 247, 252)), ("Grid", "grid")]
BOARD_LIGHT = rgb(244, 247, 252)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def dim(c, k):
    """Multiply a colour by k (0..1)."""
    return tuple(int(v * k) for v in c)


def make_background(w: int, h: int, orbs=()) -> np.ndarray:
    """Cached backdrop: diagonal gradient + vignette + faint dot grid.
    ``orbs`` = [(fx, fy, radius_fraction, colour)] soft coloured light spots."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = np.clip(0.65 * yy / h + 0.35 * xx / w, 0, 1)[..., None]
    img = np.asarray(BG_TOP, np.float32) * (1 - t) + np.asarray(BG_BOT, np.float32) * t
    for fx, fy, fr, col in orbs:
        q = np.clip(1.0 - np.hypot(xx - fx * w, yy - fy * h) / (fr * w), 0, 1)
        img += (q * q * 0.55)[..., None] * np.asarray(col, np.float32) * 0.5
    d = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))[..., None]
    img *= np.clip(1.12 - 0.28 * d * d, 0.55, 1.0)
    img = np.clip(img, 0, 255).astype(np.uint8)
    step = max(24, int(round(h / 22)))
    dot = np.asarray(LINE, np.float32) * 0.55
    for oy in (0, 1):
        for ox in (0, 1):
            sub = img[step // 2 + oy::step, step // 2 + ox::step]
            sub[:] = np.clip(sub.astype(np.float32) * 0.5 + dot, 0, 255).astype(np.uint8)
    return img


def make_grid_board(w: int, h: int, base) -> np.ndarray:
    """Board background with a light square grid (for drawing graphs)."""
    img = np.empty((h, w, 3), np.uint8)
    img[:] = base
    step = max(20, h // 18)
    line = lerp(base, WHITE if sum(base) < 380 else (0, 0, 0), 0.10)
    img[::step, :] = line
    img[:, ::step] = line
    return img
