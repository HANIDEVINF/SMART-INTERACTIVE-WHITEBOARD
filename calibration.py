# ============================================================
# calibration.py : passage des coordonnees image -> tableau
# ============================================================
import cv2
import numpy as np
import config


def creer_transformation(coins):
    """Matrice qui transforme les 4 coins de l'image en rectangle du tableau."""
    source = np.float32(coins)
    destination = np.float32([[0, 0],
                              [config.TAB_L, 0],
                              [config.TAB_L, config.TAB_H],
                              [0, config.TAB_H]])
    return cv2.getPerspectiveTransform(source, destination)


def image_vers_tableau(M, point):
    """Convertit un point (x, y) de l'image en point du tableau."""
    p = np.float32([[point]])
    r = cv2.perspectiveTransform(p, M)
    return float(r[0][0][0]), float(r[0][0][1])
