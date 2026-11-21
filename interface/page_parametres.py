# ============================================================
# page_parametres.py : reglages et reinitialisation
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
import config
from interface.widgets import Carte, Puce, entete, etiquette, bouton


class PageParametres(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(22)
        lay.addWidget(entete("Paramètres", "Réglages de l'application et réinitialisation."))

        ligne = QHBoxLayout()
        ligne.setSpacing(22)
        lay.addLayout(ligne)

        # ----- calibrage -----
        c1 = Carte()
        c1.lay.addWidget(etiquette("📐  Calibrage", "h2"))
        c1.lay.addWidget(etiquette("Efface le calibrage du tableau pour recommencer.",
                                   "muted", wrap=True))
        self.puce_cal = Puce("", "off")
        c1.lay.addWidget(self.puce_cal)
        c1.lay.addWidget(bouton("Réinitialiser le calibrage", "pink", self.reset_cal))
        c1.lay.addStretch()
        ligne.addWidget(c1, 1)

        # ----- telecommande -----
        c2 = Carte()
        c2.lay.addWidget(etiquette("🎮  Télécommande", "h2"))
        c2.lay.addWidget(etiquette("Remet les touches Page Up (clic gauche) et "
                                   "Page Down (clic droit).", "muted", wrap=True))
        c2.lay.addWidget(bouton("Touches par défaut", "blue", self.reset_touches))
        c2.lay.addStretch()
        ligne.addWidget(c2, 1)

        # ----- a propos -----
        c3 = Carte()
        c3.lay.addWidget(etiquette("ℹ️  À propos", "h2"))
        c3.lay.addWidget(etiquette("Smart Interactive Whiteboard\nProjet Vision 2026 · 2027\n"
                                   "USTHB · Master SII", "muted", wrap=True))
        c3.lay.addStretch()
        ligne.addWidget(c3, 1)
        lay.addStretch()

    def showEvent(self, event):
        if self.app.M is not None:
            self.puce_cal.definir("✔ Tableau calibré", "ok")
        else:
            self.puce_cal.definir("Non calibré", "off")

    def reset_cal(self):
        self.app.coins_valides = None
        self.app.M = None
        self.app.pointeur = None
        self.puce_cal.definir("Non calibré", "off")

    def reset_touches(self):
        self.app.reglages["touche_gauche"] = config.REGLAGES_DEFAUT["touche_gauche"]
        self.app.reglages["touche_droite"] = config.REGLAGES_DEFAUT["touche_droite"]
        config.sauver_reglages(self.app.reglages)
        self.app.pages["telecommande"].maj_association()
