# ============================================================
# page_connexion.py : connexion de la camera du telephone Android
# ============================================================
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel
import config
from interface.widgets import (Panneau, VideoLabel, entete, etiquette, bouton)

ETAPES = [
    "Install the IP Webcam app on the Android phone.",
    "Connect the phone and the PC to the same WiFi.",
    "In the app, tap Start server.",
    "Enter the address shown, then press Connect.",
]

MESSAGES = {
    "connectee": "Video stream active.",
    "connexion": "Connecting...",
    "echec": "Connection failed. Check the server, the WiFi and the address.",
    "deconnectee": "",
}


def nettoyer_ip(texte):
    """Accepte 'http://192.168.1.15:8080/' ou '192.168.1.15' -> (ip, port)."""
    t = texte.strip().replace("http://", "").replace("https://", "")
    t = t.split("/")[0]
    if ":" in t:
        ip, port = t.split(":", 1)
        return ip, port
    return t, None


class PageConnexion(QWidget):
    parent_page = "reglages"

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.dernier_etat = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        lay.addWidget(entete(app, "Camera", retour="reglages"))

        corps = QHBoxLayout()
        corps.setSpacing(22)
        lay.addLayout(corps, 1)

        # ===== gauche : etapes =====
        guide = Panneau()
        guide.lay.addWidget(etiquette("Phone camera", "h2"))
        guide.lay.addSpacing(4)
        for i, texte in enumerate(ETAPES):
            ligne = QHBoxLayout()
            ligne.setSpacing(14)
            num = QLabel(str(i + 1))
            num.setObjectName("num")
            num.setFixedSize(32, 32)
            num.setAlignment(Qt.AlignCenter)
            ligne.addWidget(num, 0, Qt.AlignTop)
            ligne.addWidget(etiquette(texte, None, wrap=True), 1)
            guide.lay.addLayout(ligne)
            guide.lay.addSpacing(6)
        guide.lay.addStretch()
        corps.addWidget(guide, 4)

        # ===== droite : formulaire + apercu =====
        droite = QVBoxLayout()
        droite.setSpacing(18)
        corps.addLayout(droite, 6)

        form = Panneau()
        champs = QHBoxLayout()
        champs.setSpacing(14)
        col_ip = QVBoxLayout()
        col_ip.setSpacing(4)
        col_ip.addWidget(etiquette("IP address", "muted"))
        self.champ_ip = QLineEdit(app.reglages["ip"])
        self.champ_ip.setPlaceholderText("192.168.1.15")
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

        self.url = etiquette("", "code")
        form.lay.addWidget(self.url)
        self.champ_ip.textChanged.connect(self.maj_url)
        self.champ_port.textChanged.connect(self.maj_url)
        self.maj_url()

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.addWidget(bouton("Connect", "or", self.connecter, ico="plug"))
        btns.addWidget(bouton("Disconnect", "sombre", self.deconnecter, ico="unplug"))
        btns.addStretch()
        form.lay.addLayout(btns)

        # webcam (webcam du PC, ou telephone vu comme webcam avec Iriun / DroidCam)
        cam = QHBoxLayout()
        cam.setSpacing(10)
        cam.addWidget(etiquette("Webcam number", "muted"))
        self.champ_cam = QLineEdit(str(app.reglages.get("webcam", "0")))
        self.champ_cam.setFixedWidth(70)
        cam.addWidget(self.champ_cam)
        cam.addWidget(bouton("Use webcam", "bleu", self.webcam_pc, ico="monitor"))
        cam.addStretch()
        form.lay.addLayout(cam)
        self.message = etiquette("", "muted", wrap=True)
        form.lay.addWidget(self.message)
        droite.addWidget(form)

        self.video = VideoLabel("Preview", 360, 220)
        droite.addWidget(self.video, 1)

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
            self.message.setText("Missing IP address.")
            return
        self.app.reglages["ip"] = ip
        self.app.reglages["port"] = port
        config.sauver_reglages(self.app.reglages)
        self.app.camera.connecter(config.url_camera(ip, port))

    def webcam_pc(self):
        numero = self.champ_cam.text().strip() or "0"
        if not numero.isdigit():
            self.message.setText("Webcam number must be 0, 1, 2...")
            return
        self.app.reglages["webcam"] = numero
        config.sauver_reglages(self.app.reglages)
        self.app.camera.connecter(numero)

    def deconnecter(self):
        self.app.camera.arreter()

    # ---------------- appelee par la boucle principale ----------------
    def maj(self):
        etat = self.app.camera.etat
        if etat != self.dernier_etat:
            self.dernier_etat = etat
            self.message.setText(MESSAGES[etat])
        self.video.afficher_frame(self.app.suiveur.image)