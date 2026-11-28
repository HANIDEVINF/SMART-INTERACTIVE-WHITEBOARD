# ============================================================
# board_detection.py : detection des bordures du tableau blanc
# Etapes : gris -> flou -> Canny -> contours -> rectangle (4 coins)
# ============================================================
import cv2
import numpy as np


def ordonner_points(pts):
    """Ordre : haut-gauche, haut-droit, bas-droit, bas-gauche."""
    pts = pts.reshape(4, 2)
    res = np.zeros((4, 2), dtype="int")
    somme = pts.sum(axis=1)            # x + y
    diff = np.diff(pts, axis=1)        # y - x
    res[0] = pts[np.argmin(somme)]     # haut-gauche
    res[2] = pts[np.argmax(somme)]     # bas-droit
    res[1] = pts[np.argmin(diff)]      # haut-droit
    res[3] = pts[np.argmax(diff)]      # bas-gauche
    return res


def detecter_tableau(frame):
    """Retourne les 4 coins du tableau, ou None."""
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    flou = cv2.GaussianBlur(gris, (5, 5), 0)        # reduire le bruit
    bords = cv2.Canny(flou, 50, 150)                 # trouver les bords
    bords = cv2.dilate(bords, np.ones((3, 3), np.uint8))

    contours, _ = cv2.findContours(bords, cv2.RETR_LIST,
                                   cv2.CHAIN_APPROX_SIMPLE)
    meilleur = None
    aire_max = 0
    for c in contours:
        aire = cv2.contourArea(c)
        if aire > 10000 and aire > aire_max:
            perimetre = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * perimetre, True)
            if len(approx) == 4:                     # 4 coins = rectangle
                meilleur = approx
                aire_max = aire
    if meilleur is None:
        return None
    return ordonner_points(meilleur)


def lisser(anciens, nouveaux, alpha=0.7):
    """Stabilise les coins : moyenne entre l'ancienne et la nouvelle position."""
    if anciens is None:
        return nouveaux
    if np.abs(anciens - nouveaux).max() > 40:        # gros changement
        return nouveaux
    return (alpha * anciens + (1 - alpha) * nouveaux).astype(int)


def dessiner_tableau(frame, coins, couleur=(150, 210, 140)):
    cv2.polylines(frame, [coins.reshape(-1, 1, 2)], True, couleur, 3)
    for (x, y) in coins:
        cv2.circle(frame, (int(x), int(y)), 9, (255, 255, 255), -1)
        cv2.circle(frame, (int(x), int(y)), 9, (190, 130, 240), 3)
