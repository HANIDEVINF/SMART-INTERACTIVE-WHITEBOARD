"""detection.py - Detection du marqueur colore (segmentation HSV, tout en NumPy).

Chaine : image BGR -> HSV -> seuillage -> ouverture morphologique -> centroide robuste
         -> lissage temporel.
Limites : sensible aux objets de meme couleur et a l'eclairage ; l'UI projetee evite le vert.
"""
import json
import os
import numpy as np
import config as C


def bgr_to_hsv(img):
    """BGR uint8 -> HSV float (H en degres [0,360), S et V dans [0,1])."""
    f = img.astype(np.float32) / 255.0
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    d = mx - mn
    safe = np.where(d > 1e-6, d, 1.0)
    h = np.select([mx == r, mx == g],
                  [((g - b) / safe) % 6, (b - r) / safe + 2],
                  default=(r - g) / safe + 4)
    h = np.where(d > 1e-6, h * 60.0, 0.0)
    s = np.where(mx > 1e-6, d / np.where(mx > 1e-6, mx, 1.0), 0.0)
    return np.stack([h, s, mx], axis=-1)


def erode3(mask):
    """Erosion 3x3 : un pixel reste a 1 si ses 8 voisins sont a 1."""
    h, w = mask.shape
    p = np.pad(mask, 1)
    out = mask.copy()
    for dy in range(3):
        for dx in range(3):
            out &= p[dy:dy + h, dx:dx + w]
    return out


def dilate3(mask):
    """Dilatation 3x3 : un pixel passe a 1 si un de ses voisins est a 1."""
    h, w = mask.shape
    p = np.pad(mask, 1)
    out = mask.copy()
    for dy in range(3):
        for dx in range(3):
            out |= p[dy:dy + h, dx:dx + w]
    return out


def load_params():
    if os.path.exists(C.MARKER_FILE):
        with open(C.MARKER_FILE) as f:
            return json.load(f)
    return dict(C.DEFAULT_MARKER)


def save_params(p):
    with open(C.MARKER_FILE, "w") as f:
        json.dump(p, f, indent=2)


class MarkerDetector:
    def __init__(self, params=None):
        self.pos = None
        self.lost = 0
        self.set_params(params or load_params())

    def set_params(self, p):
        self.hue, self.hue_tol = float(p["hue"]), float(p["hue_tol"])
        self.s_min, self.v_min = float(p["s_min"]), float(p["v_min"])
        self.pos, self.lost = None, 0

    def segment(self, frame):
        """Retourne le masque booleen (image reduite par DETECT_STRIDE)."""
        small = frame[::C.DETECT_STRIDE, ::C.DETECT_STRIDE]
        hsv = bgr_to_hsv(small)
        dh = np.abs(hsv[..., 0] - self.hue)
        dh = np.minimum(dh, 360.0 - dh)                    # distance circulaire sur la teinte
        mask = (dh <= self.hue_tol) & (hsv[..., 1] >= self.s_min) & (hsv[..., 2] >= self.v_min)
        return dilate3(erode3(mask))                        # ouverture : supprime le bruit

    @staticmethod
    def locate(mask):
        """Centroide robuste : mediane -> on garde les pixels proches -> moyenne."""
        ys, xs = np.nonzero(mask)
        if len(xs) < C.MIN_AREA:
            return None
        mx, my = np.median(xs), np.median(ys)
        keep = (xs - mx) ** 2 + (ys - my) ** 2 <= C.ROBUST_RADIUS ** 2
        if keep.sum() < C.MIN_AREA:
            return None
        return xs[keep].mean() * C.DETECT_STRIDE, ys[keep].mean() * C.DETECT_STRIDE

    def detect(self, frame):
        """Retourne (position image lissee ou None, masque)."""
        mask = self.segment(frame)
        res = self.locate(mask)
        if res is None:
            self.lost += 1
            if self.lost > C.LOST_FRAMES:
                self.pos = None
            return (tuple(self.pos) if self.pos is not None else None), mask
        self.lost = 0
        p = np.array(res, float)
        if self.pos is None:
            self.pos = p
        else:
            dist = np.linalg.norm(p - self.pos)
            alpha = min(1.0, C.SMOOTH_ALPHA + dist / 100.0)  # grand saut -> moins de lissage
            self.pos = (1 - alpha) * self.pos + alpha * p
        return tuple(self.pos), mask