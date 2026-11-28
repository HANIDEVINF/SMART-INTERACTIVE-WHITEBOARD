# ============================================================
# main.py : POINT D'ENTREE  ->  python main.py
# Installation : pip install -r requirements.txt
# ============================================================
import sys
from PySide6.QtWidgets import QApplication
from interface import theme
from interface.app import FenetrePrincipale


def main():
    app = QApplication(sys.argv)
    theme.charger_polices()                 # polices du dossier assets/fonts
    app.setStyleSheet(theme.feuille_de_style())
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
