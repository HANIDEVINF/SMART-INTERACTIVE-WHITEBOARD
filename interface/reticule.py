# ============================================================
# reticule.py : la cible qui montre ou pointe la main
# (dessinee par-dessus toute la fenetre, ne bloque pas la souris)
# ============================================================
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget


class Reticule(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.pos_pointeur = None          # QPoint ou None

    def definir(self, pos):
        if pos != self.pos_pointeur:
            self.pos_pointeur = pos
            self.update()

    def paintEvent(self, event):
        if self.pos_pointeur is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.pos_pointeur)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 140, 40, 70))             # halo
        p.drawEllipse(c, 34, 34)
        p.setBrush(QColor(255, 120, 40, 110))
        p.drawEllipse(c, 26, 26)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#F5A33B"), 4))             # anneau
        p.drawEllipse(c, 20, 20)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#D8283F"))                    # coeur rouge
        p.drawEllipse(c, 12, 12)
        p.setBrush(QColor("#FFE9B0"))
        p.drawEllipse(c, 4, 4)
        p.setPen(QPen(QColor("#F5A33B"), 3, Qt.SolidLine, Qt.RoundCap))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):  # petits traits de visee
            p.drawLine(QPointF(c.x() + dx * 26, c.y() + dy * 26),
                       QPointF(c.x() + dx * 40, c.y() + dy * 40))
