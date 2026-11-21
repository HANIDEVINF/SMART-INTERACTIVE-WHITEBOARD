# ============================================================
# style.py : palette pastel + feuille de style (QSS) de toute l'application
# ============================================================

C = {
    "fond": "#F5F3FB",
    "blanc": "#FFFFFF",
    "texte": "#3B3355",
    "gris": "#8D86A6",
    "ligne": "#ECE7F6",
    "primaire": "#8F7CE0",
    "primaire_fonce": "#7C68D6",
    "primaire_clair": "#E8E1FC",
}

# ton -> (couleur pastel de fond, couleur d'accent)
TONS = {
    "mint": ("#D6F3E4", "#7ED0A5"),
    "pink": ("#FFDCE8", "#F59BBB"),
    "blue": ("#D5E8FF", "#86B8F0"),
    "lavender": ("#E6DDFB", "#A895E8"),
    "yellow": ("#FFF2C4", "#EBCB65"),
    "peach": ("#FFE0CC", "#F2A877"),
}

POLICE = '"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif'


def feuille_de_style():
    qss = """
    * { font-family: %(police)s; color: %(texte)s; }
    QWidget#fond, QWidget#page { background: %(fond)s; }
    QToolTip { background: white; border: 1px solid %(ligne)s; padding: 6px; }

    /* ---------- barre laterale ---------- */
    QFrame#sidebar { background: white; border-right: 1px solid %(ligne)s; }
    QLabel#logo { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                  stop:0 #B8A7F2, stop:1 #F6A9C8); border-radius: 14px;
                  font-size: 22px; }
    QLabel#logo_titre { font-size: 17px; font-weight: 800; }
    QLabel#section { color: %(gris)s; font-size: 11px; font-weight: 700;
                     letter-spacing: 1px; padding-left: 16px; }
    QPushButton#nav { text-align: left; padding: 11px 16px; border: none;
                      border-radius: 13px; background: transparent;
                      color: %(gris)s; font-size: 14px; font-weight: 600; }
    QPushButton#nav:hover { background: #F3EFFC; color: %(texte)s; }
    QPushButton#nav:checked { background: %(primaire_clair)s; color: #5B45C4;
                              font-weight: 700; }
    QFrame#statut_camera { background: #F7F5FD; border-radius: 16px; }

    /* ---------- cartes ---------- */
    QFrame#card { background: white; border-radius: 22px;
                  border: 1px solid %(ligne)s; }
    QFrame#card_plat { background: white; border-radius: 22px;
                       border: 1px solid %(ligne)s; }

    /* ---------- textes ---------- */
    QLabel#titre_page { font-size: 28px; font-weight: 800; }
    QLabel#sous_titre { color: %(gris)s; font-size: 14px; }
    QLabel#h2 { font-size: 17px; font-weight: 700; }
    QLabel#muted { color: %(gris)s; font-size: 13px; }
    QLabel#carte_titre { font-size: 16px; font-weight: 700; }
    QLabel#hero_titre { font-size: 34px; font-weight: 800; }
    QLabel#hero_texte { font-size: 15px; color: #5E5578; }
    QLabel#gros { font-size: 44px; font-weight: 800; }
    QLabel#code { background: #F7F5FD; border-radius: 10px; padding: 9px 12px;
                  font-family: Consolas, "DejaVu Sans Mono", monospace;
                  font-size: 13px; color: #5B45C4; }
    QLabel#num { background: %(primaire_clair)s; color: #5B45C4;
                 border-radius: 17px; font-weight: 800; font-size: 15px; }

    /* ---------- puces d'etat ---------- */
    QLabel#puce { border-radius: 13px; padding: 5px 13px; font-size: 12px;
                  font-weight: 700; }
    QLabel#puce[etat="ok"]   { background: #D6F3E4; color: #2F8A5B; }
    QLabel#puce[etat="off"]  { background: #EEEAF6; color: %(gris)s; }
    QLabel#puce[etat="warn"] { background: #FFE0CC; color: #B5622A; }
    QLabel#puce[etat="info"] { background: #D5E8FF; color: #3A74B8; }

    /* ---------- boutons ---------- */
    QPushButton[variante] { border: none; border-radius: 14px;
                            padding: 12px 22px; font-size: 14px;
                            font-weight: 700; }
    QPushButton[variante="primaire"] { background: %(primaire)s; color: white; }
    QPushButton[variante="primaire"]:hover { background: %(primaire_fonce)s; }
    QPushButton[variante="blanc"] { background: white; color: %(texte)s;
                                    border: 2px solid %(ligne)s; }
    QPushButton[variante="blanc"]:hover { border: 2px solid %(primaire)s; }
    QPushButton[variante]:disabled { background: #EEEAF6; color: #B7B0CC; }
    QPushButton[variante]:checked { border: 2px solid %(primaire)s; }

    /* ---------- champs ---------- */
    QLineEdit { background: #F7F5FD; border: 2px solid %(ligne)s;
                border-radius: 12px; padding: 10px 14px; font-size: 15px; }
    QLineEdit:focus { border: 2px solid %(primaire)s; background: white; }

    QSlider::groove:horizontal { height: 8px; background: %(ligne)s;
                                 border-radius: 4px; }
    QSlider::sub-page:horizontal { background: #B8A7F2; border-radius: 4px; }
    QSlider::handle:horizontal { background: white; border: 3px solid %(primaire)s;
                                 width: 16px; height: 16px; margin: -8px 0;
                                 border-radius: 11px; }

    QScrollArea { border: none; background: transparent; }
    QScrollArea > QWidget > QWidget { background: transparent; }
    QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
    QScrollBar::handle:vertical { background: #D8D0EE; border-radius: 4px;
                                  min-height: 30px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
    QScrollBar::handle:horizontal { background: #D8D0EE; border-radius: 4px;
                                    min-width: 30px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

    QListWidget { background: transparent; border: none; outline: none; }
    QListWidget::item { background: #F7F5FD; border-radius: 10px;
                        padding: 9px 12px; margin: 3px 0; }

    /* ---------- cartes de l'accueil ---------- */
    QFrame#homecard { background: white; border-radius: 22px;
                      border: 2px solid transparent; }
    """ % dict(C, police=POLICE)

    # Variantes pastel des boutons + cartes d'accueil, une par ton
    for nom, (bg, accent) in TONS.items():
        qss += """
        QPushButton[variante="%(n)s"] { background: %(bg)s; color: %(t)s; }
        QPushButton[variante="%(n)s"]:hover { background: %(ac)s; color: white; }
        QFrame#homecard[ton="%(n)s"]:hover { border: 2px solid %(ac)s; }
        QLabel#badge[ton="%(n)s"] { background: %(bg)s; border-radius: 20px;
                                    font-size: 28px; }
        """ % dict(n=nom, bg=bg, ac=accent, t=C["texte"])
    return qss
