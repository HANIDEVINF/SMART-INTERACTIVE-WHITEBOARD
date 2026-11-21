"""ui.py - Primitives de dessin (NumPy, bords anti-aliases) + icones + widget Button.
Aucune logique d'application ici."""
import cv2
import numpy as np
import config as C

FONT = cv2.FONT_HERSHEY_COMPLEX          # serif
FONT_TITLE = cv2.FONT_HERSHEY_SCRIPT_COMPLEX  # calligraphie
FONT_SUB = cv2.FONT_HERSHEY_TRIPLEX
_alpha_cache, _bg_cache = {}, {}


def shade(c, f):
    """Eclaircit (f>1) ou assombrit (f<1) une couleur."""
    return tuple(int(min(255, max(0, v * f))) for v in c)


def _paint(img, x, y, alpha, color):
    """Melange 'color' sur img[y:y+h, x:x+w] avec un masque alpha (h,w) en [0,1]."""
    H, W = img.shape[:2]
    h, w = alpha.shape
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    a = alpha[y0 - y:y1 - y, x0 - x:x1 - x][..., None]
    col = np.asarray(color, np.float32)
    if col.ndim == 3:
        col = col[y0 - y:y1 - y]
    reg = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = (reg * (1 - a) + col * a).astype(np.uint8)


def rounded_alpha(w, h, r):
    """Masque anti-alias d'un rectangle arrondi (distance signee), mis en cache."""
    key = (w, h, r)
    if key not in _alpha_cache:
        r = min(r, w / 2, h / 2)
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        px = np.abs(xs + 0.5 - w / 2) - (w / 2 - r)
        py = np.abs(ys + 0.5 - h / 2) - (h / 2 - r)
        sdf = np.hypot(np.maximum(px, 0), np.maximum(py, 0)) + np.minimum(np.maximum(px, py), 0) - r
        _alpha_cache[key] = np.clip(0.5 - sdf, 0, 1)
    return _alpha_cache[key]


def fill_rect(img, x, y, w, h, color):
    H, W = img.shape[:2]
    x0, y0, x1, y1 = max(int(x), 0), max(int(y), 0), min(int(x + w), W), min(int(y + h), H)
    if x0 < x1 and y0 < y1:
        img[y0:y1, x0:x1] = color


def fill_gradient(img, x, y, w, h, c_top, c_bot):
    t = np.linspace(0, 1, h)[:, None, None]
    img[y:y + h, x:x + w] = (np.array(c_top) * (1 - t) + np.array(c_bot) * t).astype(np.uint8)


def fill_rounded(img, x, y, w, h, r, color, alpha=1.0):
    x, y, w, h, r = (int(round(v)) for v in (x, y, w, h, r))
    if w > 0 and h > 0:
        _paint(img, x, y, rounded_alpha(w, h, max(r, 0)) * alpha, color)


def fill_rounded_grad(img, x, y, w, h, r, c_top, c_bot):
    x, y, w, h, r = (int(round(v)) for v in (x, y, w, h, r))
    t = np.linspace(0, 1, h)[:, None, None]
    col = (np.array(c_top, np.float32) * (1 - t) + np.array(c_bot, np.float32) * t)
    _paint(img, x, y, rounded_alpha(w, h, r), col)


def draw_rounded_border(img, x, y, w, h, r, color, t=2):
    outer = rounded_alpha(w, h, r)
    inner = np.zeros_like(outer)
    if w - 2 * t > 0 and h - 2 * t > 0:
        inner[t:h - t, t:w - t] = rounded_alpha(w - 2 * t, h - 2 * t, max(r - t, 1))
    _paint(img, x, y, np.clip(outer - inner, 0, 1), color)


def draw_shadow(img, x, y, w, h, r, off=6):
    """Ombre douce : 3 rectangles arrondis noirs semi-transparents de plus en plus grands."""
    for g, a in ((12, 0.07), (8, 0.10), (4, 0.14)):
        fill_rounded(img, x - g, y - g + off, w + 2 * g, h + 2 * g, r + g, (0, 0, 0), a)


