# ============================================================
# widgets.py : composants graphiques du theme "Smart Whiteboard"
# (fond, titre, tuiles, pilules, panneaux, video...)
# ============================================================
import cv2
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QRect, QSize, QTimer
from PySide6.QtGui import (QColor, QPainter, QPainterPath, QPen, QImage,
                           QPixmap, QFont, QFontMetrics, QFontMetricsF,
                           QLinearGradient, QRadialGradient, QBrush, QPolygonF)
from PySide6.QtWidgets import (QFrame, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QWidget, QSizePolicy,
                               QGraphicsDropShadowEffect)
import config
from interface import icones, theme


# ------------------------------------------------------------
# Petites fonctions utiles
# ------------------------------------------------------------
def losange(p, cx, cy, r):
    """Dessine un losange centre en (cx, cy) de demi-diagonale r."""
    p.drawPolygon(QPolygonF([QPointF(cx, cy - r), QPointF(cx + r, cy),
                             QPointF(cx, cy + r), QPointF(cx - r, cy)]))


def ombre_texte(widget):
    """Ombre portee sombre derriere un texte."""
    e = QGraphicsDropShadowEffect(widget)
    e.setBlurRadius(0)
    e.setOffset(3, 3)
    e.setColor(QColor(15, 2, 8, 200))
    widget.setGraphicsEffect(e)


def etiquette(texte, nom=None, wrap=False, align=None):
    lab = QLabel(texte)
    if nom:
        lab.setObjectName(nom)
    lab.setWordWrap(wrap)
    if align:
        lab.setAlignment(align)
    return lab


def mettre_icone(b, ico, variante="sombre"):
    couleur = theme.ENCRE if variante in ("or", "rose") else theme.CREME
    b.setIcon(icones.icone(ico, couleur, 18))
    b.setIconSize(QSize(18, 18))


def bouton(texte, variante="or", slot=None, checkable=False, ico=None):
    """Bouton du theme. variante : or, rose, rouge, violet, bleu, orange, sombre."""
    b = QPushButton((("  " + texte) if ico else texte).replace("&", "&&"))
    b.setProperty("variante", variante)
    b.setCursor(Qt.PointingHandCursor)
    b.setCheckable(checkable)
    if ico:
        mettre_icone(b, ico, variante)
    if slot:
        b.clicked.connect(slot)
    return b


def rafraichir_style(widget):
    """A appeler apres un setProperty pour appliquer le nouveau style."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Panneau(QFrame):
    """Cadre sombre a bordure doree."""

    def __init__(self, marges=(22, 20, 22, 20)):
        super().__init__()
        self.setObjectName("panneau")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(*marges)
        self.lay.setSpacing(12)


class Puce(QLabel):
    """Petite pastille d'etat (ok / off / warn / info)."""

    def __init__(self, texte="", etat="off"):
        super().__init__(texte)
        self.setObjectName("puce")
        self.setProperty("etat", etat)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def definir(self, texte, etat):
        if texte != self.text() or etat != self.property("etat"):
            self.setText(texte)
            self.setProperty("etat", etat)
            rafraichir_style(self)


class PuceCamera(Puce):
    """Pastille qui affiche toujours l'etat de la camera."""

    def __init__(self, app):
        super().__init__("Camera offline", "off")
        self.app = app
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.maj)
        self.timer.start(400)
        self.maj()

    def maj(self):
        etat = self.app.camera.etat
        if etat == "connectee":
            self.definir("Camera connected", "ok")
        elif etat == "connexion":
            self.definir("Connecting...", "warn")
        elif etat == "echec":
            self.definir("Connection failed", "warn")
        else:
            self.definir("Camera offline", "off")


