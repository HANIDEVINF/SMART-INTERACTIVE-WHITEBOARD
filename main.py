# ============================================================
# main.py : POINT D'ENTREE  ->  python main.py
# Installation : pip install PySide6 opencv-python numpy
# ============================================================
import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from interface.style import feuille_de_style
from interface.app import FenetrePrincipale


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(feuille_de_style())
    fenetre = FenetrePrincipale()
    fenetre.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
