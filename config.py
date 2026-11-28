# ============================================================
# config.py : reglages generaux du projet
# ============================================================
import json
import os

DOSSIER = os.path.dirname(os.path.abspath(__file__))
FICHIER_REGLAGES = os.path.join(DOSSIER, "reglages.json")

# Largeur de l'image traitee (la hauteur suit le format de la camera)
LARGEUR_VIDEO = 640

# Taille du tableau dans son propre repere (unites arbitraires)
TAB_L, TAB_H = 1000, 600

# Reglages par defaut (sauvegardes dans reglages.json)
# 16777239 = Page Down ("Next")   -> clic gauche
# 16777238 = Page Up   ("Previous") -> clic droit
REGLAGES_DEFAUT = {
    "ip": "192.168.1.10",
    "port": "8080",
    "webcam": "0",
    "touche_clic_gauche": 16777239,
    "touche_clic_droit": 16777238,
}


def charger_reglages():
    reglages = dict(REGLAGES_DEFAUT)
    try:
        with open(FICHIER_REGLAGES, "r", encoding="utf-8") as f:
            reglages.update(json.load(f))
    except (OSError, ValueError):
        pass
    return reglages


def sauver_reglages(reglages):
    try:
        with open(FICHIER_REGLAGES, "w", encoding="utf-8") as f:
            json.dump(reglages, f, indent=2)
    except OSError:
        pass


def url_camera(ip, port):
    """Adresse du flux video de l'application IP Webcam."""
    return "http://%s:%s/video" % (ip, port)