def entete(app, titre, retour="accueil", droite=None):
    """Haut de page : bouton Back, titre en lettres cursives, etat de la camera."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)

    gauche = QWidget()
    gauche.setFixedWidth(360)
    gl = QHBoxLayout(gauche)
    gl.setContentsMargins(0, 0, 0, 0)
    gl.addWidget(bouton("Back", "sombre", lambda: app.afficher(retour),
                        ico="arrow-left"))
    gl.addStretch()
    lay.addWidget(gauche)

    lay.addStretch()
    t = etiquette(titre, "titre_page")
    ombre_texte(t)
    lay.addWidget(t)
    lay.addStretch()

    d = QWidget()
    d.setFixedWidth(360)
    dl = QHBoxLayout(d)
    dl.setContentsMargins(0, 0, 0, 0)
    dl.setSpacing(8)
    dl.addStretch()
    if droite is not None:
        dl.addWidget(droite)
    dl.addWidget(PuceCamera(app))
    lay.addWidget(d)
    return w


# ------------------------------------------------------------
# Fond de la fenetre : bordeaux, losanges, cadre dore
# ------------------------------------------------------------
class FondTheme(QWidget):
    def __init__(self):
        super().__init__()
        self.cache = None
        self.plein_cadre = []      # widgets qui couvrent toute la fenetre

    def resizeEvent(self, event):
        self.cache = self.fabriquer(self.size())
        for w in self.plein_cadre:
            w.setGeometry(self.rect())

    def fabriquer(self, taille):
        w, h = taille.width(), taille.height()
        pix = QPixmap(taille)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        g = QRadialGradient(QPointF(w / 2, h * 0.45), max(w, h) * 0.75)
        g.setColorAt(0.0, QColor("#6E1743"))
        g.setColorAt(1.0, QColor("#3A0A24"))
        p.fillRect(0, 0, w, h, QBrush(g))

        # motif de losanges
        pas = 76
        p.setBrush(Qt.NoBrush)
        for ligne in range(-1, int(h / (pas / 2)) + 2):
            decal = pas / 2 if ligne % 2 else 0
            cy = ligne * pas / 2
            for col in range(-1, int(w / pas) + 2):
                cx = col * pas + decal
                p.setPen(QPen(QColor(255, 255, 255, 22), 2))
                losange(p, cx, cy, 24)
                p.setPen(QPen(QColor(255, 255, 255, 14), 1.5))
                losange(p, cx, cy, 11)

        # cadre dore (double filet) + losanges aux coins
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(theme.OR), 3))
        p.drawRect(QRectF(9, 9, w - 18, h - 18))
        p.setPen(QPen(QColor(233, 196, 106, 150), 1.5))
        p.drawRect(QRectF(17, 17, w - 34, h - 34))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.OR))
        for (x, y) in ((17, 17), (w - 17, 17), (17, h - 17), (w - 17, h - 17)):
            losange(p, x, y, 6)
        p.end()
        return pix

    def paintEvent(self, event):
        if self.cache is not None:
            QPainter(self).drawPixmap(0, 0, self.cache)


# ------------------------------------------------------------
# Grand titre de l'accueil
# ------------------------------------------------------------
class TitreOrne(QWidget):
    def __init__(self, titre="Smart Whiteboard",
                 petit="~ ESTABLISHED 2026 ~",
                 sous="Point with the marker, then press a remote button"):
        super().__init__()
        self.titre, self.petit, self.sous = titre, petit, sous
        self.setFixedHeight(228)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()

        # petit texte
        f1 = QFont(theme.FAMILLE_TEXTE)
        f1.setBold(True)
        f1.setPixelSize(13)
        f1.setLetterSpacing(QFont.AbsoluteSpacing, 2.5)
        p.setFont(f1)
        p.setPen(QColor(theme.OR))
        p.drawText(QRectF(0, 4, w, 22), Qt.AlignHCenter | Qt.AlignVCenter, self.petit)

        # titre cursif dore avec ombre
        f2 = QFont(theme.FAMILLE_TITRE)
        f2.setPixelSize(76)
        fm = QFontMetricsF(f2)
        x = (w - fm.horizontalAdvance(self.titre)) / 2
        y = 118
        chemin = QPainterPath()
        chemin.addText(x, y, f2, self.titre)
        p.save()
        p.translate(3, 4)
        p.fillPath(chemin, QColor(20, 2, 10, 170))
        p.restore()
        g = QLinearGradient(0, y - 62, 0, y + 14)
        g.setColorAt(0.0, QColor("#FFF4C6"))
        g.setColorAt(1.0, QColor("#E2A93C"))
        p.fillPath(chemin, QBrush(g))
        p.setPen(QPen(QColor("#9A6A18"), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(chemin)

        # filet avec losange
        cy = 142
        p.setPen(QPen(QColor(233, 196, 106, 210), 2))
        p.drawLine(QPointF(w / 2 - 200, cy), QPointF(w / 2 - 18, cy))
        p.drawLine(QPointF(w / 2 + 18, cy), QPointF(w / 2 + 200, cy))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.OR))
        losange(p, w / 2, cy, 8)

        # sous-titre
        f3 = QFont(theme.FAMILLE_TEXTE)
        f3.setPixelSize(21)
        f3.setLetterSpacing(QFont.AbsoluteSpacing, 1.1)
        p.setFont(f3)
        p.setPen(QColor(theme.CREME))
        p.drawText(QRectF(0, 166, w, 36), Qt.AlignHCenter | Qt.AlignVCenter, self.sous)


# ------------------------------------------------------------
# Grosse tuile du menu : degrade, bordure doree, icone, titre, sous-titre
# ------------------------------------------------------------
class BoutonTuile(QWidget):
    clique = Signal()

    def __init__(self, titre, sous_titre, ico, couleur):
        super().__init__()
        self.titre, self.sous = titre, sous_titre
        self.c1, self.c2 = theme.TUILES[couleur]
        self.pix = icones.pixmap(ico, theme.OR_CLAIR, 46)
        self.survol = False
        self.appuye = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(118)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def definir_survol(self, v):
        self.survol = v
        self.update()

    def enterEvent(self, event):
        self.definir_survol(True)

    def leaveEvent(self, event):
        self.definir_survol(False)
        self.appuye = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.appuye = True
            self.update()

    def mouseReleaseEvent(self, event):
        if self.appuye and self.rect().contains(event.position().toPoint()):
            self.appuye = False
            self.update()
            self.clique.emit()
        self.appuye = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(5, 5, -5, -9)
        if self.appuye:
            r.translate(0, 2)

        # ombre
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(r.translated(0, 5), 16, 16)
        # degrade
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0.0, QColor(self.c1))
        g.setColorAt(1.0, QColor(self.c2))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, 16, 16)
        # reflet
        refl = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + r.height() * 0.55))
        refl.setColorAt(0.0, QColor(255, 255, 255, 55))
        refl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(refl))
        p.drawRoundedRect(r, 16, 16)
        if self.survol:
            p.setBrush(QColor(255, 255, 255, 32))
            p.drawRoundedRect(r, 16, 16)
        # bordure doree
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(theme.OR), 3))
        p.drawRoundedRect(r, 16, 16)
        p.setPen(QPen(QColor(233, 196, 106, 110), 1))
        p.drawRoundedRect(r.adjusted(6, 6, -6, -6), 11, 11)
        # petits losanges dores dans les coins
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.OR))
        for (x, y) in ((r.left() + 10, r.top() + 10), (r.right() - 10, r.top() + 10),
                       (r.left() + 10, r.bottom() - 10), (r.right() - 10, r.bottom() - 10)):
            losange(p, x, y, 4)

        # icone
        t = self.pix.deviceIndependentSize()
        p.drawPixmap(QPointF(r.left() + r.width() * 0.17 - t.width() / 2,
                             r.center().y() - t.height() / 2), self.pix)

        # titre + sous-titre
        x = r.left() + r.width() * 0.31
        f1 = QFont(theme.FAMILLE_TEXTE)
        f1.setBold(True)
        f1.setPixelSize(int(min(40, r.height() * 0.30)))
        p.setFont(f1)
        y1 = r.center().y() - 2
        p.setPen(QColor(0, 0, 0, 150))
        p.drawText(QPointF(x + 2, y1 + 2), self.titre)
        p.setPen(QColor(theme.CREME))
        p.drawText(QPointF(x, y1), self.titre)
        f2 = QFont(theme.FAMILLE_TEXTE)
        f2.setPixelSize(14)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 1.1)
        p.setFont(f2)
        p.setPen(QColor(248, 233, 184, 200))
        p.drawText(QPointF(x, y1 + 30), self.sous)


# ------------------------------------------------------------
# Pilule en bas de l'ecran : "NEXT: left click" / "PREVIOUS: right click"
# ------------------------------------------------------------
class Pilule(QWidget):
    COULEURS = {"or": ("#FBEBA6", "#E3B84C", "#8A6420"),
                "rose": ("#F89DB8", "#DE5C84", "#8E3358")}

    def __init__(self, texte, ton="or"):
        super().__init__()
        self.texte = texte
        self.c1, self.c2, self.bord = self.COULEURS[ton]
        self.police = QFont(theme.FAMILLE_TEXTE)
        self.police.setBold(True)
        self.police.setPixelSize(18)
        self.setFixedSize(QFontMetrics(self.police).horizontalAdvance(texte) + 58, 46)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 3, -3, -5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(r.translated(0, 3), r.height() / 2, r.height() / 2)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0.0, QColor(self.c1))
        g.setColorAt(1.0, QColor(self.c2))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(self.bord), 2))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setFont(self.police)
        p.setPen(QColor(theme.ENCRE))
        p.drawText(r, Qt.AlignCenter, self.texte)


# ------------------------------------------------------------
# Zone video (coins arrondis + bordure doree)
# ------------------------------------------------------------
class VideoLabel(QWidget):
    def __init__(self, texte="No image", min_l=520, min_h=320):
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
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        chemin = QPainterPath()
        chemin.addRoundedRect(r, 12, 12)
        p.setClipPath(chemin)
        p.fillRect(self.rect(), QColor("#1C0412"))
        if self.pix is not None:
            cible = self.pix.size().scaled(self.size(), Qt.KeepAspectRatio)
            x = (self.width() - cible.width()) // 2
            y = (self.height() - cible.height()) // 2
            p.drawPixmap(QRect(x, y, cible.width(), cible.height()), self.pix)
        else:
            p.setPen(QColor(248, 233, 184, 150))
            p.setFont(QFont(theme.FAMILLE_TEXTE, 12))
            p.drawText(self.rect(), Qt.AlignCenter, self.texte)
        p.setClipping(False)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(233, 196, 106, 200), 2))
        p.drawRoundedRect(r, 12, 12)


# ------------------------------------------------------------
# Mini tableau : position du pointeur sur le tableau
# ------------------------------------------------------------
class MiniTableau(QWidget):
    def __init__(self):
        super().__init__()
        self.point = None            # (x, y) en unites du tableau
        self.setMinimumHeight(170)

    def definir(self, point):
        self.point = point
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dispo = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        ratio = config.TAB_L / config.TAB_H
        l = dispo.width()
        h = l / ratio
        if h > dispo.height():
            h = dispo.height()
            l = h * ratio
        r = QRectF(dispo.center().x() - l / 2, dispo.center().y() - h / 2, l, h)

        p.setPen(QPen(QColor(theme.OR), 2))
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawRoundedRect(r, 10, 10)
        p.setPen(QPen(QColor(233, 196, 106, 50), 1))
        for i in range(1, 5):
            x = r.left() + r.width() * i / 5
            p.drawLine(QPointF(x, r.top() + 8), QPointF(x, r.bottom() - 8))
        for j in range(1, 3):
            y = r.top() + r.height() * j / 3
            p.drawLine(QPointF(r.left() + 8, y), QPointF(r.right() - 8, y))
        if self.point is None:
            return
        x = r.left() + min(max(self.point[0] / config.TAB_L, 0), 1) * r.width()
        y = r.top() + min(max(self.point[1] / config.TAB_H, 0), 1) * r.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(245, 150, 50, 90))
        p.drawEllipse(QPointF(x, y), 16, 16)
        p.setBrush(QColor("#F2992E"))
        p.drawEllipse(QPointF(x, y), 7, 7)
