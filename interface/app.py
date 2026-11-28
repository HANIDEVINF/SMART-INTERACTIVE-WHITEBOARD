# ============================================================
# app.py : fenetre principale
#  - pages empilees (une par fichier)
#  - boucle camera : suit la main et deplace le reticule
#  - telecommande : Next = clic gauche, Previous = clic droit
# ============================================================
from PySide6.QtCore import Qt, QEvent, QTimer, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QMainWindow, QStackedWidget, QApplication,
                               QVBoxLayout, QHBoxLayout)
import config
from camera import Camera
from tracker import Suiveur
from remote import Telecommande
from interface.widgets import FondTheme, Pilule
from interface.reticule import Reticule
from interface.page_accueil import PageAccueil
from interface.page_dessin import PageDessin
from interface.page_image import PageImage
from interface.page_cours import PageCours
from interface.page_reglages import PageReglages
from interface.page_connexion import PageConnexion
from interface.page_calibration import PageCalibration
from interface.page_telecommande import PageTelecommande


class FenetrePrincipale(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Whiteboard")
        self.resize(1280, 800)
        self.setMinimumSize(1100, 700)

        # ----- donnees partagees entre les pages -----
        self.camera = Camera()
        self.suiveur = Suiveur()
        self.reglages = config.charger_reglages()
        self.telecommande = Telecommande(self.reglages)
        self.pointeur = None            # position du pointeur (QPoint, repere de la fenetre)
        self.cible_survol = None

        # ----- fond + pages + pilules du bas -----
        self.conteneur = FondTheme()
        self.setCentralWidget(self.conteneur)
        lay = QVBoxLayout(self.conteneur)
        lay.setContentsMargins(48, 34, 48, 20)
        lay.setSpacing(8)

        self.pile = QStackedWidget()
        lay.addWidget(self.pile, 1)
        self.pages = {
            "accueil": PageAccueil(self),
            "dessin": PageDessin(self),
            "images": PageImage(self),
            "cours": PageCours(self),
            "reglages": PageReglages(self),
            "camera": PageConnexion(self),
            "calibration": PageCalibration(self),
            "telecommande": PageTelecommande(self),
        }
        for page in self.pages.values():
            self.pile.addWidget(page)

        pilules = QHBoxLayout()
        pilules.setSpacing(34)
        pilules.addStretch()
        pilules.addWidget(Pilule("NEXT: left click", "or"))
        pilules.addWidget(Pilule("PREVIOUS: right click", "rose"))
        pilules.addStretch()
        lay.addLayout(pilules)

        # ----- reticule (la cible), au-dessus de tout -----
        self.reticule = Reticule(self.conteneur)
        self.conteneur.plein_cadre.append(self.reticule)
        self.reticule.setGeometry(self.conteneur.rect())
        self.reticule.raise_()

        # ----- boucle principale (environ 33 images / seconde) -----
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)

        QApplication.instance().installEventFilter(self)
        self.afficher("accueil")

    # ------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------
    def afficher(self, nom):
        self.pile.setCurrentWidget(self.pages[nom])
        self.reticule.raise_()

    def retour(self):
        """Revient a la page parente (accueil par defaut)."""
        page = self.pile.currentWidget()
        if page is self.pages["accueil"]:
            return
        self.afficher(getattr(page, "parent_page", "accueil"))

    # ------------------------------------------------------------
    # Boucle principale : camera -> main -> reticule
    # ------------------------------------------------------------
    def tick(self):
        page = self.pile.currentWidget()

        frame = self.camera.lire()
        if frame is not None:
            self.suiveur.traiter(frame, getattr(page, "besoin_cadre", False))
        else:
            self.suiveur.vider()

        # le pointeur suit la main ; sans main, il suit la souris (pour tester)
        W, H = self.conteneur.width(), self.conteneur.height()
        pos = None
        n = self.suiveur.pointeur_norm
        if n is not None:
            pos = QPoint(int(n[0] * W), int(n[1] * H))
        else:
            p = self.conteneur.mapFromGlobal(QCursor.pos())
            if self.conteneur.rect().contains(p):
                pos = p
        self.pointeur = pos
        self.reticule.definir(pos)
        self.maj_survol(pos)

        if hasattr(page, "maj"):
            page.maj()

    def maj_survol(self, pos):
        """Met en valeur la tuile qui se trouve sous le reticule."""
        cible = None
        if pos is not None:
            cible = QApplication.widgetAt(self.conteneur.mapToGlobal(pos))
            while cible is not None and not hasattr(cible, "definir_survol"):
                cible = cible.parentWidget()
        if cible is not self.cible_survol:
            for w, valeur in ((self.cible_survol, False), (cible, True)):
                if w is not None:
                    try:
                        w.definir_survol(valeur)
                    except RuntimeError:        # widget deja supprime
                        pass
            self.cible_survol = cible

    # ------------------------------------------------------------
    # Telecommande : Next = clic gauche, Previous = clic droit
    # ------------------------------------------------------------
    def clic(self, bouton):
        if bouton == "droit":                   # clic droit = retour / annuler
            page = self.pile.currentWidget()
            if hasattr(page, "clic_droit"):
                page.clic_droit()
            else:
                self.retour()
            return
        if self.pointeur is None:
            return
        glob = self.conteneur.mapToGlobal(self.pointeur)
        cible = QApplication.widgetAt(glob)
        if cible is not None:                   # clic gauche a la position du reticule
            QTest.mouseClick(cible, Qt.LeftButton, Qt.NoModifier,
                             cible.mapFromGlobal(glob))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and not event.isAutoRepeat():
            page = self.pile.currentWidget()
            if hasattr(page, "recevoir") and page.recevoir(event):
                return True                     # la page a utilise la touche
            action = self.telecommande.action(event.key())
            if action:
                self.clic(action)
                return True
        return False

    def closeEvent(self, event):
        self.camera.arreter()
        config.sauver_reglages(self.reglages)
        super().closeEvent(event)
