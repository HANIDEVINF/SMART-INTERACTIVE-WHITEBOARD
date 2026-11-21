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

# ---- Palette victorienne "rose & or" (BGR) : vin, aubergine, or antique, creme, rose poudre ----
# Pas de vert dans l'interface (reserve au marqueur).
BG_TOP = (46, 22, 74)            # vin
BG_BOTTOM = (28, 10, 30)         # aubergine
BG = BG_BOTTOM
HEADER_TOP, HEADER_BOTTOM = (66, 38, 110), (44, 22, 66)
PANEL = (48, 28, 66)             # velours acajou
HOVER = (76, 48, 104)
GOLD = (90, 172, 212)            # or antique
GOLD_LIGHT = (150, 221, 245)
GOLD_DARK = (48, 104, 140)
IVORY = (216, 238, 248)          # creme
ACCENT = GOLD
TEXT = IVORY
GRAY = (176, 180, 204)           # rose-beige
POINTER_COLOR = (40, 170, 255)
CLICK_LEFT = GOLD_LIGHT
CLICK_RIGHT = (170, 140, 232)    # rose
DANGER = (70, 36, 140)
# Cartes assorties (tons joyaux adoucis) : rose poudre, mauve, bleu paon, bronze
CARD_COLORS = [(116, 92, 176), (156, 88, 122), (124, 108, 44), (52, 120, 168)]
PEN_COLORS = [IVORY, GOLD_LIGHT, (170, 140, 232), (232, 170, 196), (232, 210, 150)]
PEN_SIZES = [4, 10, 22]