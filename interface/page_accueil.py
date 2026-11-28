# ============================================================
# page_accueil.py : menu principal (4 grandes tuiles)
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from interface.widgets import TitreOrne, BoutonTuile, PuceCamera


class PageAccueil(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        haut = QHBoxLayout()
        haut.addStretch()
        haut.addWidget(PuceCamera(app))
        lay.addLayout(haut)
        lay.addWidget(TitreOrne())

        # (titre, sous-titre, icone, couleur, page)
        tuiles = [
            ("Draw", "Free drawing", "pencil", "rouge", "dessin"),
            ("Images", "Display and zoom", "image", "violet", "images"),
            ("Lesson", "Guided slides", "book-open", "bleu", "cours"),
            ("Settings", "Calibration and reset", "settings", "orange", "reglages"),
        ]
        grille = QGridLayout()
        grille.setHorizontalSpacing(26)
        grille.setVerticalSpacing(22)
        for i, (titre, sous, ico, couleur, page) in enumerate(tuiles):
            t = BoutonTuile(titre, sous, ico, couleur)
            t.clique.connect(lambda p=page: app.afficher(p))
            grille.addWidget(t, i // 2, i % 2)

        centre = QHBoxLayout()
        centre.addStretch(1)
        cadre = QWidget()
        cadre.setLayout(grille)
        cadre.setMaximumWidth(960)
        centre.addWidget(cadre, 6)
        centre.addStretch(1)
        lay.addLayout(centre, 1)
        lay.addSpacing(10)
