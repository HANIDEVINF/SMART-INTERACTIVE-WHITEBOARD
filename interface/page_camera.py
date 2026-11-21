# ============================================================
# page_camera.py : page Calibration ET page Pointeur
# (meme code, le parametre "mode" change le comportement)
# ============================================================
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from camera import preparer
from board_detection import detecter_tableau, lisser, dessiner_tableau
from hand_detection import detecter_main, dessiner_main
from calibration import creer_transformation, image_vers_tableau
from interface.widgets import (Carte, Puce, VideoLabel, MiniTableau, entete,
                               etiquette, bouton)


class PageCamera(QWidget):
    def __init__(self, app, mode):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app
        self.mode = mode
        self.coins = None          # coins detectes (lisses)
        self.rates = 0             # nombre d'images sans tableau
        self.pt_lisse = None       # pointeur lisse

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(22)

        if mode == "calibration":
            titre, sous = "Calibration", "Détecte les 4 coins du tableau puis valide."
        else:
            titre, sous = "Suivi du pointeur", "Montre le tableau avec ta main : le bout du doigt est suivi."
        self.puce_cam = Puce("●  Caméra non connectée", "off")
        lay.addWidget(entete(titre, sous, self.puce_cam))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ----- video -----
        carte_video = Carte(avec_ombre=False)
        carte_video.lay.setContentsMargins(14, 14, 14, 14)
        self.video = VideoLabel("Caméra non connectée\n\n"
                                "Ouvre « Caméra du téléphone » pour la connecter")
        carte_video.lay.addWidget(self.video)
        corps.addWidget(carte_video, 1)

        # ----- panneau de droite -----
        droite = QWidget()
        droite.setFixedWidth(330)
        dl = QVBoxLayout(droite)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(18)
        corps.addWidget(droite)

        carte_det = Carte()
        carte_det.lay.addWidget(etiquette("Détection", "h2"))
        self.puce_tableau = Puce("Tableau : non détecté", "off")
        carte_det.lay.addWidget(self.puce_tableau)
        if mode == "pointeur":
            self.puce_main = Puce("Main : non détectée", "off")
            carte_det.lay.addWidget(self.puce_main)
        dl.addWidget(carte_det)

        if mode == "calibration":
            carte_cal = Carte()
            carte_cal.lay.addWidget(etiquette("Calibrage", "h2"))
            self.texte_coins = etiquette("Aucun coin détecté", "code")
            carte_cal.lay.addWidget(self.texte_coins)
            self.puce_cal = Puce("Non calibré", "off")
            carte_cal.lay.addWidget(self.puce_cal)
            carte_cal.lay.addWidget(bouton("✔   Valider le calibrage",
                                           "primaire", self.valider))
            carte_cal.lay.addWidget(bouton("Réinitialiser", "blanc", self.reset))
            dl.addWidget(carte_cal)
        else:
            carte_pos = Carte()
            carte_pos.lay.addWidget(etiquette("Position sur le tableau", "h2"))
            self.mini = MiniTableau()
            carte_pos.lay.addWidget(self.mini)
            self.texte_pos = etiquette("Calibre d'abord le tableau", "code")
            carte_pos.lay.addWidget(self.texte_pos)
            dl.addWidget(carte_pos)

        dl.addWidget(bouton("📱   Réglages de la caméra", "blue",
                            lambda: app.afficher("connexion")))
        dl.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.boucle)

    # ---------------- boutons ----------------
    def valider(self):
        if self.coins is None:
            self.puce_cal.definir("Aucun tableau détecté", "warn")
            return
        self.app.coins_valides = self.coins.copy()
        self.app.M = creer_transformation(self.coins)
        self.puce_cal.definir("✔ Calibrage validé", "ok")

    def reset(self):
        self.app.coins_valides = None
        self.app.M = None
        self.puce_cal.definir("Non calibré", "off")

    # ---------------- boucle ----------------
    def showEvent(self, event):
        if self.mode == "calibration":
            if self.app.M is not None:
                self.puce_cal.definir("✔ Calibrage validé", "ok")
            else:
                self.puce_cal.definir("Non calibré", "off")
        self.timer.start(30)

    def hideEvent(self, event):
        self.timer.stop()

    def boucle(self):
        cam = self.app.camera
        if cam.etat == "connectee":
            self.puce_cam.definir("●  Caméra connectée", "ok")
        elif cam.etat == "connexion":
            self.puce_cam.definir("●  Connexion en cours...", "warn")
        else:
            self.puce_cam.definir("●  Caméra non connectée", "off")

        frame = cam.lire()
        if frame is None:
            self.video.afficher_frame(None)
            return
        frame = preparer(frame)

        # 1) tableau
        nouveaux = detecter_tableau(frame)
        if nouveaux is not None:
            self.coins = lisser(self.coins, nouveaux)
            self.rates = 0
            self.puce_tableau.definir("Tableau : détecté ✔", "ok")
        else:
            self.rates += 1
            if self.rates > 15:
                self.coins = None
                self.puce_tableau.definir("Tableau : non détecté", "off")

        a_dessiner = self.coins
        couleur = (150, 210, 140)
        if self.mode == "pointeur" and self.app.coins_valides is not None:
            a_dessiner = self.app.coins_valides      # on garde le calibrage
            couleur = (240, 190, 130)
        if a_dessiner is not None:
            dessiner_tableau(frame, a_dessiner, couleur)

        if self.mode == "calibration":
            if self.coins is not None:
                noms = ["HG", "HD", "BD", "BG"]
                lignes = ["%s  (%d, %d)" % (noms[i], x, y)
                          for i, (x, y) in enumerate(self.coins)]
                self.texte_coins.setText("\n".join(lignes))
            else:
                self.texte_coins.setText("Aucun coin détecté")
        else:
            self.suivre_main(frame)

        self.video.afficher_frame(frame)

    def suivre_main(self, frame):
        pointeur, contour = detecter_main(frame)
        if pointeur is None:
            self.puce_main.definir("Main : non détectée", "off")
            self.pt_lisse = None
            self.mini.definir(None)
            return
        # lissage simple du pointeur (moins de tremblement)
        if self.pt_lisse is None:
            self.pt_lisse = pointeur
        else:
            self.pt_lisse = (int(0.6 * self.pt_lisse[0] + 0.4 * pointeur[0]),
                             int(0.6 * self.pt_lisse[1] + 0.4 * pointeur[1]))
        dessiner_main(frame, self.pt_lisse, contour)
        self.puce_main.definir("Main : détectée ✔", "ok")
        self.app.pointeur = self.pt_lisse

        if self.app.M is not None:
            x, y = image_vers_tableau(self.app.M, self.pt_lisse)
            self.mini.definir((x, y))
            self.texte_pos.setText("X = %d     Y = %d" % (x, y))
        else:
            self.mini.definir(None)
            self.texte_pos.setText("Calibre d'abord le tableau")
