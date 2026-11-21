"""config.py - Constantes globales du projet (tout ce qu'on peut regler est ici)."""

# ---- Interface projetee (= systeme de coordonnees "tableau", en pixels) ----
UI_W, UI_H = 1280, 720

# ---- Camera ----
CAMERA_INDEX = 0
CAM_W, CAM_H = 640, 480

# ---- Fichiers de configuration generes par l'application ----
CALIB_FILE = "calibration.json"   # homographie image -> tableau
MARKER_FILE = "marker.json"       # couleur du marqueur
KEYMAP_FILE = "keymap.json"       # codes des touches de la telecommande
IMAGES_DIR = "images"

# ---- Detection du marqueur (segmentation couleur en HSV) ----
DETECT_STRIDE = 2        # on traite 1 pixel sur 2 (vitesse)
# Teinte en degres [0,360), S et V dans [0,1]. Defaut : marqueur VERT.
DEFAULT_MARKER = {"hue": 120.0, "hue_tol": 28.0, "s_min": 0.45, "v_min": 0.35}
MIN_AREA = 12            # nb min de pixels (image reduite) pour valider
ROBUST_RADIUS = 25       # rayon (image reduite) pour rejeter les parasites
SMOOTH_ALPHA = 0.45      # lissage exponentiel (0..1, grand = reactif)
LOST_FRAMES = 8          # nb d'images pendant lesquelles on garde la derniere position
BOARD_MARGIN = 40        # tolerance hors du tableau (pixels tableau)

# ---- Telecommande ----
REMOTE_BACKEND = "opencv"   # "opencv" (fenetre au focus) ou "pynput" (global)
CLICK_DEBOUNCE = 0.25       # secondes entre 2 clics (anti-repetition)
# Codes par defaut de cv2.waitKeyEx : PageDown/PageUp/Droite/Gauche (Windows + Linux) + 'n'/'p'
# Next -> clic gauche ; Previous -> clic droit. Utiliser identify_keys.py pour TA telecommande.
DEFAULT_KEYMAP = {
    "left_codes":  [2228224, 65366, 2555904, 65363, ord('n')],
    "right_codes": [2162688, 65365, 2424832, 65361, ord('p')],
    "left_names":  ["page_down", "right", "down", "n"],
    "right_names": ["page_up", "left", "up", "p"],
}

# ---- Palette victorienne (BGR) : velours bordeaux, or, ivoire, acajou. Pas de vert (marqueur !) ----
BG_TOP = (58, 24, 104)           # bordeaux
BG_BOTTOM = (28, 10, 52)
BG = BG_BOTTOM
PANEL = (36, 30, 84)             # acajou / velours sombre
HOVER = (62, 46, 128)
GOLD = (60, 170, 212)
GOLD_LIGHT = (130, 215, 245)
GOLD_DARK = (28, 105, 150)
IVORY = (205, 235, 245)
ACCENT = GOLD
TEXT = IVORY
GRAY = (150, 170, 190)           # parchemin pale
POINTER_COLOR = (40, 170, 255)
CLICK_LEFT = GOLD_LIGHT
CLICK_RIGHT = (130, 90, 230)     # rose
CARD_COLORS = [(52, 28, 150), (110, 44, 100), (118, 88, 24), (30, 80, 160)]  # cramoisi, prune, bleu paon, rouille
PEN_COLORS = [IVORY, GOLD_LIGHT, (130, 90, 230), (230, 150, 180), (230, 200, 120)]  # ivoire, or, rose, lavande, ciel
PEN_SIZES = [4, 10, 22]