def blend_disc(img, cx, cy, r, color, alpha=1.0):
    x0, y0, n = int(cx - r - 2), int(cy - r - 2), int(2 * r + 5)
    ys, xs = np.mgrid[0:n, 0:n]
    d = np.hypot(xs + x0 - cx, ys + y0 - cy)
    _paint(img, x0, y0, np.clip(r - d + 0.5, 0, 1) * alpha, color)


def stamp_disc(img, cx, cy, r, color):
    """Disque plein anti-alias (brique de base du trait epais)."""
    blend_disc(img, cx, cy, r, color, 1.0)


def draw_ring(img, cx, cy, r_out, r_in, color, alpha=1.0):
    x0, y0, n = int(cx - r_out - 2), int(cy - r_out - 2), int(2 * r_out + 5)
    ys, xs = np.mgrid[0:n, 0:n]
    d = np.hypot(xs + x0 - cx, ys + y0 - cy)
    a = np.clip(r_out - d + 0.5, 0, 1) * np.clip(d - r_in + 0.5, 0, 1)
    _paint(img, x0, y0, a * alpha, color)


def draw_line(img, p0, p1, thickness, color):
    """Segment epais : on 'tamponne' des disques le long du segment."""
    r = max(thickness / 2.0, 0.5)
    (x0, y0), (x1, y1) = p0, p1
    n = int(np.hypot(x1 - x0, y1 - y0) / max(r / 2.0, 1.0)) + 1
    for t in np.linspace(0, 1, n + 1):
        stamp_disc(img, x0 + t * (x1 - x0), y0 + t * (y1 - y0), r, color)


def resize_nearest(img, h, w):
    """Redimensionnement plus-proche-voisin par indexation NumPy (zoom)."""
    ys = (np.arange(h) * img.shape[0] / h).astype(int)
    xs = (np.arange(w) * img.shape[1] / w).astype(int)
    return img[ys][:, xs]


