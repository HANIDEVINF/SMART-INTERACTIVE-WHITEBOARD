# ============================================================
# page_telecommande.py : detection des touches de la telecommande
# Les telecommandes de presentation envoient des touches clavier
# (souvent Page Up / Page Down). Cette page les identifie.
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget
import config
from interface.widgets import Carte, Puce, entete, etiquette, bouton


def nom_touche(touche, texte=""):
    nom = QKeySequence(touche).toString()
    return nom if nom else (texte or "?")


class PageTelecommande(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app
        self.apprentissage = None      # None / "gauche" / "droite"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(22)
        lay.addWidget(entete("Télécommande",
                             "Appuie sur un bouton de la télécommande pour voir son code."))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ----- gauche : derniere touche -----
        gauche = Carte()
        gauche.lay.addWidget(etiquette("DERNIÈRE TOUCHE DÉTECTÉE", "muted"))
        self.l_touche = etiquette("—", "gros")
        gauche.lay.addWidget(self.l_touche)
        self.l_code = etiquette("Code Qt : —\nScan code : —\nCode virtuel : —", "code")
        gauche.lay.addWidget(self.l_code)
        self.puce_action = Puce("En attente...", "off")
        gauche.lay.addWidget(self.puce_action)
        gauche.lay.addSpacing(8)
        gauche.lay.addWidget(etiquette("Historique", "h2"))
        self.liste = QListWidget()
        gauche.lay.addWidget(self.liste, 1)
        corps.addWidget(gauche, 1)

        # ----- droite : association des boutons -----
        droite = Carte()
        droite.lay.addWidget(etiquette("Association des boutons", "h2"))
        droite.lay.addWidget(etiquette(
            "Clique sur « Apprendre », puis appuie sur le bouton voulu de la "
            "télécommande.", "muted", wrap=True))
        droite.lay.addSpacing(6)

        self.puce_g = Puce("", "info")
        self.puce_d = Puce("", "info")
        self.btn_g = bouton("Apprendre", "mint", lambda: self.apprendre("gauche"))
        self.btn_d = bouton("Apprendre", "pink", lambda: self.apprendre("droite"))
        for titre, puce, btn in (("Bouton PRÉCÉDENT  →  clic gauche", self.puce_g, self.btn_g),
                                 ("Bouton SUIVANT  →  clic droit", self.puce_d, self.btn_d)):
            droite.lay.addWidget(etiquette(titre, "carte_titre"))
            ligne = QHBoxLayout()
            ligne.addWidget(puce)
            ligne.addStretch()
            ligne.addWidget(btn)
            droite.lay.addLayout(ligne)
            droite.lay.addSpacing(10)
        droite.lay.addStretch()
        corps.addWidget(droite, 1)
        self.maj_association()

    def maj_association(self):
        r = self.app.reglages
        self.puce_g.definir("Touche : " + nom_touche(r["touche_gauche"]), "info")
        self.puce_d.definir("Touche : " + nom_touche(r["touche_droite"]), "info")
        self.btn_g.setText("Appuie sur le bouton..." if self.apprentissage == "gauche" else "Apprendre")
        self.btn_d.setText("Appuie sur le bouton..." if self.apprentissage == "droite" else "Apprendre")

    def apprendre(self, cote):
        self.apprentissage = cote
        self.maj_association()

    def recevoir(self, event):
        """Appelee par la fenetre principale a chaque touche."""
        touche = event.key()
        nom = nom_touche(touche, event.text())
        self.l_touche.setText(nom)
        self.l_code.setText("Code Qt : 0x%X\nScan code : %d\nCode virtuel : %d"
                            % (touche, event.nativeScanCode(),
                               event.nativeVirtualKey()))
        r = self.app.reglages

        if self.apprentissage is not None:            # mode apprentissage
            r["touche_" + self.apprentissage] = touche
            config.sauver_reglages(r)
            self.puce_action.definir("Touche enregistrée ✔", "ok")
            self.apprentissage = None
            self.maj_association()
            return

        if touche == r["touche_gauche"]:
            self.puce_action.definir("➜ Clic GAUCHE", "ok")
            action = "clic gauche"
        elif touche == r["touche_droite"]:
            self.puce_action.definir("➜ Clic DROIT", "ok")
            action = "clic droit"
        else:
            self.puce_action.definir("Touche non associée", "warn")
            action = "non associée"
        self.liste.insertItem(0, "%s     →     %s" % (nom, action))
        while self.liste.count() > 8:
            self.liste.takeItem(self.liste.count() - 1)
