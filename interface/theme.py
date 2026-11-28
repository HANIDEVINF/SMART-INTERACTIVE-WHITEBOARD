# ============================================================
# theme.py : couleurs, polices et feuille de style (QSS)
# Theme "Smart Whiteboard" : bordeaux, or et creme
# ============================================================
import os
from PySide6.QtGui import QFontDatabase
import config

OR = "#E9C46A"
OR_CLAIR = "#F6D587"
CREME = "#F8E9B8"
VIN = "#5B1035"
VIN_FONCE = "#34091E"
ENCRE = "#3A0D20"          # texte fonce sur boutons dores

# couleur de tuile -> (haut du degrade, bas du degrade)
TUILES = {
    "rouge": ("#EC3B57", "#A91A3A"),
    "violet": ("#8333A0", "#54206A"),
    "bleu": ("#21809F", "#10495F"),
    "orange": ("#D4741F", "#9C470D"),
}

FAMILLE_TITRE = "Lobster"
FAMILLE_TEXTE = "Arvo"


def charger_polices():
    """Charge les polices du dossier assets/fonts (si elles manquent : polices Windows)."""
    global FAMILLE_TITRE, FAMILLE_TEXTE
    dossier = os.path.join(config.DOSSIER, "assets", "fonts")
    familles = set()
    if os.path.isdir(dossier):
        for nom in sorted(os.listdir(dossier)):
            if nom.lower().endswith((".ttf", ".otf")):
                ident = QFontDatabase.addApplicationFont(os.path.join(dossier, nom))
                if ident >= 0:
                    familles.update(QFontDatabase.applicationFontFamilies(ident))
    if "Lobster" not in familles:
        FAMILLE_TITRE = "Segoe Script"
    if "Arvo" not in familles:
        FAMILLE_TEXTE = "Georgia"


