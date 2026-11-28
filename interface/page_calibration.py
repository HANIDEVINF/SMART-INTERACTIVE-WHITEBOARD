# ============================================================
# page_calibration.py : calibrage du tableau + suivi de la main
#  - detecte les 4 coins du tableau
#  - "Validate" memorise le calibrage (image -> tableau)
#  - montre ou se trouve le doigt sur le tableau
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea
from interface.widgets import (Panneau, Puce, VideoLabel, MiniTableau, entete,
                               etiquette, bouton)


class PageCalibration(QWidget):
    parent_page = "reglages"
    besoin_cadre = True            # la boucle principale cherche aussi le tableau

    def __init__(self, app):
        super().__init__()
        self.app = app

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        lay.addWidget(entete(app, "Calibration", retour="reglages"))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        self.video = VideoLabel("Camera offline")
        corps.addWidget(self.video, 1)

        # ----- colonne de droite -----
        defil = QScrollArea()
        defil.setWidgetResizable(True)
        defil.setFixedWidth(350)
        defil.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        droite = QWidget()
        dl = QVBoxLayout(droite)
        dl.setContentsMargins(0, 0, 8, 0)
        dl.setSpacing(14)
        defil.setWidget(droite)
        corps.addWidget(defil)

        p1 = Panneau()
        p1.lay.addWidget(etiquette("Board", "h2"))
        self.puce_tableau = Puce("Board not found", "off")
        p1.lay.addWidget(self.puce_tableau)
        self.texte_coins = etiquette("No corner", "code")
        self.texte_coins.setMinimumHeight(64)
        p1.lay.addWidget(self.texte_coins)
        self.puce_cal = Puce("Not calibrated", "off")
        p1.lay.addWidget(self.puce_cal)
        p1.lay.addWidget(bouton("Validate", "or", self.valider, ico="check"))
        p1.lay.addWidget(bouton("Reset", "sombre", self.reset, ico="rotate-ccw"))
        dl.addWidget(p1)

        p2 = Panneau()
        p2.lay.addWidget(etiquette("Pointer", "h2"))
        self.puce_main = Puce("No hand", "off")
        p2.lay.addWidget(self.puce_main)
        self.mini = MiniTableau()
        self.mini.setMinimumHeight(130)
        p2.lay.addWidget(self.mini)
        self.texte_pos = etiquette("Not calibrated", "code")
        p2.lay.addWidget(self.texte_pos)
        self.btn_miroir = bouton("Mirror", "sombre", self.miroir, checkable=True,
                                 ico="arrow-left-right")
        p2.lay.addWidget(self.btn_miroir)
        dl.addWidget(p2)
        dl.addStretch()

    # ---------------- boutons ----------------
    def valider(self):
        if self.app.suiveur.valider():
            self.puce_cal.definir("Calibration saved", "ok")
        else:
            self.puce_cal.definir("No board detected", "warn")

    def reset(self):
        self.app.suiveur.reinitialiser()
        self.puce_cal.definir("Not calibrated", "off")

    def miroir(self):
        self.app.suiveur.miroir = self.btn_miroir.isChecked()

    # ---------------- appelee par la boucle principale ----------------
    def maj(self):
        s = self.app.suiveur
        self.video.afficher_frame(s.image)

        if s.tableau_detecte:
            self.puce_tableau.definir("Board detected", "ok")
            noms = ["TL", "TR", "BR", "BL"]
            c = ["%s (%d,%d)" % (noms[i], x, y) for i, (x, y) in enumerate(s.coins)]
            self.texte_coins.setText("%s   %s\n%s   %s" % (c[0], c[1], c[3], c[2]))
        else:
            self.puce_tableau.definir("Board not found", "off")
            self.texte_coins.setText("No corner")

        if s.est_calibre():
            self.puce_cal.definir("Calibration saved", "ok")
        elif self.puce_cal.text() != "No board detected":
            self.puce_cal.definir("Not calibrated", "off")

        if s.main_detectee:
            self.puce_main.definir("Hand detected", "ok")
        else:
            self.puce_main.definir("No hand", "off")
        if s.pointeur_tableau is not None:
            x, y = s.pointeur_tableau
            self.mini.definir((x, y))
            self.texte_pos.setText("X = %d     Y = %d" % (x, y))
        else:
            self.mini.definir(None)
            self.texte_pos.setText("Not calibrated" if not s.est_calibre() else "-")
