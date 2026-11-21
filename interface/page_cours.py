# ============================================================
# page_cours.py : petite lecon (diapositives precedent / suivant)
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from interface.widgets import Carte, Puce, entete, etiquette, bouton

DIAPOS = [
    ("Introduction",
     "La vision par ordinateur permet à une machine de comprendre le "
     "contenu d'une image : trouver un objet, une couleur, un contour."),
    ("La couleur en HSV",
     "Dans l'espace HSV, la teinte (H) est séparée de la luminosité (V). "
     "C'est idéal pour détecter la peau de la main avec un seuillage."),
    ("Les contours du tableau",
     "Le filtre de Canny trouve les bords. Un tableau blanc est le plus "
     "grand contour à 4 coins de l'image."),
    ("Interaction",
     "La position du doigt est convertie en coordonnées du tableau. Les "
     "deux boutons de la télécommande déclenchent les clics."),
]


class PageCours(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app
        self.i = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(22)
        self.puce = Puce("", "info")
        lay.addWidget(entete("Cours", "Une petite leçon pour la démonstration.", self.puce))

        carte = Carte()
        carte.lay.setContentsMargins(60, 50, 60, 50)
        carte.lay.setSpacing(18)
        self.titre = etiquette("", "hero_titre")
        self.texte = etiquette("", "hero_texte", wrap=True)
        self.texte.setStyleSheet("font-size: 20px; color: #5E5578;")
        self.points = etiquette("", "muted")
        carte.lay.addStretch()
        carte.lay.addWidget(self.titre)
        carte.lay.addWidget(self.texte)
        carte.lay.addStretch()
        carte.lay.addWidget(self.points)
        lay.addWidget(carte, 1)

        nav = QHBoxLayout()
        nav.setSpacing(12)
        nav.addStretch()
        nav.addWidget(bouton("←   Précédent", "lavender", self.precedent))
        nav.addWidget(bouton("Suivant   →", "primaire", self.suivant))
        lay.addLayout(nav)
        self.maj()

    def maj(self):
        titre, texte = DIAPOS[self.i]
        self.titre.setText(titre)
        self.texte.setText(texte)
        self.puce.definir("Page %d / %d" % (self.i + 1, len(DIAPOS)), "info")
        self.points.setText("   ".join("●" if k == self.i else "○"
                                       for k in range(len(DIAPOS))))

    def suivant(self):
        self.i = min(self.i + 1, len(DIAPOS) - 1)
        self.maj()

    def precedent(self):
        self.i = max(self.i - 1, 0)
        self.maj()
