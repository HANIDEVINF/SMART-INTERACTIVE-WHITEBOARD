"""identify_keys.py - Outil : trouve les codes REELS des 2 boutons de la telecommande.
Lancer :  python identify_keys.py   (garder la fenetre au premier plan)
Ecrit keymap.json, utilise ensuite automatiquement par remote_input.py."""
import json
import time
import cv2
import numpy as np
import config as C

names_seen = []
try:
    from pynput import keyboard

    def _on(key):
        names_seen.append(key.char if getattr(key, "char", None) else str(key).replace("Key.", ""))
    keyboard.Listener(on_press=_on).start()
except ImportError:
    pass

WIN = "Identify remote keys"


def capture(msg):
    img = np.zeros((200, 900, 3), np.uint8)
    cv2.putText(img, msg, (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    cv2.imshow(WIN, img)
    names_seen.clear()
    codes = []
    while not codes:
        k = cv2.waitKeyEx(30)
        if k != -1:
            codes.append(k)
    t = time.time()
    while time.time() - t < 0.7:                 # certaines telecommandes envoient plusieurs codes
        k = cv2.waitKeyEx(30)
        if k != -1 and k not in codes:
            codes.append(k)
    return codes, sorted(set(names_seen))


def main():
    nxt, nxt_names = capture("Press the NEXT button on the remote")
    time.sleep(0.8)
    prv, prv_names = capture("Press the PREVIOUS button on the remote")
    print("NEXT     (left click) codes:", nxt, "names:", nxt_names)
    print("PREVIOUS (right click) codes:", prv, "names:", prv_names)
    km = {"left_codes": nxt, "right_codes": prv}
    if nxt_names and prv_names:
        km.update(left_names=nxt_names, right_names=prv_names)
    with open(C.KEYMAP_FILE, "w") as f:
        json.dump(km, f, indent=2)
    print("Saved to", C.KEYMAP_FILE)


if __name__ == "__main__":
    main()
