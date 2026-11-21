"""main.py - Point d'entree : relie camera -> detection -> mapping -> telecommande -> UI.

Usage :
  python main.py              # mode reel (camera + projecteur)
  python main.py --sim        # test sans camera : souris = pointeur, boutons souris = clics
  python main.py --fullscreen # fenetre UI en plein ecran (sur le projecteur)
Raccourcis : c = recalibrer | m = couleur du marqueur | d = vue camera | q = quitter
"""
import argparse
import cv2
import numpy as np
import config as C
from app import App
from remote_input import RemoteInput
from ui import resize_nearest

UI_WIN, DBG_WIN = "Smart Whiteboard (projector)", "Camera debug"


def draw_debug(frame, mask, pos, mapper):
    vis = frame.copy()
    quad = np.array([mapper.to_image(p) for p in [(0, 0), (C.UI_W, 0), (C.UI_W, C.UI_H), (0, C.UI_H)]], np.int32)
    cv2.polylines(vis, [quad], True, (0, 255, 255), 2)
    if pos is not None:
        cv2.drawMarker(vis, (int(pos[0]), int(pos[1])), (0, 0, 255), cv2.MARKER_CROSS, 30, 2)
    m = resize_nearest(mask.astype(np.uint8) * 255, 120, 160)
    vis[:120, :160] = np.dstack([m, m, m])
    return vis


def handle_requests(app, ctx):
    for r in app.pop_requests():
        if r == "quit":
            ctx["running"] = False
        elif r == "debug" and not ctx["sim"]:
            ctx["debug"] = not ctx["debug"]
            if not ctx["debug"]:
                cv2.destroyWindow(DBG_WIN)
        elif ctx["sim"]:
            app.toast("Not available in simulation mode")
        elif r == "calibrate":
            from calibration import calibrate_corners
            m = calibrate_corners(ctx["cam"], UI_WIN)
            if m:
                ctx["mapper"] = m
        elif r == "marker":
            from calibration import calibrate_marker_color
            p = calibrate_marker_color(ctx["cam"])
            if p:
                ctx["detector"].set_params(p)


def run_sim(app, remote):
    cv2.namedWindow(UI_WIN, cv2.WINDOW_AUTOSIZE)
    st = {"pos": None, "ev": []}

    def on_mouse(ev, x, y, flags, param):
        st["pos"] = (x, y)
        if ev == cv2.EVENT_LBUTTONDOWN:
            st["ev"].append("left")
        elif ev == cv2.EVENT_RBUTTONDOWN:
            st["ev"].append("right")

    cv2.setMouseCallback(UI_WIN, on_mouse)
    ctx = {"sim": True, "running": True}
    while ctx["running"]:
        app.update(st["pos"])
        cv2.imshow(UI_WIN, app.render())
        key = cv2.waitKeyEx(15)
        if key in (ord('q'), 27):
            break
        events, st["ev"] = st["ev"] + remote.poll(key), []
        for ev in events:
            app.handle_event(ev)
        handle_requests(app, ctx)


def run_live(app, remote, args):
    from camera import Camera
    from detection import MarkerDetector
    from calibration import load_mapper, calibrate_corners, calibrate_marker_color
    from mapping import BoardMapper

    cam = Camera(args.camera, C.CAM_W, C.CAM_H)
    cv2.namedWindow(UI_WIN, cv2.WINDOW_NORMAL)
    if args.fullscreen:
        cv2.setWindowProperty(UI_WIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    mapper = load_mapper() or calibrate_corners(cam, UI_WIN)
    if mapper is None:
        print("Calibration cancelled.")
        return
    ctx = {"sim": False, "running": True, "debug": True, "cam": cam,
           "mapper": mapper, "detector": MarkerDetector()}
    while ctx["running"]:
        frame = cam.read()
        if frame is None:
            continue
        pos, mask = ctx["detector"].detect(frame)             # 1. detection (pixels camera)
        pointer = None
        if pos is not None:
            bx, by = ctx["mapper"].to_board(pos)              # 2. image -> tableau
            if BoardMapper.inside(bx, by, C.BOARD_MARGIN):
                pointer = (min(max(bx, 0), C.UI_W - 1), min(max(by, 0), C.UI_H - 1))
        app.update(pointer)                                   # 3. logique + rendu
        cv2.imshow(UI_WIN, app.render())
        if ctx["debug"]:
            cv2.imshow(DBG_WIN, draw_debug(frame, mask, pos, ctx["mapper"]))
        key = cv2.waitKeyEx(1)
        if key == ord('q'):
            break
        if key == ord('c'):
            app.request("calibrate")
        elif key == ord('m'):
            app.request("marker")
        elif key == ord('d'):
            app.request("debug")
        for ev in remote.poll(key):                           # 4. telecommande -> clic
            app.handle_event(ev)
        handle_requests(app, ctx)
    cam.release()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--fullscreen", action="store_true")
    ap.add_argument("--camera", type=int, default=C.CAMERA_INDEX)
    args = ap.parse_args()
    app, remote = App(), RemoteInput()
    try:
        run_sim(app, remote) if args.sim else run_live(app, remote, args)
    finally:
        remote.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()