# ============================================================
# widgets.py : composants graphiques reutilisables
# (cartes, boutons, puces, zone video, mini tableau...)
# ============================================================
import cv2
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QRect
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QLinearGradient,
                           QBrush, QPen, QImage, QPixmap, QFont)
from PySide6.QtWidgets import (QFrame, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QWidget, QGraphicsDropShadowEffect,
                               QSizePolicy)
import config


# ------------------------------------------------------------
# Fonctions utiles
# ------------------------------------------------------------
def ombre(widget, flou=30, decalage=8, alpha=40):
    """Ajoute une ombre douce sous un widget."""
    effet = QGraphicsDropShadowEffect(widget)
    effet.setBlurRadius(flou)
    effet.setOffset(0, decalage)
    effet.setColor(QColor(90, 70, 160, alpha))
    widget.setGraphicsEffect(effet)


def etiquette(texte, nom=None, wrap=False, align=None):
    lab = QLabel(texte)
    if nom:
        lab.setObjectName(nom)
    lab.setWordWrap(wrap)
    if align:
        lab.setAlignment(align)
    return lab


def bouton(texte, variante="primaire", slot=None, checkable=False):
    b = QPushButton(texte.replace("&", "&&"))   # && = afficher un vrai &
    b.setProperty("variante", variante)
    b.setCursor(Qt.PointingHandCursor)
    b.setCheckable(checkable)
    if slot:
        b.clicked.connect(slot)
    return b


def rafraichir_style(widget):
    """A appeler apres un setProperty pour appliquer le nouveau style."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Carte(QFrame):
    """Carte blanche aux coins arrondis."""

    def __init__(self, avec_ombre=True):
        super().__init__()
        self.setObjectName("card")
        if avec_ombre:
            ombre(self, 28, 8, 28)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(24, 22, 24, 22)
        self.lay.setSpacing(12)


class Puce(QLabel):
    """Petite pastille d'etat (ok / off / warn / info)."""

    def __init__(self, texte="", etat="off"):
        super().__init__(texte)
        self.setObjectName("puce")
        self.setProperty("etat", etat)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def definir(self, texte, etat):
        self.setText(texte)
        self.setProperty("etat", etat)
        rafraichir_style(self)


