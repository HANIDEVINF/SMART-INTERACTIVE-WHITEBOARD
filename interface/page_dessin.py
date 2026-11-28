# ============================================================
# page_dessin.py : dessin libre avec la MAIN
#  - le pointeur (reticule) est le stylo
#  - clic gauche (Next) sur le tableau blanc : lever / baisser le stylo
#  - clic droit (Previous) : annuler le dernier trait
# La souris fonctionne aussi (le reticule suit la souris sans camera).
# ============================================================
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QPen, QPolygonF,
                           QFont, QFontMetrics)
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QSlider, QFileDialog, QScrollArea)
from interface import theme
from interface.widgets import (Panneau, Puce, VideoLabel, entete, etiquette,
                               bouton, mettre_icone, rafraichir_style)

COULEURS = ["#E8344F", "#2F6FDB", "#2E9E68", "#7C3FA0", "#E88B1A", "#2B1A24"]
FOND_TABLEAU = "#FFFBEF"


class Trait:
    """Un trait = couleur + epaisseur + points (entre 0 et 1, independants de la taille)."""

    def __init__(self, couleur, epaisseur):
        self.couleur = couleur
        self.epaisseur = epaisseur
        self.points = []


class ZoneDessin(QWidget):
    """Tableau blanc virtuel."""
    clique = Signal()

    def __init__(self):
        super().__init__()
        self.traits = []
        self.trait_courant = None
        self.couleur = COULEURS[0]
        self.epaisseur = 8
        self.stylo = False              # False = stylo leve
        self.afficher_etat = True
        self.setMinimumSize(520, 360)

    # ---------- gestion des traits ----------
    def debut_trait(self, n):
        t = Trait(self.couleur, self.epaisseur)
        t.points.append(n)
        self.traits.append(t)
        self.trait_courant = t
        self.update()

    def ajouter_point(self, n):
        t = self.trait_courant
        if t is None:
            return
        dx = (n[0] - t.points[-1][0]) * self.width()
        dy = (n[1] - t.points[-1][1]) * self.height()
        d2 = dx * dx + dy * dy
        if d2 > 250 * 250:               # saut trop grand : nouveau trait
            self.fin_trait()
            self.debut_trait(n)
            return
        if d2 < 1:
            return
        t.points.append(n)
        self.update()

    def fin_trait(self):
        self.trait_courant = None

    def defaire(self):
        self.fin_trait()
        if self.traits:
            self.traits.pop()
            self.update()

    def effacer(self):
        self.fin_trait()
        self.traits = []
        self.update()

    def image_propre(self):
        """Image du dessin sans la pastille d'etat."""
        self.afficher_etat = False
        pix = self.grab()
        self.afficher_etat = True
        return pix

    # ---------- souris ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clique.emit()

    # ---------- affichage ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        chemin = QPainterPath()
        chemin.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)
        p.setClipPath(chemin)
        p.fillRect(self.rect(), QColor(FOND_TABLEAU))

        w, h = self.width(), self.height()
        for t in self.traits:
            p.setPen(QPen(QColor(t.couleur), t.epaisseur, Qt.SolidLine,
                          Qt.RoundCap, Qt.RoundJoin))
            pts = [QPointF(x * w, y * h) for x, y in t.points]
            if len(pts) == 1:
                p.drawPoint(pts[0])
            else:
                p.drawPolyline(QPolygonF(pts))

        if not self.afficher_etat:
            return
        # pastille d'etat en haut a gauche
        texte = "Pen down" if self.stylo else "Pen up"
        police = QFont(theme.FAMILLE_TEXTE, 10)
        police.setBold(True)
        p.setFont(police)
        largeur = QFontMetrics(police).horizontalAdvance(texte) + 30
        r = QRectF(16, 14, largeur, 32)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2D6A4B") if self.stylo else QColor(58, 13, 32, 200))
        p.drawRoundedRect(r, 16, 16)
        p.setPen(QColor("#E2F6E9") if self.stylo else QColor(theme.CREME))
        p.drawText(r, Qt.AlignCenter, texte)


