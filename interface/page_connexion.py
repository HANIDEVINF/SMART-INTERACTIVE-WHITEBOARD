# ============================================================
# page_connexion.py : connexion de la camera du telephone Android
# (guide pas a pas + formulaire + apercu video)
# ============================================================
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QLabel, QFrame, QScrollArea)
import config
from camera import preparer
from interface.widgets import (Carte, Puce, VideoLabel, entete, etiquette,
                               bouton)

ETAPES = [
    ("Installe l'application « IP Webcam »",
     "Sur le téléphone Android, ouvre le Play Store et installe IP Webcam "
     "(gratuite)."),
    ("Mets le téléphone et le PC sur le même WiFi",
     "Pas de WiFi commun ? Active le partage de connexion du téléphone et "
     "connecte le PC dessus."),
    ("Démarre le serveur sur le téléphone",
     "Dans IP Webcam, descends tout en bas et appuie sur « Démarrer le "
     "serveur ». Une adresse s'affiche, par exemple 192.168.1.15:8080."),
    ("Saisis l'adresse ici et clique sur Connecter",
     "Recopie l'IP (192.168.1.15) et le port (8080) dans le formulaire."),
]


def nettoyer_ip(texte):
    """Accepte 'http://192.168.1.15:8080/' ou '192.168.1.15' -> (ip, port)."""
    t = texte.strip().replace("http://", "").replace("https://", "")
    t = t.split("/")[0]
    if ":" in t:
        ip, port = t.split(":", 1)
        return ip, port
    return t, None


