# ============================================================
# camera.py : connexion a la camera (telephone Android par WiFi)
# La connexion se fait dans un thread : l'interface ne se bloque pas.
# ============================================================
import os
import threading
import time
import cv2
import config


class Camera:
    def __init__(self):
        self.frame = None
        self.etat = "deconnectee"   # deconnectee / connexion / connectee / echec
        self._id = 0                # numero de la connexion en cours

    def connecter(self, source):
        """Lance la connexion. 'source' = URL du telephone ou '0' (webcam PC)."""
        self.arreter()
        self.etat = "connexion"
        threading.Thread(target=self._travail, args=(source, self._id),
                         daemon=True).start()

    def _travail(self, source, ident):
        if str(source).isdigit():
            source = int(source)
        webcam = isinstance(source, int)          # webcam / camera virtuelle
        if webcam and os.name == "nt":
            cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)   # demarrage rapide sous Windows
        else:
            cap = cv2.VideoCapture(source)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)       # pas de retard : une seule image en attente
        if webcam:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        if ident != self._id or not cap.isOpened():
            cap.release()
            if ident == self._id:
                self.etat = "echec"
            return

        self.etat = "connectee"
        echecs = 0
        while ident == self._id:             # lecture continue
            ok, image = cap.read()
            if ok:
                self.frame = image
                echecs = 0
            else:
                echecs += 1
                if echecs > 100:             # le flux est perdu
                    self.etat = "echec"
                    break
                time.sleep(0.02)
        cap.release()

    def lire(self):
        """Derniere image recue (ou None)."""
        if self.frame is None:
            return None
        return self.frame.copy()

    def arreter(self):
        self._id += 1                        # arrete le thread en cours
        self.frame = None
        self.etat = "deconnectee"

    def est_connectee(self):
        return self.etat == "connectee"


def preparer(frame):
    """Reduit l'image a une largeur fixe (calculs plus rapides)."""
    h, w = frame.shape[:2]
    nouvelle_h = int(h * config.LARGEUR_VIDEO / w)
    return cv2.resize(frame, (config.LARGEUR_VIDEO, nouvelle_h))