def put_text(img, text, x, y, scale=0.8, color=C.TEXT, thick=2, center=False, shadow=False, vmid=False, font=None):
    font = font or FONT
    (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
    if center:
        x, y = x - tw // 2, y + th // 2
    elif vmid:
        y = y + th // 2
    x, y = int(x), int(y)
    if shadow:
        cv2.putText(img, text, (x + 2, y + 3), font, scale, (0, 0, 0), thick + 1, cv2.LINE_AA)
    cv2.putText(img, text, (x, y), font, scale, color, thick, cv2.LINE_AA)


def diamond(img, cx, cy, r, color, alpha=1.0):
    """Losange plein anti-alias (motif victorien)."""
    x0, y0, n = int(cx - r - 2), int(cy - r - 2), int(2 * r + 5)
    ys, xs = np.mgrid[0:n, 0:n]
    d = np.abs(xs + x0 - cx) + np.abs(ys + y0 - cy)
    _paint(img, x0, y0, np.clip(r - d + 0.5, 0, 1) * alpha, color)


def draw_border(img, x, y, w, h, color, t=2):
    fill_rect(img, x, y, w, t, color)
    fill_rect(img, x, y + h - t, w, t, color)
    fill_rect(img, x, y, t, h, color)
    fill_rect(img, x + w - t, y, t, h, color)


def draw_frame(img, x, y, w, h):
    """Cadre orne : filet dore epais + filet fin interieur + losanges aux coins."""
    draw_border(img, x, y, w, h, C.GOLD, 3)
    draw_border(img, x + 7, y + 7, w - 14, h - 14, C.GOLD_DARK, 1)
    for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        draw_ring(img, cx, cy, 52, 49, C.GOLD)            # eventails de coin
        draw_ring(img, cx, cy, 42, 41, C.GOLD_DARK)
        draw_ring(img, cx, cy, 32, 30, C.GOLD)
        diamond(img, cx, cy, 12, C.GOLD_LIGHT)
        diamond(img, cx, cy, 5, C.BG_BOTTOM)


def flourish(img, cx, cy, half_w, color=C.GOLD):
    """Separateur orne : filets + losange central + petits ornements."""
    fill_rect(img, cx - half_w, cy - 1, half_w - 30, 2, color)
    fill_rect(img, cx + 30, cy - 1, half_w - 30, 2, color)
    diamond(img, cx, cy, 11, C.GOLD_LIGHT)
    for k in (-1, 1):
        diamond(img, cx + k * 22, cy, 5, color)
        stamp_disc(img, cx + k * half_w, cy, 3.5, color)


def damask_alpha(h, w, tile=72):
    """Motif damasse repetitif (losanges + points) sous forme de masque alpha."""
    ys, xs = np.mgrid[0:tile, 0:tile]
    dx, dy = xs - tile / 2 + 0.5, ys - tile / 2 + 0.5
    d1 = np.abs(dx) + np.abs(dy)
    a = ((d1 <= 20) & (d1 >= 16)).astype(np.float32) + (np.hypot(dx, dy) <= 4)
    cd = np.minimum(xs, tile - xs) + np.minimum(ys, tile - ys)   # distance au coin du motif
    a = a + ((cd <= 8) & (cd >= 5))
    return np.tile(np.clip(a, 0, 1), (h // tile + 1, w // tile + 1))[:h, :w]


def get_background(decor=True):
    """Velours bordeaux en degrade ; decor=True ajoute damas, vignette et cadre dore (cache)."""
    if decor not in _bg_cache:
        t = np.linspace(0, 1, C.UI_H)[:, None, None]
        col = np.array(C.BG_TOP) * (1 - t) + np.array(C.BG_BOTTOM) * t
        img = (col * np.ones((1, C.UI_W, 1))).astype(np.uint8)
        if decor:
            _paint(img, 0, 0, damask_alpha(C.UI_H, C.UI_W) * 0.10, C.GOLD)
            ys, xs = np.mgrid[0:C.UI_H, 0:C.UI_W]
            r2 = ((xs - C.UI_W / 2) / (C.UI_W / 2)) ** 2 + ((ys - C.UI_H / 2) / (C.UI_H / 2)) ** 2
            img = (img * (1 - 0.30 * np.clip(r2 / 2, 0, 1))[..., None]).astype(np.uint8)  # vignette
            draw_frame(img, 10, 10, C.UI_W - 20, C.UI_H - 20)
        _bg_cache[decor] = img
    return _bg_cache[decor]


def draw_pointer(img, pos):
    """Pointeur : halo + contour sombre + anneau + 4 reperes + point central."""
    x, y = pos
    blend_disc(img, x, y, 38, C.POINTER_COLOR, 0.22)
    draw_ring(img, x, y, 25, 13, (20, 8, 30), 0.55)
    draw_ring(img, x, y, 21, 16, C.POINTER_COLOR)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        draw_line(img, (x + dx * 25, y + dy * 25), (x + dx * 34, y + dy * 34), 3, C.POINTER_COLOR)
    stamp_disc(img, x, y, 7, (20, 8, 30))
    stamp_disc(img, x, y, 5, (255, 255, 255))
    stamp_disc(img, x, y, 2.5, C.POINTER_COLOR)


# ------------------------------------------------------------------ icones (dessinees avec les primitives)
def _poly(img, pts, t, col):
    for a, b in zip(pts, pts[1:]):
        draw_line(img, a, b, t, col)


def icon_home(img, cx, cy, s, col):
    _poly(img, [(cx - 18 * s, cy - s), (cx, cy - 18 * s), (cx + 18 * s, cy - s)], 5 * s, col)
    fill_rounded(img, cx - 12 * s, cy - 2 * s, 24 * s, 18 * s, 3 * s, col)
    fill_rounded(img, cx - 4 * s, cy + 6 * s, 8 * s, 10 * s, 2 * s, C.PANEL)


def icon_back(img, cx, cy, s, col):
    _poly(img, [(cx + 16 * s, cy), (cx - 16 * s, cy)], 5 * s, col)
    _poly(img, [(cx - 4 * s, cy - 12 * s), (cx - 16 * s, cy), (cx - 4 * s, cy + 12 * s)], 5 * s, col)


def icon_next(img, cx, cy, s, col):
    _poly(img, [(cx - 16 * s, cy), (cx + 16 * s, cy)], 5 * s, col)
    _poly(img, [(cx + 4 * s, cy - 12 * s), (cx + 16 * s, cy), (cx + 4 * s, cy + 12 * s)], 5 * s, col)


def icon_plus(img, cx, cy, s, col):
    _poly(img, [(cx - 14 * s, cy), (cx + 14 * s, cy)], 5 * s, col)
    _poly(img, [(cx, cy - 14 * s), (cx, cy + 14 * s)], 5 * s, col)


def icon_minus(img, cx, cy, s, col):
    _poly(img, [(cx - 14 * s, cy), (cx + 14 * s, cy)], 5 * s, col)


def icon_fit(img, cx, cy, s, col):
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = cx + sx * 14 * s, cy + sy * 14 * s
            _poly(img, [(px, py + sy * -8 * s), (px, py), (px + sx * -8 * s, py)], 4 * s, col)


def icon_trash(img, cx, cy, s, col):
    _poly(img, [(cx - 14 * s, cy - 10 * s), (cx + 14 * s, cy - 10 * s)], 4 * s, col)
    _poly(img, [(cx - 5 * s, cy - 10 * s), (cx - 5 * s, cy - 15 * s), (cx + 5 * s, cy - 15 * s),
                (cx + 5 * s, cy - 10 * s)], 3 * s, col)
    fill_rounded(img, cx - 11 * s, cy - 6 * s, 22 * s, 22 * s, 4 * s, col)
    for dx in (-4, 4):
        _poly(img, [(cx + dx * s, cy - s), (cx + dx * s, cy + 11 * s)], 2.5 * s, C.PANEL)


def icon_pencil(img, cx, cy, s, col):
    draw_line(img, (cx - 6 * s, cy + 6 * s), (cx + 13 * s, cy - 13 * s), 9 * s, col)
    draw_line(img, (cx - 16 * s, cy + 16 * s), (cx - 9 * s, cy + 9 * s), 4 * s, col)


def icon_image(img, cx, cy, s, col):
    draw_rounded_border(img, int(cx - 17 * s), int(cy - 13 * s), int(34 * s), int(26 * s), int(5 * s), col, max(2, int(3 * s)))
    stamp_disc(img, cx + 8 * s, cy - 5 * s, 3.5 * s, col)
    _poly(img, [(cx - 14 * s, cy + 9 * s), (cx - 5 * s, cy - 2 * s), (cx + 2 * s, cy + 6 * s),
                (cx + 7 * s, cy + 1 * s), (cx + 14 * s, cy + 9 * s)], 3.5 * s, col)


def icon_book(img, cx, cy, s, col):
    fill_rounded(img, cx - 18 * s, cy - 12 * s, 17 * s, 26 * s, 3 * s, col)
    fill_rounded(img, cx + 1 * s, cy - 12 * s, 17 * s, 26 * s, 3 * s, col)
    for k in (-5, 1, 7):
        _poly(img, [(cx - 14 * s, cy + k * s), (cx - 5 * s, cy + k * s)], 2 * s, C.PANEL)
        _poly(img, [(cx + 5 * s, cy + k * s), (cx + 14 * s, cy + k * s)], 2 * s, C.PANEL)


def icon_gear(img, cx, cy, s, col):
    draw_ring(img, cx, cy, 13 * s, 6 * s, col)
    for k in range(8):
        a = k * np.pi / 4
        stamp_disc(img, cx + 15 * s * np.cos(a), cy + 15 * s * np.sin(a), 3.5 * s, col)


def icon_camera(img, cx, cy, s, col):
    fill_rounded(img, cx - 17 * s, cy - 9 * s, 34 * s, 24 * s, 5 * s, col)
    fill_rounded(img, cx - 7 * s, cy - 14 * s, 14 * s, 8 * s, 2 * s, col)
    stamp_disc(img, cx, cy + 3 * s, 7 * s, C.PANEL)
    stamp_disc(img, cx, cy + 3 * s, 4 * s, col)


def icon_target(img, cx, cy, s, col):
    draw_ring(img, cx, cy, 16 * s, 12 * s, col)
    stamp_disc(img, cx, cy, 6 * s, col)


def icon_close(img, cx, cy, s, col):
    _poly(img, [(cx - 12 * s, cy - 12 * s), (cx + 12 * s, cy + 12 * s)], 5 * s, col)
    _poly(img, [(cx + 12 * s, cy - 12 * s), (cx - 12 * s, cy + 12 * s)], 5 * s, col)


ICONS = {n[5:]: f for n, f in list(globals().items()) if n.startswith("icon_")}


class Button:
    """Bouton arrondi avec ombre, degrade, icone optionnelle et sous-titre optionnel.
    icon(img, cx, cy, s, color) ; s = facteur d'echelle (1.0 ~ 36 px)."""

    def __init__(self, label, x, y, w, h, action, color=None, icon=None, scale=0.8, sub=None, radius=10):
        self.label, self.x, self.y, self.w, self.h = label, x, y, w, h
        self.action, self.color, self.icon, self.scale, self.sub, self.radius = action, color, icon, scale, sub, radius
        self.selected = False

    def contains(self, px, py):
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h

    def draw(self, img, pointer):
        hover = pointer is not None and self.contains(*pointer)
        x, y, w, h, r = int(self.x), int(self.y) - (3 if hover else 0), int(self.w), int(self.h), self.radius
        draw_shadow(img, x, y, w, h, r, off=9 if hover else 5)
        base = self.color or C.PANEL
        if hover:
            base = shade(base, 1.3) if self.color else C.HOVER
        fill_rounded_grad(img, x, y, w, h, r, shade(base, 1.25), shade(base, 0.75))   # velours
        lit = hover or self.selected
        draw_rounded_border(img, x, y, w, h, r, C.GOLD_LIGHT if lit else C.GOLD, 5 if self.selected else (4 if hover else 3))
        if h >= 60 and w > 20:                                                        # filet interieur fin
            draw_rounded_border(img, x + 7, y + 7, w - 14, h - 14, max(r - 5, 2), C.GOLD_DARK, 1)
        if h >= 100:                                                                  # losanges de coin
            for dx, dy in ((14, 14), (w - 14, 14), (14, h - 14), (w - 14, h - 14)):
                diamond(img, x + dx, y + dy, 5, C.GOLD)
        cx, cy = x + w // 2, y + h // 2
        horizontal = w >= h * 2.5
        ic = C.GOLD_LIGHT
        if self.icon and self.label and horizontal:
            self.icon(img, x + h * 0.55, cy, h / 95.0, ic)
            ty = cy - (self.scale * 11 if self.sub else 0)
            put_text(img, self.label, x + h * 1.05, ty, self.scale, C.TEXT, 2, vmid=True, shadow=True)
            if self.sub:
                put_text(img, self.sub, x + h * 1.05, cy + self.scale * 26, 0.6, C.GRAY, 1, vmid=True, font=FONT_SUB)
        elif self.icon and self.label:
            self.icon(img, cx, y + h * 0.38, h / 100.0, ic)
            put_text(img, self.label, cx, y + h - 14, 0.45, C.TEXT, 1, center=True)
        elif self.icon:
            self.icon(img, cx, cy, h / 80.0, ic)
        elif self.label:
            put_text(img, self.label, cx, cy, self.scale, C.TEXT, 2, center=True, shadow=True)