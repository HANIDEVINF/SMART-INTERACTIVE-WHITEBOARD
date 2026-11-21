# ============================================================
# page_menus.py : menu principal + sous-menus
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QButtonGroup
from interface.widgets import Carte, entete, etiquette, bouton

# categorie -> (icone, ton, [(texte, page)])
MENUS = {
    "Outils": ("🛠️", "yellow", [("🎨  Dessin libre", "dessin"),
                                ("🖼️  Image & Zoom", "image")]),
    "Cours": ("📚", "mint", [("📖  Leçon", "cours"),
                             ("🎮  Télécommande", "telecommande")]),
    "Caméra": ("📷", "blue", [("📱  Connexion du téléphone", "connexion"),
                              ("📐  Calibration", "calibration"),
                              ("👆  Pointeur", "pointeur")]),
}


class PageMenus(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(22)
        lay.addWidget(entete("Menus", "Un menu principal et des sous-menus pour naviguer."))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ----- niveau 1 : menu principal -----
        principal = Carte()
        principal.setFixedWidth(330)
        principal.lay.addWidget(etiquette("Menu principal", "h2"))
        groupe = QButtonGroup(self)
        groupe.setExclusive(True)
        self.boutons = {}
        for nom, (icone, ton, _) in MENUS.items():
            b = bouton("%s   %s" % (icone, nom), ton,
                       lambda _=False, n=nom: self.ouvrir(n), checkable=True)
            b.setMinimumHeight(58)
            groupe.addButton(b)
            principal.lay.addWidget(b)
            self.boutons[nom] = b
        principal.lay.addStretch()
        corps.addWidget(principal)

        # ----- niveau 2 : sous-menu -----
        self.sous = Carte()
        self.titre_sous = etiquette("", "h2")
        self.sous.lay.addWidget(self.titre_sous)
        self.zone = QVBoxLayout()
        self.zone.setSpacing(12)
        self.sous.lay.addLayout(self.zone)
        self.sous.lay.addStretch()
        corps.addWidget(self.sous, 1)

        self.ouvrir("Outils")

    def ouvrir(self, nom):
        self.boutons[nom].setChecked(True)
        self.titre_sous.setText("Menu principal  ›  %s" % nom)
        while self.zone.count():                     # vider l'ancien sous-menu
            item = self.zone.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        _, ton, items = MENUS[nom]
        for texte, page in items:
            b = bouton(texte + "      →", "blanc",
                       lambda _=False, p=page: self.app.afficher(p))
            b.setMinimumHeight(54)
            b.setStyleSheet("text-align: left;")
            self.zone.addWidget(b)
