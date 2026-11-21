# ============================================================
# page_image.py : afficher une image + zoom avant / arriere / origine
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QScrollArea, QFileDialog)
from interface.widgets import Carte, Puce, entete, etiquette, bouton


class PageImage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app
        self.image = None            # image d'origine (QPixmap)
        self.zoom = 1.0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(22)
        self.puce_zoom = Puce("Zoom 100 %", "info")
        lay.addWidget(entete("Image & Zoom", "Affiche une image, zoome et reviens à la vue d'origine.",
                             self.puce_zoom))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ----- zone image (avec barres de defilement) -----
        carte = Carte(avec_ombre=False)
        carte.lay.setContentsMargins(14, 14, 14, 14)
        self.defil = QScrollArea()
        self.defil.setWidgetResizable(False)
        self.defil.setAlignment(Qt.AlignCenter)
        self.label = QLabel("Aucune image\n\nClique sur « Ouvrir une image »")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #A79FC2; font-size: 15px;")
        self.defil.setWidget(self.label)
        self.defil.setStyleSheet("QScrollArea { background: #EEE9FA; border-radius: 18px; }")
        carte.lay.addWidget(self.defil)
        corps.addWidget(carte, 1)

        # ----- outils -----
        outils = Carte()
        outils.setFixedWidth(290)
        outils.lay.addWidget(etiquette("Outils", "h2"))
        outils.lay.addWidget(bouton("📂   Ouvrir une image", "peach", self.ouvrir))
        outils.lay.addSpacing(6)
        outils.lay.addWidget(bouton("➕   Zoom avant", "mint", self.zoom_avant))
        outils.lay.addWidget(bouton("➖   Zoom arrière", "blue", self.zoom_arriere))
        outils.lay.addWidget(bouton("↺   Vue d'origine", "pink", self.origine))
        outils.lay.addStretch()
        corps.addWidget(outils)

    def ouvrir(self):
        chemin, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if chemin:
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