def entete(titre, sous_titre, widget_droite=None):
    """Titre de page + sous-titre (+ widget a droite)."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    textes = QVBoxLayout()
    textes.setSpacing(2)
    textes.addWidget(etiquette(titre, "titre_page"))
    textes.addWidget(etiquette(sous_titre, "sous_titre"))
    lay.addLayout(textes)
    lay.addStretch()
    if widget_droite is not None:
        lay.addWidget(widget_droite)
    return w


# ------------------------------------------------------------
# Banniere de l'accueil (degrade + cercles decoratifs)
# ------------------------------------------------------------
class Hero(QFrame):
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0, 0, -1, -1)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0.0, QColor("#E4DAFB"))
        g.setColorAt(0.55, QColor("#FCDDE9"))
        g.setColorAt(1.0, QColor("#D5E8FD"))
        chemin = QPainterPath()
        chemin.addRoundedRect(r, 28, 28)
        p.fillPath(chemin, QBrush(g))
        p.setClipPath(chemin)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 95))
        p.drawEllipse(QPointF(r.right() - 90, r.top() + 10), 150, 150)
        p.setBrush(QColor(255, 255, 255, 70))
        p.drawEllipse(QPointF(r.right() - 300, r.bottom() + 20), 100, 100)
        p.setBrush(QColor(255, 255, 255, 60))
        p.drawEllipse(QPointF(r.right() - 30, r.bottom() - 20), 70, 70)


# ------------------------------------------------------------
# Carte cliquable de l'accueil
# ------------------------------------------------------------
class CarteAccueil(QFrame):
    clique = Signal()

    def __init__(self, icone, titre, description, ton):
        super().__init__()
        self.setObjectName("homecard")
        self.setProperty("ton", ton)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(170)
        ombre(self, 26, 6, 26)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(4)
        badge = QLabel(icone)
        badge.setObjectName("badge")
        badge.setProperty("ton", ton)
        badge.setFixedSize(60, 60)
        badge.setAlignment(Qt.AlignCenter)
        t = etiquette(titre, "carte_titre")
        d = etiquette(description, "muted", wrap=True)
        for w in (badge, t, d):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(badge)
        lay.addSpacing(8)
        lay.addWidget(t)
        lay.addWidget(d)
        lay.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clique.emit()


# ------------------------------------------------------------
# Zone d'affichage de la video (coins arrondis)
# ------------------------------------------------------------
class VideoLabel(QWidget):
    def __init__(self, texte="Aucune image", min_l=520, min_h=320):
        super().__init__()
        self.pix = None
        self.texte = texte
        self.setMinimumSize(min_l, min_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def afficher_frame(self, frame):
        """frame = image OpenCV (BGR) ou None."""
        if frame is None:
            self.pix = None
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, _ = rgb.shape
            image = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
            self.pix = QPixmap.fromImage(image)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        chemin = QPainterPath()
        chemin.addRoundedRect(QRectF(self.rect()), 18, 18)
        p.setClipPath(chemin)
        p.fillRect(self.rect(), QColor("#EEE9FA"))
        if self.pix is not None:
            cible = self.pix.size().scaled(self.size(), Qt.KeepAspectRatio)
            x = (self.width() - cible.width()) // 2
            y = (self.height() - cible.height()) // 2
            p.drawPixmap(QRect(x, y, cible.width(), cible.height()), self.pix)
        else:
            p.setPen(QColor("#A79FC2"))
            p.setFont(QFont("Segoe UI", 13))
            p.drawText(self.rect(), Qt.AlignCenter, self.texte)


# ------------------------------------------------------------
# Mini tableau : montre ou se trouve le pointeur sur le tableau
# ------------------------------------------------------------
class MiniTableau(QWidget):
    def __init__(self):
        super().__init__()
        self.point = None            # (x, y) en unites du tableau
        self.setMinimumHeight(190)

    def definir(self, point):
        self.point = point
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # rectangle du tableau avec le meme format que le vrai tableau
        marge = 6
        dispo = QRectF(self.rect()).adjusted(marge, marge, -marge, -marge)
        ratio = config.TAB_L / config.TAB_H
        l = dispo.width()
        h = l / ratio
        if h > dispo.height():
            h = dispo.height()
            l = h * ratio
        r = QRectF(dispo.center().x() - l / 2, dispo.center().y() - h / 2, l, h)

        p.setPen(QPen(QColor("#D9D0F0"), 2))
        p.setBrush(QColor("#FBFAFF"))
        p.drawRoundedRect(r, 14, 14)
        # grille legere
        p.setPen(QPen(QColor("#EEE9FA"), 1))
        for i in range(1, 5):
            x = r.left() + r.width() * i / 5
            p.drawLine(QPointF(x, r.top() + 8), QPointF(x, r.bottom() - 8))
        for j in range(1, 3):
            y = r.top() + r.height() * j / 3
            p.drawLine(QPointF(r.left() + 8, y), QPointF(r.right() - 8, y))

        if self.point is None:
            p.setPen(QColor("#B7B0CC"))
            p.drawText(r, Qt.AlignCenter, "Pas de pointeur")
            return
        x = r.left() + min(max(self.point[0] / config.TAB_L, 0), 1) * r.width()
        y = r.top() + min(max(self.point[1] / config.TAB_H, 0), 1) * r.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(245, 155, 187, 70))
        p.drawEllipse(QPointF(x, y), 18, 18)
        p.setBrush(QColor("#F59BBB"))
        p.drawEllipse(QPointF(x, y), 8, 8)
