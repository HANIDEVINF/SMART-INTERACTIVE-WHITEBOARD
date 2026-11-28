# ============================================================
# page_image.py : afficher une image + zoom avant / arriere / origine
# Les images du dossier assets/images apparaissent en miniatures.
# ============================================================
import os
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QScrollArea, QFileDialog, QPushButton)
import config
from interface.widgets import Panneau, Puce, entete, etiquette, bouton


class PageImage(QWidget):
    parent_page = "accueil"

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.image = None            # image d'origine (QPixmap)
        self.zoom = 1.0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        self.puce_zoom = Puce("Zoom 100 %", "info")
        lay.addWidget(entete(app, "Images", droite=self.puce_zoom))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ----- zone image (avec barres de defilement) -----
        cadre = Panneau((8, 8, 8, 8))
        self.defil = QScrollArea()
        self.defil.setWidgetResizable(False)
        self.defil.setAlignment(Qt.AlignCenter)
        self.label = QLabel("No image")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: rgba(248, 233, 184, 150); font-size: 16px;")
        self.defil.setWidget(self.label)
        cadre.lay.addWidget(self.defil)
        corps.addWidget(cadre, 1)

        # ----- outils + miniatures -----
        outils = Panneau()
        outils.setFixedWidth(300)
        outils.lay.addWidget(bouton("Open", "or", self.ouvrir, ico="folder-open"))
        outils.lay.addSpacing(4)
        outils.lay.addWidget(bouton("Zoom in", "violet", self.zoom_avant, ico="zoom-in"))
        outils.lay.addWidget(bouton("Zoom out", "bleu", self.zoom_arriere, ico="zoom-out"))
        outils.lay.addWidget(bouton("Original", "orange", self.origine, ico="rotate-ccw"))
        outils.lay.addSpacing(8)
        outils.lay.addWidget(etiquette("Gallery", "h2"))
        self.miniatures = QVBoxLayout()
        self.miniatures.setSpacing(8)
        outils.lay.addLayout(self.miniatures)
        outils.lay.addStretch()
        corps.addWidget(outils)
        self.charger_galerie()

    # ---------------- galerie ----------------
    def charger_galerie(self):
        dossier = os.path.join(config.DOSSIER, "assets", "images")
        if not os.path.isdir(dossier):
            return
        for nom in sorted(os.listdir(dossier))[:4]:
            if not nom.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                continue
            chemin = os.path.join(dossier, nom)
            pix = QPixmap(chemin)
            if pix.isNull():
                continue
            b = QPushButton()
            b.setProperty("variante", "sombre")
            vignette = pix.scaled(250, 62, Qt.KeepAspectRatioByExpanding,
                                  Qt.SmoothTransformation)
            vignette = vignette.copy((vignette.width() - 250) // 2,
                                     (vignette.height() - 62) // 2, 250, 62)
            b.setIcon(QIcon(vignette))
            b.setIconSize(QSize(250, 62))
            b.setFixedHeight(76)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, c=chemin: self.charger(c))
            self.miniatures.addWidget(b)

    # ---------------- actions ----------------
    def ouvrir(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choose an image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if chemin:
            self.charger(chemin)

    def charger(self, chemin):
        pix = QPixmap(chemin)
        if not pix.isNull():
            self.image = pix
            self.zoom = 1.0
            self.redessiner()

    def zoom_avant(self):
        self.zoom = min(self.zoom * 1.25, 6.0)
        self.redessiner()

    def zoom_arriere(self):
        self.zoom = max(self.zoom / 1.25, 0.2)
        self.redessiner()

    def origine(self):
        self.zoom = 1.0
        self.redessiner()

    def clic_droit(self):
        """Clic droit (Previous) : dezoome, puis retour au menu."""
        if self.zoom > 1.01:
            self.zoom_arriere()
        else:
            self.app.retour()

    def redessiner(self):
        if self.image is None:
            return
        vue = self.defil.viewport().size()
        # zoom 100 % = l'image tient entierement dans la zone
        base = min(vue.width() / self.image.width(),
                   vue.height() / self.image.height())
        taille = self.image.size() * (base * self.zoom)
        pix = self.image.scaled(taille, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(pix)
        self.label.resize(max(pix.width(), vue.width()),
                          max(pix.height(), vue.height()))
        self.puce_zoom.definir("Zoom %d %%" % round(self.zoom * 100), "info")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.redessiner()