class ApercuStylo(QWidget):
    """Petit trait qui montre la couleur et l'epaisseur choisies."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(54)
        self.couleur = COULEURS[0]
        self.epaisseur = 8

    def definir(self, couleur, epaisseur):
        self.couleur = couleur
        self.epaisseur = epaisseur
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(FOND_TABLEAU))
        p.drawRoundedRect(QRectF(self.rect()), 12, 12)
        p.setPen(QPen(QColor(self.couleur), self.epaisseur, Qt.SolidLine, Qt.RoundCap))
        y = self.height() / 2
        p.drawLine(QPointF(28, y), QPointF(self.width() - 28, y))


class PageDessin(QWidget):
    parent_page = "accueil"

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.couleur = COULEURS[0]
        self.epaisseur = 8
        self.stylo = False
        self.gomme = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        self.puce_main = Puce("No hand", "off")
        lay.addWidget(entete(app, "Draw", droite=self.puce_main))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ----- tableau blanc -----
        cadre = Panneau((8, 8, 8, 8))
        self.zone = ZoneDessin()
        self.zone.clique.connect(self.basculer_stylo)
        cadre.lay.addWidget(self.zone)
        corps.addWidget(cadre, 1)

        # ----- colonne de droite (defilable) -----
        defil = QScrollArea()
        defil.setWidgetResizable(True)
        defil.setFixedWidth(350)
        defil.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        droite = QWidget()
        dl = QVBoxLayout(droite)
        dl.setContentsMargins(0, 0, 8, 0)
        dl.setSpacing(14)
        defil.setWidget(droite)
        corps.addWidget(defil)

        self.video = VideoLabel("Camera offline", 300, 170)
        self.video.setMaximumHeight(190)
        dl.addWidget(self.video)

        p_stylo = Panneau((18, 16, 18, 16))
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
                "border: 3px solid #5B1035; } "
                "QPushButton:checked { border: 3px solid #F6D587; }" % c)
            b.clicked.connect(lambda _=False, c=c: self.choisir_couleur(c))
            grille.addWidget(b, i // 3, i % 3, Qt.AlignHCenter)
            self.pastilles.append(b)
        self.pastilles[0].setChecked(True)
        p_stylo.lay.addLayout(grille)
        self.curseur = QSlider(Qt.Horizontal)
        self.curseur.setRange(2, 40)
        self.curseur.setValue(8)
        self.curseur.valueChanged.connect(self.changer_epaisseur)
        p_stylo.lay.addWidget(self.curseur)
        self.apercu = ApercuStylo()
        p_stylo.lay.addWidget(self.apercu)
        dl.addWidget(p_stylo)

        p_act = Panneau((18, 16, 18, 16))
        self.btn_stylo = bouton("Pen up", "sombre", self.basculer_stylo, ico="hand")
        p_act.lay.addWidget(self.btn_stylo)
        g2 = QGridLayout()
        g2.setSpacing(10)
        self.btn_gomme = bouton("Eraser", "orange", self.basculer_gomme,
                                checkable=True, ico="eraser")
        petits = [self.btn_gomme,
                  bouton("Undo", "bleu", self.zone.defaire, ico="undo-2"),
                  bouton("Clear", "violet", self.zone.effacer, ico="trash"),
                  bouton("Save", "or", self.enregistrer, ico="save")]
        for i, b in enumerate(petits):
            b.setStyleSheet("padding: 11px 6px;")
            g2.addWidget(b, i // 2, i % 2)
        p_act.lay.addLayout(g2)
        dl.addWidget(p_act)
        dl.addStretch()

        # Les boutons ne prennent pas le clavier (sinon Espace les declenche)
        for b in self.findChildren(QPushButton):
            b.setFocusPolicy(Qt.NoFocus)
        self.appliquer_outil()

    # ---------------- outils ----------------
    def appliquer_outil(self):
        self.zone.fin_trait()
        if self.gomme:
            self.zone.couleur = FOND_TABLEAU
            self.zone.epaisseur = self.epaisseur * 3
        else:
            self.zone.couleur = self.couleur
            self.zone.epaisseur = self.epaisseur
        self.apercu.definir(self.zone.couleur if not self.gomme else "#C9BE9A",
                            self.zone.epaisseur)

    def choisir_couleur(self, c):
        self.couleur = c
        self.gomme = False
        self.btn_gomme.setChecked(False)
        for b, cb in zip(self.pastilles, COULEURS):
            b.setChecked(cb == c)
        self.appliquer_outil()

    def changer_epaisseur(self, v):
        self.epaisseur = v
        self.appliquer_outil()

    def basculer_gomme(self):
        self.gomme = self.btn_gomme.isChecked()
        self.appliquer_outil()

    def basculer_stylo(self):
        self.stylo = not self.stylo
        self.zone.stylo = self.stylo
        if self.stylo:
            self.btn_stylo.setText("  Pen down")
            self.btn_stylo.setProperty("variante", "rouge")
            mettre_icone(self.btn_stylo, "pencil", "rouge")
        else:
            self.btn_stylo.setText("  Pen up")
            self.btn_stylo.setProperty("variante", "sombre")
            mettre_icone(self.btn_stylo, "hand", "sombre")
            self.zone.fin_trait()
        rafraichir_style(self.btn_stylo)
        self.zone.update()

    def enregistrer(self):
        chemin, _ = QFileDialog.getSaveFileName(self, "Save", "drawing.png",
                                                "PNG image (*.png)")
        if chemin:
            self.zone.image_propre().save(chemin)

    # ---------------- clavier / telecommande ----------------
    def recevoir(self, event):
        """Espace = lever / baisser le stylo."""
        if event.key() == Qt.Key_Space:
            self.basculer_stylo()
            return True
        return False

    def clic_droit(self):
        """Clic droit (Previous) = annuler le dernier trait."""
        self.zone.defaire()

    # ---------------- appelee par la boucle principale ----------------
    def maj(self):
        s = self.app.suiveur
        self.video.afficher_frame(s.image)
        self.puce_main.definir("Hand detected" if s.main_detectee else "No hand",
                               "ok" if s.main_detectee else "off")

        pos = self.app.pointeur
        if pos is None or not self.stylo:
            self.zone.fin_trait()
            return
        local = self.zone.mapFrom(self.app.conteneur, pos)
        if self.zone.rect().contains(local):
            n = (local.x() / max(1, self.zone.width()),
                 local.y() / max(1, self.zone.height()))
            if self.zone.trait_courant is None:
                self.zone.debut_trait(n)
            else:
                self.zone.ajouter_point(n)
        else:
            self.zone.fin_trait()
