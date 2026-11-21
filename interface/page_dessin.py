# ============================================================
# page_dessin.py : dessin libre (couleurs, epaisseur, gomme, effacer)
# ============================================================
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QSlider, QFileDialog)
from interface.widgets import Carte, entete, etiquette, bouton

COULEURS = ["#FF8FAB", "#7FB5FF", "#7ED9A6", "#B39DDB", "#FFB26B", "#5B5170"]


class ZoneDessin(QWidget):
    """Zone blanche ou l'on dessine avec la souris."""

    def __init__(self):
        super().__init__()
        self.tampon = QPixmap(2400, 1600)       # l'image du dessin
        self.tampon.fill(Qt.white)
        self.couleur = QColor(COULEURS[0])
        self.epaisseur = 8
        self.dernier = None
        self.setMinimumSize(520, 360)
        self.setCursor(Qt.CrossCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        chemin = QPainterPath()
        chemin.addRoundedRect(QRectF(self.rect()), 18, 18)
        p.setClipPath(chemin)
        p.drawPixmap(0, 0, self.tampon)

    def trace(self, a, b):
        p = QPainter(self.tampon)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(self.couleur, self.epaisseur, Qt.SolidLine,
                      Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(a, b)
        p.end()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dernier = event.position().toPoint()
            self.trace(self.dernier, self.dernier)       # un simple point

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.dernier is not None:
            pos = event.position().toPoint()
            self.trace(self.dernier, pos)
            self.dernier = pos

    def mouseReleaseEvent(self, event):
        self.dernier = None

    def effacer(self):
        self.tampon.fill(Qt.white)
        self.update()


class PageDessin(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app
        self.couleur_choisie = COULEURS[0]

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(22)
        lay.addWidget(entete("Dessin libre", "Dessine, change de couleur ou d'épaisseur, efface."))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ----- zone de dessin -----
        carte = Carte(avec_ombre=False)
        carte.lay.setContentsMargins(14, 14, 14, 14)
        self.zone = ZoneDessin()
        carte.lay.addWidget(self.zone)
        corps.addWidget(carte, 1)

        # ----- outils -----
        outils = Carte()
        outils.setFixedWidth(290)
        outils.lay.addWidget(etiquette("Couleurs", "h2"))
        grille = QGridLayout()
        grille.setSpacing(10)
        self.pastilles = []
        for i, c in enumerate(COULEURS):
            b = QPushButton()
            b.setFixedSize(46, 46)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { background: %s; border-radius: 23px; "
                "border: 3px solid white; } "
                "QPushButton:checked { border: 3px solid #3B3355; }" % c)
            b.clicked.connect(lambda _=False, c=c: self.choisir(c))
            grille.addWidget(b, i // 3, i % 3)
            self.pastilles.append(b)
        self.pastilles[0].setChecked(True)
        outils.lay.addLayout(grille)

        outils.lay.addSpacing(8)
        outils.lay.addWidget(etiquette("Épaisseur", "h2"))
        self.curseur = QSlider(Qt.Horizontal)
        self.curseur.setRange(2, 40)
        self.curseur.setValue(8)
        self.curseur.valueChanged.connect(self.changer_epaisseur)
        outils.lay.addWidget(self.curseur)

        outils.lay.addSpacing(8)
        self.btn_gomme = bouton("🧽   Gomme", "yellow", self.gomme, checkable=True)
        outils.lay.addWidget(self.btn_gomme)
        outils.lay.addWidget(bouton("🗑️   Tout effacer", "pink", self.zone.effacer))
        outils.lay.addWidget(bouton("💾   Enregistrer", "blue", self.enregistrer))
        outils.lay.addStretch()
        corps.addWidget(outils)

    def choisir(self, c):
        self.couleur_choisie = c
        self.btn_gomme.setChecked(False)
        self.zone.couleur = QColor(c)
        for b in self.pastilles:
            b.setChecked(False)
        # recoche la pastille choisie
        self.pastilles[COULEURS.index(c)].setChecked(True)

    def changer_epaisseur(self, v):
        self.zone.epaisseur = v

    def gomme(self):
        if self.btn_gomme.isChecked():
            self.zone.couleur = QColor("white")
        else:
            self.zone.couleur = QColor(self.couleur_choisie)

    def enregistrer(self):
        chemin, _ = QFileDialog.getSaveFileName(self, "Enregistrer", "dessin.png",
                                                "Image PNG (*.png)")
        if chemin:
            self.zone.tampon.copy(0, 0, self.zone.width(),
                                  self.zone.height()).save(chemin)
