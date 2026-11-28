# ============================================================
# page_telecommande.py : identifier les 2 boutons de la telecommande
# (une telecommande de presentation envoie des touches clavier)
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget
from interface.widgets import Panneau, Puce, entete, etiquette, bouton


def nom_touche(touche, texte=""):
    nom = QKeySequence(touche).toString()
    return nom if nom else (texte or "?")


class PageTelecommande(QWidget):
    parent_page = "reglages"

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.apprentissage = None      # None / "gauche" / "droit"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        lay.addWidget(entete(app, "Remote", retour="reglages"))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ----- gauche : derniere touche -----
        gauche = Panneau()
        gauche.lay.addWidget(etiquette("Last key", "h2"))
        self.l_touche = etiquette("-", "gros")
        gauche.lay.addWidget(self.l_touche)
        self.l_code = etiquette("Qt code : -\nScan code : -\nVirtual code : -", "code")
        gauche.lay.addWidget(self.l_code)
        self.puce_action = Puce("Waiting", "off")
        gauche.lay.addWidget(self.puce_action)
        self.liste = QListWidget()
        gauche.lay.addWidget(self.liste, 1)
        corps.addWidget(gauche, 1)

        # ----- droite : association des boutons -----
        droite = Panneau()
        droite.lay.addWidget(etiquette("Buttons", "h2"))
        droite.lay.addSpacing(6)
        self.puce_g = Puce("", "info")
        self.puce_d = Puce("", "info")
        self.btn_g = bouton("Learn", "or", lambda: self.apprendre("gauche"))
        self.btn_d = bouton("Learn", "rose", lambda: self.apprendre("droit"))
        for titre, puce, btn in (("NEXT  =  left click", self.puce_g, self.btn_g),
                                 ("PREVIOUS  =  right click", self.puce_d, self.btn_d)):
            droite.lay.addWidget(etiquette(titre, None))
            ligne = QHBoxLayout()
            ligne.addWidget(puce)
            ligne.addStretch()
            ligne.addWidget(btn)
            droite.lay.addLayout(ligne)
            droite.lay.addSpacing(12)
        droite.lay.addWidget(bouton("Default keys", "sombre", self.par_defaut, ico="rotate-ccw"))
        droite.lay.addStretch()
        corps.addWidget(droite, 1)
        self.maj_association()

    def maj_association(self):
        tel = self.app.telecommande
        self.puce_g.definir("Key : " + nom_touche(tel.touche("gauche")), "info")
        self.puce_d.definir("Key : " + nom_touche(tel.touche("droit")), "info")
        self.btn_g.setText("Press the button" if self.apprentissage == "gauche" else "Learn")
        self.btn_d.setText("Press the button" if self.apprentissage == "droit" else "Learn")

    def apprendre(self, cote):
        self.apprentissage = cote
        self.maj_association()

    def par_defaut(self):
        self.app.telecommande.par_defaut()
        self.maj_association()

    def recevoir(self, event):
        """Appelee par la fenetre principale a chaque touche (toujours utilisee ici)."""
        touche = event.key()
        nom = nom_touche(touche, event.text())
        self.l_touche.setText(nom)
        self.l_code.setText("Qt code : 0x%X\nScan code : %d\nVirtual code : %d"
                            % (touche, event.nativeScanCode(),
                               event.nativeVirtualKey()))
        tel = self.app.telecommande

        if self.apprentissage is not None:            # mode apprentissage
            tel.apprendre(self.apprentissage, touche)
            self.puce_action.definir("Key saved", "ok")
            self.apprentissage = None
            self.maj_association()
            return True

        action = tel.action(touche)
        if action == "gauche":
            self.puce_action.definir("Left click", "ok")
            texte = "left click"
        elif action == "droit":
            self.puce_action.definir("Right click", "ok")
            texte = "right click"
        else:
            self.puce_action.definir("Not assigned", "warn")
            texte = "not assigned"
        self.liste.insertItem(0, "%s   -   %s" % (nom, texte))
        while self.liste.count() > 8:
            self.liste.takeItem(self.liste.count() - 1)
        return True