def eclaircir(couleur, f=0.18):
    """Melange une couleur #RRGGBB avec du blanc."""
    r, g, b = (int(couleur[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = (int(c + (255 - c) * f) for c in (r, g, b))
    return "#%02X%02X%02X" % (r, g, b)


def degrade(c1, c2):
    return ("qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 %s, stop:1 %s)"
            % (c1, c2))


def feuille_de_style():
    d = dict(texte=FAMILLE_TEXTE, titre=FAMILLE_TITRE, creme=CREME, or_=OR,
             or_clair=OR_CLAIR, encre=ENCRE)
    qss = """
    * { font-family: "%(texte)s", Georgia, serif; color: %(creme)s;
        font-size: 15px; }
    QToolTip { background: #34091E; color: %(creme)s; border: 1px solid %(or_)s;
               padding: 6px; }

    /* ---------- textes ---------- */
    QLabel#titre_page { font-family: "%(titre)s", "Segoe Script", cursive;
                        font-size: 46px; color: %(or_clair)s; }
    QLabel#h2 { font-size: 20px; font-weight: bold; color: %(or_)s; }
    QLabel#muted { color: rgba(248, 233, 184, 170); font-size: 14px; }
    QLabel#gros { font-family: "%(titre)s", "Segoe Script", cursive;
                  font-size: 64px; color: %(or_clair)s; }
    QLabel#code { background: rgba(0, 0, 0, 90);
                  border: 1px solid rgba(233, 196, 106, 110);
                  border-radius: 10px; padding: 9px 12px;
                  font-family: Consolas, "DejaVu Sans Mono", monospace;
                  font-size: 14px; color: %(creme)s; }
    QLabel#num { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                 stop:0 #FBEBA6, stop:1 #E3B84C); color: %(encre)s;
                 border-radius: 16px; font-weight: bold; font-size: 16px; }

    /* ---------- puces d'etat ---------- */
    QLabel#puce { border-radius: 13px; padding: 5px 14px; font-size: 13px;
                  font-weight: bold; border: 1px solid rgba(233, 196, 106, 120); }
    QLabel#puce[etat="ok"]   { background: #2D6A4B; color: #E2F6E9; }
    QLabel#puce[etat="off"]  { background: rgba(0, 0, 0, 100); color: rgba(248, 233, 184, 190); }
    QLabel#puce[etat="warn"] { background: #8A4B12; color: #FFE6BC; }
    QLabel#puce[etat="info"] { background: #1D5A74; color: #D8F0FA; }

    /* ---------- panneaux ---------- */
    QFrame#panneau { background: rgba(28, 4, 17, 150);
                     border: 2px solid %(or_)s; border-radius: 16px; }
    QFrame#panneau QLabel { background: transparent; }
    QFrame#filet { background: rgba(233, 196, 106, 120); max-height: 2px; }

    /* ---------- boutons ---------- */
    QPushButton[variante] { border-radius: 16px; padding: 11px 22px;
                            font-size: 15px; font-weight: bold;
                            border: 2px solid %(or_)s; }
    QPushButton[variante]:disabled { background: #4A2A3A; color: #8A6F7A;
                                     border: 2px solid #6A4A5A; }
    QPushButton[variante]:checked { border: 3px solid #FFF4C4; }
    QPushButton[variante="sombre"] { background: rgba(0, 0, 0, 90); color: %(creme)s; }
    QPushButton[variante="sombre"]:hover { background: rgba(233, 196, 106, 55); }
    QPushButton[variante="or"] { background: %(g_or)s; color: %(encre)s;
                                 border: 2px solid #9C7424; }
    QPushButton[variante="or"]:hover { background: %(g_or_h)s; }
    QPushButton[variante="rose"] { background: %(g_rose)s; color: %(encre)s;
                                   border: 2px solid #8E3358; }
    QPushButton[variante="rose"]:hover { background: %(g_rose_h)s; }
    """ % dict(d, g_or=degrade("#FBEBA6", "#E3B84C"),
               g_or_h=degrade("#FFF3BE", "#EEC85E"),
               g_rose=degrade("#F89DB8", "#DE5C84"),
               g_rose_h=degrade("#FFB3C9", "#EC7396"))

    for nom, (c1, c2) in TUILES.items():
        qss += """
        QPushButton[variante="%s"] { background: %s; color: %s; }
        QPushButton[variante="%s"]:hover { background: %s; }
        """ % (nom, degrade(c1, c2), CREME, nom,
               degrade(eclaircir(c1), eclaircir(c2)))

    qss += """
    /* ---------- champs ---------- */
    QLineEdit { background: rgba(0, 0, 0, 100);
                border: 2px solid rgba(233, 196, 106, 150);
                border-radius: 12px; padding: 10px 14px; font-size: 16px;
                color: %(creme)s; selection-background-color: #B8892E; }
    QLineEdit:focus { border: 2px solid %(or_)s; }

    QSlider::groove:horizontal { height: 8px; background: rgba(0, 0, 0, 120);
                                 border: 1px solid rgba(233, 196, 106, 120);
                                 border-radius: 4px; }
    QSlider::sub-page:horizontal { background: %(or_)s; border-radius: 4px; }
    QSlider::handle:horizontal { background: %(creme)s; border: 3px solid #B58A2A;
                                 width: 14px; height: 14px; margin: -8px 0;
                                 border-radius: 10px; }

    /* ---------- listes et defilement ---------- */
    QListWidget { background: transparent; border: none; outline: none; }
    QListWidget::item { background: rgba(0, 0, 0, 80); border-radius: 8px;
                        padding: 8px 12px; margin: 3px 0; color: %(creme)s; }
    QScrollArea { border: none; background: transparent; }
    QScrollArea > QWidget > QWidget { background: transparent; }
    QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
    QScrollBar::handle:vertical { background: rgba(233, 196, 106, 150);
                                  border-radius: 4px; min-height: 30px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
    QScrollBar::handle:horizontal { background: rgba(233, 196, 106, 150);
                                    border-radius: 4px; min-width: 30px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    """ % d
    return qss
