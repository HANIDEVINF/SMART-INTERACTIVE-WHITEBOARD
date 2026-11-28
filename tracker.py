# ============================================================
# tracker.py : suivi du pointeur (main) + tableau + calibrage
# Sans interface graphique : on lui donne une image de la camera,
# il retourne la position du doigt sur le tableau (entre 0 et 1).
# ============================================================
from camera import preparer
from board_detection import detecter_tableau, lisser, dessiner_tableau
from hand_detection import detecter_main, dessiner_main
from calibration import creer_transformation, image_vers_tableau
import config


class Suiveur:
    def __init__(self):
        self.coins_valides = None     # coins du tableau apres calibrage
        self.M = None                 # matrice image -> tableau
        self.miroir = False           # inverse gauche/droite (sans calibrage)

        self.coins = None             # coins detectes (lisses)
        self.rates = 0                # images sans tableau
        self.pt_lisse = None          # doigt lisse (en pixels image)

        self.tableau_detecte = False
        self.main_detectee = False
        self.pointeur_norm = None     # (x, y) entre 0 et 1, ou None
        self.pointeur_tableau = None  # (x, y) en unites du tableau (si calibre)
        self.image = None             # derniere image annotee (BGR)

    # ---------------- calibrage ----------------
    def valider(self):
        """Valide le calibrage avec les coins actuellement detectes."""
        if self.coins is None:
            return False
        self.coins_valides = self.coins.copy()
        self.M = creer_transformation(self.coins)
        return True

    def reinitialiser(self):
        self.coins_valides = None
        self.M = None

    def est_calibre(self):
        return self.M is not None

    # ---------------- analyse d'une image ----------------
    def vider(self):
        """Appelee quand il n'y a pas d'image."""
        self.image = None
        self.main_detectee = False
        self.tableau_detecte = False
        self.pointeur_norm = None
        self.pointeur_tableau = None
        self.pt_lisse = None

    def traiter(self, frame, chercher_tableau=False):
        frame = preparer(frame)
        h, w = frame.shape[:2]

        # 1) tableau (seulement quand on calibre : c'est plus lourd)
        if chercher_tableau:
            nouveaux = detecter_tableau(frame)
            if nouveaux is not None:
                self.coins = lisser(self.coins, nouveaux)
                self.rates = 0
                self.tableau_detecte = True
            else:
                self.rates += 1
                if self.rates > 15:
                    self.coins = None
                    self.tableau_detecte = False
            if self.coins is not None:
                dessiner_tableau(frame, self.coins, (150, 210, 140))
        elif self.coins_valides is not None:
            dessiner_tableau(frame, self.coins_valides, (240, 190, 130))

        # 2) main
        pointeur, contour = detecter_main(frame)
        self.pointeur_norm = None
        self.pointeur_tableau = None
        if pointeur is None:
            self.main_detectee = False
            self.pt_lisse = None
        else:
            self.main_detectee = True
            if self.pt_lisse is None:                 # lissage : moins de tremblements
                self.pt_lisse = pointeur
            else:
                self.pt_lisse = (int(0.5 * self.pt_lisse[0] + 0.5 * pointeur[0]),
                                 int(0.5 * self.pt_lisse[1] + 0.5 * pointeur[1]))
            dessiner_main(frame, self.pt_lisse, contour)
            self.pointeur_norm = self.vers_normalise(self.pt_lisse, w, h)

        self.image = frame

    def vers_normalise(self, pt, w, h):
        """Position du doigt (pixels) -> position entre 0 et 1 sur le tableau."""
        if self.M is not None:                        # avec calibrage
            x, y = image_vers_tableau(self.M, pt)
            self.pointeur_tableau = (x, y)
            nx, ny = x / config.TAB_L, y / config.TAB_H
            if nx < -0.03 or nx > 1.03 or ny < -0.03 or ny > 1.03:
                return None                           # doigt hors du tableau
        else:                                         # sans calibrage : toute l'image
            nx, ny = pt[0] / w, pt[1] / h
            if self.miroir:
                nx = 1 - nx
        return (min(max(nx, 0.0), 1.0), min(max(ny, 0.0), 1.0))
