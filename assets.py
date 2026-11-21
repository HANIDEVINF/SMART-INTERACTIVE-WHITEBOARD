"""assets.py - Images a afficher (dossier images/ ou images de demo) et contenu du cours."""
import os
import cv2
import numpy as np
import config as C
from ui import stamp_disc, FONT


def make_demo_images():
    h, w = 600, 900
    y, x = np.mgrid[0:h, 0:w]
    a = np.zeros((h, w, 3), np.uint8)
    a[..., 0], a[..., 1], a[..., 2] = x * 255 // w, y * 255 // h, 160
    for k in range(6):
        stamp_disc(a, 150 + k * 120, 330, 30 + k * 8, (255, 255, 255))
    cv2.putText(a, "Demo gradient", (40, 90), FONT, 2, (255, 255, 255), 4)
    b = (((x // 20 + y // 20) % 2) * 200 + 30).astype(np.uint8)
    b = np.dstack([b, b, b])
    cv2.putText(b, "Zoom: 20 px squares", (40, 90), FONT, 1.6, (0, 140, 255), 4)
    return [("Demo gradient", a), ("Demo checkerboard", b)]


def load_images():
    out = []
    if os.path.isdir(C.IMAGES_DIR):
        for f in sorted(os.listdir(C.IMAGES_DIR)):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                im = cv2.imread(os.path.join(C.IMAGES_DIR, f))
                if im is not None:
                    out.append((os.path.splitext(f)[0][:30], im))
    return out or make_demo_images()


SLIDES = [
    {"title": "Computer vision for teaching",
     "lines": ["A fixed camera watches the board",
               "A coloured marker gives the pointer position",
               "A homography converts pixels to board coordinates",
               "A 2-button remote gives left / right clicks"]},
    {"title": "Step 1 - Segment the marker",
     "lines": ["BGR -> HSV (hue is robust to lighting)",
               "Threshold on hue, saturation, value",
               "Opening = erosion then dilation (3x3)",
               "Centroid of remaining pixels = pointer"]},
    {"title": "Step 2 - Image to board (homography)",
     "lines": ["4 image corners <-> 4 board corners",
               "8 unknowns solved with SVD (DLT)",
               "(u,v,w) = H (x,y,1), then divide by w"],
     "diagram": True},
    {"title": "Step 3 - Interaction",
     "lines": ["Next -> left click: select / pen down-up",
               "Previous -> right click: back / lift pen",
               "Press Annotate below and draw on this slide!"]},
]