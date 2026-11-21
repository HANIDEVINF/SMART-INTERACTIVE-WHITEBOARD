# ============================================================
# app.py : fenetre principale = barre laterale + pages
# Contient aussi les donnees partagees entre les pages
# ============================================================
from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QFrame, QLabel, QStackedWidget, QPushButton,
                               QButtonGroup, QApplication)
import config
from camera import Camera
from interface.widgets import etiquette
from interface.page_accueil import PageAccueil
from interface.page_connexion import PageConnexion
from interface.page_camera import PageCamera
from interface.page_telecommande import PageTelecommande
from interface.page_menus import PageMenus
from interface.page_dessin import PageDessin
from interface.page_image import PageImage
from interface.page_cours import PageCours
from interface.page_parametres import PageParametres

# Menu de la barre laterale : (section, [(nom de la page, icone, texte)])
SECTIONS = [
    ("PRINCIPAL", [("accueil", "🏠", "Accueil"),
                   ("connexion", "📱", "Caméra du téléphone")]),
    ("VISION", [("calibration", "📐", "Calibration"),
                ("pointeur", "👆", "Pointeur"),
                ("telecommande", "🎮", "Télécommande")]),
    ("OUTILS", [("menus", "🧭", "Menus"),
                ("dessin", "🎨", "Dessin libre"),
                ("image", "🖼️", "Image & Zoom"),
                ("cours", "📚", "Cours")]),
    ("SYSTÈME", [("parametres", "⚙️", "Paramètres")]),
]


class FenetrePrincipale(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tableau Blanc Interactif")
        self.resize(1360, 840)
        self.setMinimumSize(1180, 720)

        # ----- donnees partagees entre les pages -----
        self.camera = Camera()
        self.reglages = config.charger_reglages()
        self.coins_valides = None     # coins du tableau apres calibrage
        self.M = None                 # matrice image -> tableau
        self.pointeur = None          # position du doigt dans l'image

        centre = QWidget()
        centre.setObjectName("fond")
        centre.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(centre)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.setCentralWidget(centre)

        self.boutons_nav = {}
        lay.addWidget(self.creer_barre_laterale())

        # ----- pages empilees -----
        self.pile = QStackedWidget()
        lay.addWidget(self.pile, 1)
        self.pages = {
            "accueil": PageAccueil(self),
            "connexion": PageConnexion(self),
            "calibration": PageCamera(self, "calibration"),
            "pointeur": PageCamera(self, "pointeur"),
            "telecommande": PageTelecommande(self),
            "menus": PageMenus(self),
            "dessin": PageDessin(self),
            "image": PageImage(self),
            "cours": PageCours(self),
            "parametres": PageParametres(self),
        }
        for page in self.pages.values():
            self.pile.addWidget(page)

        # Mise a jour regulière de l'etat de la camera (barre laterale)
        self.timer_statut = QTimer(self)
        self.timer_statut.timeout.connect(self.maj_statut)
        self.timer_statut.start(400)

        # Pour recevoir les touches de la telecommande
        QApplication.instance().installEventFilter(self)
        self.afficher("accueil")

    # ------------------------------------------------------------
    def creer_barre_laterale(self):
        barre = QFrame()
        barre.setObjectName("sidebar")
        barre.setFixedWidth(270)
        lay = QVBoxLayout(barre)
        lay.setContentsMargins(18, 24, 18, 20)
        lay.setSpacing(4)

        # logo
        haut = QHBoxLayout()
        logo = QLabel("🧑‍🏫")
        logo.setObjectName("logo")
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignCenter)
        textes = QVBoxLayout()
        textes.setSpacing(0)
        textes.addWidget(etiquette("Smart Board", "logo_titre"))
        textes.addWidget(etiquette("Vision 2026 · 2027", "muted"))
        haut.addWidget(logo)
        haut.addSpacing(8)
        haut.addLayout(textes)
        haut.addStretch()
        lay.addLayout(haut)
        lay.addSpacing(18)

        # boutons de navigation
        groupe = QButtonGroup(self)
        groupe.setExclusive(True)
        for titre_section, items in SECTIONS:
            lay.addSpacing(10)
            lay.addWidget(etiquette(titre_section, "section"))
            lay.addSpacing(2)
            for nom, icone, texte in items:
                b = QPushButton(("%s   %s" % (icone, texte)).replace("&", "&&"))
                b.setObjectName("nav")
                b.setCheckable(True)
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _=False, n=nom: self.afficher(n))
                groupe.addButton(b)
                lay.addWidget(b)
                self.boutons_nav[nom] = b
        lay.addStretch()

        # carte d'etat de la camera
        self.carte_statut = QFrame()
        self.carte_statut.setObjectName("statut_camera")
        sl = QHBoxLayout(self.carte_statut)
        sl.setContentsMargins(14, 12, 14, 12)
        self.point_statut = QLabel("●")
        self.point_statut.setStyleSheet("color: #C9C2DD; font-size: 18px;")
        col = QVBoxLayout()
        col.setSpacing(0)
        self.texte_statut = etiquette("Caméra non connectée", "carte_titre")
        self.texte_statut.setStyleSheet("font-size: 13px;")
        self.sous_statut = etiquette("Aucun flux vidéo", "muted")
        col.addWidget(self.texte_statut)
        col.addWidget(self.sous_statut)
        sl.addWidget(self.point_statut)
        sl.addLayout(col)
        sl.addStretch()
        lay.addWidget(self.carte_statut)
        return barre

    # ------------------------------------------------------------
    def afficher(self, nom):
        """Affiche une page et selectionne son bouton dans le menu."""
        self.pile.setCurrentWidget(self.pages[nom])
        self.boutons_nav[nom].setChecked(True)

    def maj_statut(self):
        etat = self.camera.etat
        if etat == "connectee":
            couleur, texte, sous = "#5BC48C", "Caméra connectée", "Flux vidéo actif"
        elif etat == "connexion":
            couleur, texte, sous = "#F2A877", "Connexion...", "Patiente un instant"
        elif etat == "echec":
            couleur, texte, sous = "#F28B9B", "Connexion échouée", "Vérifie l'adresse"
        else:
            couleur, texte, sous = "#C9C2DD", "Caméra non connectée", "Aucun flux vidéo"
        self.point_statut.setStyleSheet("color: %s; font-size: 18px;" % couleur)
        self.texte_statut.setText(texte)
        self.sous_statut.setText(sous)

    def eventFilter(self, obj, event):
        # Transmet les touches a la page Telecommande (sans les bloquer)
        if event.type() == QEvent.KeyPress and not event.isAutoRepeat():
            page = self.pages["telecommande"]
            if self.pile.currentWidget() is page:
                page.recevoir(event)
        return False

    def closeEvent(self, event):
        self.camera.arreter()
        config.sauver_reglages(self.reglages)
        super().closeEvent(event)