class PageConnexion(QWidget):
    def __init__(self, app):
        super().__init__()
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.app = app

        externe = QVBoxLayout(self)
        externe.setContentsMargins(0, 0, 0, 0)
        defil = QScrollArea()
        defil.setWidgetResizable(True)
        externe.addWidget(defil)
        contenu = QWidget()
        defil.setWidget(contenu)
        lay = QVBoxLayout(contenu)
        lay.setContentsMargins(36, 32, 36, 32)
        lay.setSpacing(22)

        self.puce = Puce("●  Non connectée", "off")
        lay.addWidget(entete("Caméra du téléphone",
                             "Utilise ton téléphone Android comme caméra, par WiFi.",
                             self.puce))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ===== colonne gauche : guide =====
        guide = Carte()
        guide.lay.addWidget(etiquette("Comment faire ?  4 étapes simples", "h2"))
        guide.lay.addSpacing(4)
        for i, (titre, desc) in enumerate(ETAPES):
            ligne = QHBoxLayout()
            ligne.setSpacing(14)
            num = QLabel(str(i + 1))
            num.setObjectName("num")
            num.setFixedSize(34, 34)
            num.setAlignment(Qt.AlignCenter)
            texte = QVBoxLayout()
            texte.setSpacing(2)
            texte.addWidget(etiquette(titre, "carte_titre", wrap=True))
            texte.addWidget(etiquette(desc, "muted", wrap=True))
            ligne.addWidget(num, 0, Qt.AlignTop)
            ligne.addLayout(texte, 1)
            guide.lay.addLayout(ligne)
            guide.lay.addSpacing(6)

        astuce = QFrame()
        astuce.setObjectName("astuce")
        astuce.setStyleSheet("QFrame#astuce { background: #FFF2C4; "
                             "border-radius: 14px; } "
                             "QFrame#astuce QLabel { background: transparent; }")
        al = QVBoxLayout(astuce)
        al.setContentsMargins(16, 12, 16, 12)
        al.addWidget(etiquette(
            "💡  Astuce : tape l'adresse du téléphone dans le navigateur du PC. "
            "Si la page d'IP Webcam s'ouvre, la connexion est bonne.",
            None, wrap=True))
        guide.lay.addWidget(astuce)
        guide.lay.addStretch()
        corps.addWidget(guide, 5)

        # ===== colonne droite : formulaire + apercu =====
        droite = QVBoxLayout()
        droite.setSpacing(22)
        corps.addLayout(droite, 6)

        form = Carte()
        form.lay.addWidget(etiquette("Connexion", "h2"))
        champs = QHBoxLayout()
        champs.setSpacing(14)
        col_ip = QVBoxLayout()
        col_ip.setSpacing(4)
        col_ip.addWidget(etiquette("Adresse IP du téléphone", "muted"))
        self.champ_ip = QLineEdit(app.reglages["ip"])
        self.champ_ip.setPlaceholderText("ex : 192.168.1.15")
        col_ip.addWidget(self.champ_ip)
        col_port = QVBoxLayout()
        col_port.setSpacing(4)
        col_port.addWidget(etiquette("Port", "muted"))
        self.champ_port = QLineEdit(app.reglages["port"])
        self.champ_port.setFixedWidth(110)
        col_port.addWidget(self.champ_port)
        champs.addLayout(col_ip, 1)
        champs.addLayout(col_port)
        form.lay.addLayout(champs)

        form.lay.addWidget(etiquette("Adresse du flux vidéo", "muted"))
        self.url = etiquette("", "code")
        form.lay.addWidget(self.url)
        self.champ_ip.textChanged.connect(self.maj_url)
        self.champ_port.textChanged.connect(self.maj_url)
        self.maj_url()

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addWidget(bouton("📱   Connecter", "primaire", self.connecter))
        btns.addWidget(bouton("💻   Webcam du PC", "blue", self.webcam_pc))
        btns.addWidget(bouton("Déconnecter", "blanc", self.deconnecter))
        btns.addStretch()
        form.lay.addLayout(btns)
        self.message = etiquette("", "muted", wrap=True)
        form.lay.addWidget(self.message)
        droite.addWidget(form)

        apercu = Carte(avec_ombre=False)
        apercu.lay.setContentsMargins(14, 14, 14, 14)
        self.video = VideoLabel("Aperçu de la caméra", 360, 230)
        apercu.lay.addWidget(self.video)
        droite.addWidget(apercu, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.boucle)

    # ---------------- actions ----------------
    def adresse(self):
        ip, port_saisi = nettoyer_ip(self.champ_ip.text())
        port = port_saisi or self.champ_port.text().strip() or "8080"
        return ip, port

    def maj_url(self):
        ip, port = self.adresse()
        self.url.setText(config.url_camera(ip or "...", port))

    def connecter(self):
        ip, port = self.adresse()
        if not ip:
            self.message.setText("Saisis d'abord l'adresse IP du téléphone.")
            return
        self.app.reglages["ip"] = ip
        self.app.reglages["port"] = port
        config.sauver_reglages(self.app.reglages)
        self.message.setText("Connexion à %s ..." % config.url_camera(ip, port))
        self.app.camera.connecter(config.url_camera(ip, port))

    def webcam_pc(self):
        self.message.setText("Connexion à la webcam du PC ...")
        self.app.camera.connecter("0")

    def deconnecter(self):
        self.app.camera.arreter()
        self.message.setText("")

    # ---------------- boucle d'affichage ----------------
    def showEvent(self, event):
        self.timer.start(40)

    def hideEvent(self, event):
        self.timer.stop()

    def boucle(self):
        cam = self.app.camera
        if cam.etat == "connectee":
            self.puce.definir("●  Connectée", "ok")
            self.message.setText("✔ Le flux vidéo arrive. Tu peux passer à la "
                                 "calibration.")
        elif cam.etat == "connexion":
            self.puce.definir("●  Connexion en cours...", "warn")
        elif cam.etat == "echec":
            self.puce.definir("●  Échec", "warn")
            self.message.setText(
                "✖ Connexion impossible. Vérifie : 1) le serveur est démarré "
                "sur le téléphone, 2) téléphone et PC sont sur le même WiFi, "
                "3) l'adresse IP et le port sont corrects.")
        else:
            self.puce.definir("●  Non connectée", "off")

        frame = cam.lire()
        self.video.afficher_frame(preparer(frame) if frame is not None else None)
