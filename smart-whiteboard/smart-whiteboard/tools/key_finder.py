"""Find the key codes sent by YOUR presentation remote.

    python tools/key_finder.py

1. A small window opens - click on it so it has keyboard focus.
2. Press the "Next" button, then the "Previous" button on the remote.
3. Copy the printed codes into config.json:
       "remote": { "next_codes": [<code>], "prev_codes": [<code>] }
Press q (or ESC) in the window to quit.

Codes come from cv2.waitKeyEx() and differ between Windows and Linux.
"""
import numpy as np


def main():
    import cv2
    win = "Remote key finder (click here, then press the remote buttons)"
    img = np.zeros((220, 760, 3), np.uint8)
    cv2.putText(img, "Press the remote buttons - codes are printed in the terminal",
                (14, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.namedWindow(win)
    print("Waiting for keys... (q / ESC to quit)")
    last = ""
    while True:
        cv2.imshow(win, img)
        k = cv2.waitKeyEx(50)
        if k < 0:
            continue
        if k in (27, ord("q")):
            break
        msg = f"key code = {k}   (hex 0x{k:X})" + (f"   char '{chr(k)}'" if 32 <= k < 127 else "")
        print(msg)
        img[:] = 0
        cv2.putText(img, msg, (14, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(img, "-> put it in remote.next_codes or remote.prev_codes",
                    (14, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
