"""mapping.py - Geometrie : homographie image -> tableau (implementee avec NumPy)."""
import numpy as np
import config as C


def compute_homography(src, dst):
    """Estime H (3x3) telle que dst ~ H * src, par DLT + SVD.
    src, dst : N>=4 points (x,y). Chaque paire donne 2 equations lineaires en les 9
    coefficients de H ; la solution est le dernier vecteur singulier de A."""
    src = np.asarray(src, float)
    dst = np.asarray(dst, float)
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, Vt = np.linalg.svd(np.array(A))
    H = Vt[-1].reshape(3, 3)
    return H / H[2, 2]


def apply_homography(H, pts):
    """Applique H a des points (N,2) -> (N,2) (division par la coordonnee homogene w)."""
    pts = np.atleast_2d(np.asarray(pts, float))
    p = np.hstack([pts, np.ones((len(pts), 1))]) @ H.T
    return p[:, :2] / p[:, 2:3]


def reprojection_error(H, src, dst):
    """Erreur moyenne (pixels cible) entre H*src et dst."""
    diff = apply_homography(H, src) - np.asarray(dst, float)
    return float(np.mean(np.hypot(diff[:, 0], diff[:, 1])))


def is_convex_quad(pts):
    """Vrai si le quadrilatere (4 points ordonnes) est convexe (ordre de clic valide)."""
    p = np.asarray(pts, float)
    signs = []
    for i in range(4):
        a, b, c = p[i], p[(i + 1) % 4], p[(i + 2) % 4]
        signs.append(np.sign((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])))
    return all(s > 0 for s in signs) or all(s < 0 for s in signs)


class BoardMapper:
    """Convertit image camera <-> coordonnees tableau (origine = coin haut-gauche, Y vers le bas)."""

    def __init__(self, H):
        self.H = np.asarray(H, float)
        self.Hinv = np.linalg.inv(self.H)

    def to_board(self, p):
        x, y = apply_homography(self.H, p)[0]
        return float(x), float(y)

    def to_image(self, p):
        x, y = apply_homography(self.Hinv, p)[0]
        return float(x), float(y)

    @staticmethod
    def inside(x, y, margin=0):
        return -margin <= x <= C.UI_W + margin and -margin <= y <= C.UI_H + margin