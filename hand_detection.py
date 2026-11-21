# ============================================================
# hand_detection.py : detection de la main (couleur de la peau)
# Etapes : HSV -> seuillage -> erosion/dilatation -> plus grand contour
# ============================================================
import cv2
import numpy as np


def detecter_main(frame):
    """Retourne (pointeur, contour) ou (None, None)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    bas = np.array([0, 30, 60])
    haut = np.array([20, 150, 255])
    masque = cv2.inRange(hsv, bas, haut)             # pixels couleur peau

    noyau = np.ones((5, 5), np.uint8)
    masque = cv2.erode(masque, noyau)                # enlever le bruit
    masque = cv2.dilate(masque, noyau, iterations=2)

    contours, _ = cv2.findContours(masque, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) == 0:
        return None, None

    c = max(contours, key=cv2.contourArea)           # plus grande zone
    if cv2.contourArea(c) < 3000:
        return None, None

    # Pointeur = point le plus haut de la main (bout du doigt)
    pointeur = tuple(int(v) for v in c[c[:, :, 1].argmin()][0])
    return pointeur, c


def dessiner_main(frame, pointeur, contour):
    cv2.drawContours(frame, [contour], -1, (200, 150, 255), 2)
    cv2.circle(frame, pointeur, 13, (255, 255, 255), -1)
    cv2.circle(frame, pointeur, 13, (150, 120, 255), 4)
