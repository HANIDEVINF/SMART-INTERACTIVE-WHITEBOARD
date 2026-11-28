# ============================================================
# page_cours.py : Lesson = diapositives guidees (Previous / Next)
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from interface.widgets import Panneau, Puce, entete, etiquette, bouton

DIAPOS = [
    ("Computer vision",
     "A machine understands an image: it finds a color, a shape, a contour."),
    ("Hand detection",
     "In HSV, skin tones are separated from brightness. A threshold keeps the "
     "hand, and the highest point of the hand is the fingertip."),
    ("Board detection",
     "Canny finds the edges. The whiteboard is the largest contour with "
     "4 corners."),
    ("Interaction",
     "The fingertip is mapped onto the board. The two remote buttons "
     "trigger the left and right clicks."),
]


class PageCours(QWidget):
    parent_page = "accueil"

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.i = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        self.puce = Puce("", "info")
        lay.addWidget(entete(app, "Lesson", droite=self.puce))

        carte = Panneau((70, 40, 70, 40))
        carte.lay.setSpacing(18)
        self.titre = etiquette("", "gros")
        self.texte = etiquette("", None, wrap=True)
        self.texte.setStyleSheet("font-size: 24px;")
        carte.lay.addStretch()
        carte.lay.addWidget(self.titre)
        carte.lay.addWidget(self.texte)
        carte.lay.addStretch()
        lay.addWidget(carte, 1)

        nav = QHBoxLayout()
        nav.setSpacing(14)
        nav.addStretch()
        nav.addWidget(bouton("Previous", "sombre", self.precedent, ico="arrow-left"))
        self.btn_suivant = bouton("Next", "or", self.suivant, ico="arrow-right")
        self.btn_suivant.setLayoutDirection(Qt.RightToLeft)   # icone a droite
        nav.addWidget(self.btn_suivant)
        nav.addStretch()
        lay.addLayout(nav)
        self.maj_page()

    def maj_page(self):
        titre, texte = DIAPOS[self.i]
        self.titre.setText(titre)
        self.texte.setText(texte)
        self.puce.definir("%d / %d" % (self.i + 1, len(DIAPOS)), "info")

    def suivant(self):
        self.i = min(self.i + 1, len(DIAPOS) - 1)
        self.maj_page()

    def precedent(self):
        self.i = max(self.i - 1, 0)
        self.maj_page()

    def clic_droit(self):
        """Clic droit (Previous) : diapo precedente, puis retour au menu."""
        if self.i > 0:
            self.precedent()
        else:
            self.app.retour()
