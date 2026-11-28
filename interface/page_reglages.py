# ============================================================
# page_reglages.py : Settings = sous-menu (camera, calibration, remote, reset)
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from interface.widgets import BoutonTuile, entete, etiquette


class PageReglages(QWidget):
    parent_page = "accueil"

    def __init__(self, app):
        super().__init__()
        self.app = app
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(entete(app, "Settings"))

        # (titre, sous-titre, icone, couleur, action)
        tuiles = [
            ("Camera", "Connect the phone", "smartphone", "bleu",
             lambda: app.afficher("camera")),
            ("Calibration", "Detect the board", "scan", "violet",
             lambda: app.afficher("calibration")),
            ("Remote", "Learn the buttons", "keyboard", "orange",
             lambda: app.afficher("telecommande")),
            ("Reset", "Clear calibration", "rotate-ccw", "rouge", self.reinitialiser),
        ]
        grille = QGridLayout()
        grille.setHorizontalSpacing(26)
        grille.setVerticalSpacing(22)
        for i, (titre, sous, ico, couleur, action) in enumerate(tuiles):
            t = BoutonTuile(titre, sous, ico, couleur)
            t.clique.connect(action)
            grille.addWidget(t, i // 2, i % 2)

        centre = QHBoxLayout()
        centre.addStretch(1)
        cadre = QWidget()
        cadre.setLayout(grille)
        cadre.setMaximumWidth(960)
        centre.addWidget(cadre, 6)
        centre.addStretch(1)
        lay.addLayout(centre, 1)

        self.message = etiquette("", "h2", align=Qt.AlignHCenter)
        lay.addWidget(self.message)

    def reinitialiser(self):
        self.app.suiveur.reinitialiser()
        self.message.setText("Calibration cleared")
