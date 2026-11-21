"""calibration.py - Calibration interactive : coins du tableau + couleur du marqueur."""
import json
import os
import cv2
import numpy as np
import config as C
from mapping import (BoardMapper, compute_homography, apply_homography,
                     reprojection_error, is_convex_quad)
from detection import bgr_to_hsv, MarkerDetector, save_params, load_params

M = 40  # marge des croix de calibration dans l'image projetee
PATTERN_PTS = np.array([[M, M], [C.UI_W - M, M], [C.UI_W - M, C.UI_H - M], [M, C.UI_H - M]], float)
GRID = np.array([[x, y] for y in np.linspace(M, C.UI_H - M, 4)
                 for x in np.linspace(M, C.UI_W - M, 5)], float)


def make_pattern():
    """Image projetee pendant la calibration : 4 croix de coins + grille de points de controle."""
    img = np.full((C.UI_H, C.UI_W, 3), 30, np.uint8)
    for x, y in GRID:
        cv2.circle(img, (int(x), int(y)), 8, (255, 255, 255), -1)
    for x, y in PATTERN_PTS:
        cv2.drawMarker(img, (int(x), int(y)), (0, 140, 255), cv2.MARKER_CROSS, 60, 4)
    cv2.putText(img, "CALIBRATION", (C.UI_W // 2 - 150, C.UI_H // 2), cv2.FONT_HERSHEY_SIMPLEX,
                1.6, (255, 255, 255), 3, cv2.LINE_AA)
    return img


def save_calibration(corners_img, H):
    with open(C.CALIB_FILE, "w") as f:
        json.dump({"corners_img": np.asarray(corners_img).tolist(), "H": np.asarray(H).tolist()}, f, indent=2)


def load_mapper():
    if not os.path.exists(C.CALIB_FILE):
        return None
    with open(C.CALIB_FILE) as f:
        return BoardMapper(np.array(json.load(f)["H"]))


def calibrate_corners(cam, ui_win):
    """Clique les 4 croix (HG, HD, BD, BG) sur la vue camera. Les clics suivants servent de
    validation (clic sur un point de la grille -> erreur mesuree). ENTREE = sauver, r = reset."""
    win = "Calibration: click TL, TR, BR, BL crosses"
    pts, checks = [], []

    def on_mouse(ev, x, y, flags, param):
        if ev == cv2.EVENT_LBUTTONDOWN:
            (pts if len(pts) < 4 else checks).append((x, y))

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)
    pattern = make_pattern()
    H, msg = None, "Click the 4 crosses in order"
    while True:
        cv2.imshow(ui_win, pattern)
        frame = cam.read()
        if frame is None:
            continue
        vis = frame.copy()
        H = None
        if len(pts) == 4:
            if not is_convex_quad(pts):
                msg = "Bad order / not convex: press r"
            else:
                H = compute_homography(pts, PATTERN_PTS)
                Hinv = np.linalg.inv(H)
                for g in GRID:                                   # grille predite -> doit coller
                    px, py = apply_homography(Hinv, g)[0]
                    cv2.circle(vis, (int(px), int(py)), 6, (0, 0, 255), 1)
                msg = f"4-corner fit {reprojection_error(H, pts, PATTERN_PTS):.2f}px"
                if checks:
                    errs = []
                    for c in checks:
                        b = apply_homography(H, c)[0]
                        errs.append(np.min(np.hypot(*(GRID - b).T)))
                    msg += f" | check error: {np.mean(errs):.1f} board px"
                msg += " | ENTER=save r=reset"
        for i, p in enumerate(pts):
            cv2.circle(vis, p, 5, (0, 255, 255), -1)
            cv2.putText(vis, ["TL", "TR", "BR", "BL"][i], (p[0] + 8, p[1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        for c in checks:
            cv2.circle(vis, c, 4, (255, 0, 255), -1)
        cv2.putText(vis, msg, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.imshow(win, vis)
        k = cv2.waitKey(20) & 0xFF
        if k == ord('r'):
            pts.clear(); checks.clear(); msg = "Click the 4 crosses in order"
        elif k in (13, 10) and H is not None:
            save_calibration(pts, H)
            cv2.destroyWindow(win)
            return BoardMapper(H)
        elif k == 27:
            cv2.destroyWindow(win)
            return None


def calibrate_marker_color(cam):
    """Clique sur le marqueur : la teinte/saturation/valeur sont echantillonnees (zone 5x5)."""
    win = "Marker color: click on the marker, ENTER = save, ESC = cancel"
    sample, params = [None], [None]

    def on_mouse(ev, x, y, flags, param):
        if ev == cv2.EVENT_LBUTTONDOWN:
            sample[0] = (x, y)

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)
    while True:
        frame = cam.read()
        if frame is None:
            continue
        vis = frame.copy()
        if sample[0] is not None:
            x, y = sample[0]
            patch = frame[max(y - 2, 0):y + 3, max(x - 2, 0):x + 3]
            hsv = bgr_to_hsv(patch)
            ang = np.deg2rad(hsv[..., 0])                         # moyenne circulaire de la teinte
            hue = float(np.rad2deg(np.arctan2(np.sin(ang).mean(), np.cos(ang).mean())) % 360)
            s, v = float(hsv[..., 1].mean()), float(hsv[..., 2].mean())
            params[0] = {"hue": hue, "hue_tol": 25.0,
                         "s_min": max(0.25, 0.6 * s), "v_min": max(0.2, 0.6 * v)}
            mask = MarkerDetector(params[0]).segment(frame)       # apercu : pixels retenus en rouge
            ys, xs = np.nonzero(mask)
            vis[ys * C.DETECT_STRIDE, xs * C.DETECT_STRIDE] = (0, 0, 255)
            cv2.putText(vis, f"H={hue:.0f} S={s:.2f} V={v:.2f}", (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow(win, vis)
        k = cv2.waitKey(20) & 0xFF
        if k in (13, 10) and params[0] is not None:
            save_params(params[0]); cv2.destroyWindow(win)
            return params[0]
        if k == 27:
            cv2.destroyWindow(win)
            return None