# ============================================================
# page_accueil.py : Home = banniere + 8 cartes d'options
# ============================================================
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QScrollArea)
from interface.widgets import (Hero, CarteAccueil, Puce, etiquette, bouton)

# (page, icone, titre, description, couleur)
OPTIONS = [
    ("calibration", "📐", "Calibration", "Repérer les 4 coins du tableau blanc", "mint"),
    ("pointeur", "👆", "Pointeur", "Suivre la main en direct", "pink"),
    ("telecommande", "🎮", "Télécommande", "Boutons précédent / suivant", "blue"),
    ("menus", "🧭", "Menus", "Menu principal et sous-menus", "lavender"),
    ("dessin", "🎨", "Dessin libre", "Stylos, couleurs et épaisseurs", "yellow"),
    ("image", "🖼️", "Image & Zoom", "Afficher une image et zoomer", "peach"),
    ("cours", "📚", "Cours", "Séquence pédagogique", "mint"),
    ("parametres", "⚙️", "Paramètres", "Réglages et réinitialisation", "blue"),
]


class PageAccueil(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app

        externe = QVBoxLayout(self)
        externe.setContentsMargins(0, 0, 0, 0)
        defil = QScrollArea()
        defil.setWidgetResizable(True)
        externe.addWidget(defil)
        contenu = QWidget()
        defil.setWidget(contenu)
        lay = QVBoxLayout(contenu)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(26)

        # ----- banniere -----
        hero = Hero()
        hero.setFixedHeight(240)
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(40, 30, 40, 30)
        hl.setSpacing(6)
        self.puce = Puce("●  Caméra non connectée", "off")
        hl.addWidget(self.puce)
        hl.addSpacing(6)
        hl.addWidget(etiquette("Tableau Blanc Interactif", "hero_titre"))
        hl.addWidget(etiquette(
            "Pilote un tableau projeté avec ta main et une télécommande,\n"
            "grâce à la vision par ordinateur.", "hero_texte"))
        hl.addSpacing(14)
        boutons = QHBoxLayout()
        boutons.setSpacing(12)
        boutons.addWidget(bouton("📱   Connecter la caméra", "primaire",
                                 lambda: app.afficher("connexion")))
        boutons.addWidget(bouton("📐   Calibrer le tableau", "blanc",
                                 lambda: app.afficher("calibration")))
        boutons.addStretch()
        hl.addLayout(boutons)
        lay.addWidget(hero)

        # ----- cartes -----
        lay.addWidget(etiquette("Que veux-tu faire ?", "h2"))
        grille = QGridLayout()
        grille.setSpacing(20)
        for i, (page, icone, titre, desc, ton) in enumerate(OPTIONS):
            carte = CarteAccueil(icone, titre, desc, ton)
            carte.clique.connect(lambda p=page: app.afficher(p))
            grille.addWidget(carte, i // 4, i % 4)
        for c in range(4):
            grille.setColumnStretch(c, 1)
        lay.addLayout(grille)
        lay.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.maj)

    def maj(self):
        etat = self.app.camera.etat
        if etat == "connectee":
            self.puce.definir("●  Caméra connectée", "ok")
        elif etat == "connexion":
            self.puce.definir("●  Connexion en cours...", "warn")
        else:
            self.puce.definir("●  Caméra non connectée", "off")

    def showEvent(self, event):
        self.maj()
        self.timer.start(400)

    def hideEvent(self, event):
        self.timer.stop()
