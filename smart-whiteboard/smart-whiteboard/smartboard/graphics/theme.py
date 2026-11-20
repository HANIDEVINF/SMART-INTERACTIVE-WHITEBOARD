"""Colours (BGR). NO RED anywhere: the detector looks for a red dot, so the
projected interface must not contain bright saturated red."""

BG = (38, 30, 24)              # dark slate: projects as little light, dot stands out
PANEL = (62, 50, 40)
PANEL_LIGHT = (86, 72, 58)
BUTTON = (90, 70, 52)
BUTTON_HOVER = (150, 110, 70)
BUTTON_ACTIVE = (200, 150, 60)
TEXT = (245, 240, 235)
TEXT_DIM = (180, 170, 160)
ACCENT = (230, 190, 60)        # cyan-ish blue
GOOD = (110, 210, 120)         # green
WARN = (60, 170, 255)          # orange (hue ~30deg, not red)
WHITE = (255, 255, 255)

# drawing palette (name, BGR)  -- yellow / cyan / green / white / magenta
PEN_COLORS = [
    ("Yellow", (0, 225, 255)),
    ("Cyan", (255, 220, 40)),
    ("Green", (90, 230, 110)),
    ("White", (255, 255, 255)),
    ("Magenta", (255, 90, 230)),
]
PEN_SIZES = [("Thin", 3), ("Medium", 7), ("Thick", 14)]
