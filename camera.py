"""camera.py - Acquisition video (OpenCV est autorise pour la capture)."""
import cv2


class Camera:
    def __init__(self, index, width, height):
        self.cap = cv2.VideoCapture(index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not self.cap.isOpened():
            raise RuntimeError(f"Impossible d'ouvrir la camera {index}")

    def read(self):
        """Retourne une image BGR (H,W,3) uint8, ou None si echec."""
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self):
        self.cap.release()