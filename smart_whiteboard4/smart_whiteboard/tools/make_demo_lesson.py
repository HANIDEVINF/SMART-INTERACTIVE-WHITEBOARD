"""Generates data/lessons/demo_lesson.json and its pictures (data/lessons/demo/*.png).

Run from the project root:   python -m tools.make_demo_lesson
The pictures are drawn with NumPy/OpenCV, so the lesson is fully reproducible and has no external assets.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "lessons"
IMG = OUT / "demo"
F = cv2.FONT_HERSHEY_SIMPLEX


def canvas(w=900, h=620, color=(250, 249, 246)):
    img = np.empty((h, w, 3), np.uint8)
    img[:] = color
    return img


def label(img, text, org, scale=0.8, color=(60, 40, 30), thick=2):
    cv2.putText(img, text, org, F, scale, color, thick, cv2.LINE_AA)


def pixels():
    img = canvas()
    art = np.array([[0, 0, 0, 1, 1, 0, 0, 0], [0, 0, 1, 2, 2, 1, 0, 0], [0, 1, 2, 2, 2, 2, 1, 0],
                    [1, 2, 2, 3, 3, 2, 2, 1], [1, 2, 3, 3, 3, 3, 2, 1], [0, 1, 2, 3, 3, 2, 1, 0],
                    [0, 0, 1, 2, 2, 1, 0, 0], [0, 0, 0, 1, 1, 0, 0, 0]])
    pal = {0: (240, 236, 226), 1: (120, 190, 240), 2: (50, 130, 235), 3: (40, 60, 200)}
    cell = 62
    x0, y0 = 40, 50
    for r in range(8):
        for c in range(8):
            cv2.rectangle(img, (x0 + c * cell, y0 + r * cell), (x0 + (c + 1) * cell, y0 + (r + 1) * cell),
                          pal[int(art[r, c])], -1)
            cv2.rectangle(img, (x0 + c * cell, y0 + r * cell), (x0 + (c + 1) * cell, y0 + (r + 1) * cell),
                          (190, 185, 175), 1)
    r, c = 3, 3
    cv2.rectangle(img, (x0 + c * cell, y0 + r * cell), (x0 + (c + 1) * cell, y0 + (r + 1) * cell), (0, 0, 0), 4)
    bgr = pal[3]
    label(img, "8 x 8 pixels", (x0, y0 + 8 * cell + 40), 0.9)
    bx = 580
    label(img, "one pixel:", (bx, 120), 0.9)
    cv2.rectangle(img, (bx, 140), (bx + 110, 250), bgr, -1)
    cv2.rectangle(img, (bx, 140), (bx + 110, 250), (0, 0, 0), 2)
    label(img, f"B = {bgr[0]}", (bx, 300), 0.8, (200, 60, 40))
    label(img, f"G = {bgr[1]}", (bx, 340), 0.8, (40, 150, 40))
    label(img, f"R = {bgr[2]}", (bx, 380), 0.8, (40, 40, 210))
    label(img, "0..255 each", (bx, 430), 0.7, (110, 100, 90), 1)
    return img


def hsv():
    img = canvas()
    strip = np.zeros((90, 720, 3), np.uint8)
    hue = np.linspace(0, 179, 720).astype(np.uint8)
    strip[..., 0] = hue[None, :]
    strip[..., 1] = 230
    strip[..., 2] = 240
    strip = cv2.cvtColor(strip, cv2.COLOR_HSV2BGR)
    img[150:240, 90:810] = strip
    label(img, "Hue (H) : the colour itself", (90, 120), 0.9)
    lo, hi = 35, 85                      # a green window
    x0, x1 = 90 + int(lo / 179 * 720), 90 + int(hi / 179 * 720)
    cv2.rectangle(img, (x0, 140), (x1, 250), (30, 30, 30), 4)
    label(img, "keep H in [35, 85]", (x0 - 20, 290), 0.8)
    for i, (name, y) in enumerate((("Saturation (S): grey -> vivid", 380), ("Value (V): dark -> bright", 500))):
        g = np.zeros((60, 720, 3), np.uint8)
        g[..., 0] = 60
        ramp = np.linspace(40, 255, 720).astype(np.uint8)[None, :]
        g[..., 1] = ramp if i == 0 else 230
        g[..., 2] = 240 if i == 0 else ramp
        img[y:y + 60, 90:810] = cv2.cvtColor(g, cv2.COLOR_HSV2BGR)
        label(img, name, (90, y - 14), 0.8)
    return img


def segmentation():
    w, h = 440, 400
    scene = canvas(w, h, (200, 190, 180))
    cv2.rectangle(scene, (30, 40), (150, 120), (140, 150, 220), -1)
    cv2.rectangle(scene, (250, 260), (400, 360), (160, 120, 90), -1)
    cx, cy = 270, 150
    cv2.circle(scene, (cx, cy), 26, (60, 200, 70), -1)
    mask = np.zeros((h, w, 3), np.uint8)
    cv2.circle(mask, (cx, cy), 26, (255, 255, 255), -1)
    cv2.circle(mask, (60, 330), 4, (255, 255, 255), -1)          # a noise speck removed by opening
    cv2.circle(mask, (cx, cy), 5, (0, 0, 255), -1)
    cv2.line(mask, (cx - 18, cy), (cx + 18, cy), (0, 0, 255), 2)
    cv2.line(mask, (cx, cy - 18), (cx, cy + 18), (0, 0, 255), 2)
    img = canvas(940, 520)
    img[70:70 + h, 20:20 + w] = scene
    img[70:70 + h, 480:480 + w] = mask
    label(img, "camera image", (20, 50), 0.8)
    label(img, "binary mask + centroid", (480, 50), 0.8)
    label(img, "cx = m10 / m00 ,  cy = m01 / m00", (200, 500), 0.8, (150, 70, 60))
    return img


def homography():
    img = canvas(1000, 520)
    quad = np.array([[90, 120], [380, 70], [420, 330], [60, 360]], np.int32)
    cv2.fillPoly(img, [quad], (235, 225, 210))
    cv2.polylines(img, [quad], True, (60, 40, 30), 3, cv2.LINE_AA)
    for (x, y), n in zip(quad, ("TL", "TR", "BR", "BL")):
        cv2.circle(img, (int(x), int(y)), 9, (200, 80, 40), -1)
        label(img, n, (int(x) - 14, int(y) - 16), 0.7, (200, 80, 40))
    label(img, "camera view (perspective)", (40, 430), 0.75)
    cv2.arrowedLine(img, (450, 220), (560, 220), (60, 40, 30), 4, cv2.LINE_AA, tipLength=0.4)
    label(img, "H", (488, 200), 0.9, (150, 70, 60))
    rect = (600, 100, 340, 191)
    x, y, w, h = rect
    cv2.rectangle(img, (x, y), (x + w, y + h), (235, 225, 210), -1)
    for gx in range(1, 4):
        cv2.line(img, (x + gx * w // 4, y), (x + gx * w // 4, y + h), (200, 190, 175), 1)
    for gy in range(1, 3):
        cv2.line(img, (x, y + gy * h // 3), (x + w, y + gy * h // 3), (200, 190, 175), 1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (60, 40, 30), 3, cv2.LINE_AA)
    for (cx, cy), n in zip(((x, y), (x + w, y), (x + w, y + h), (x, y + h)), ("TL", "TR", "BR", "BL")):
        cv2.circle(img, (cx, cy), 9, (200, 80, 40), -1)
    label(img, "board 1600 x 900", (600, 340), 0.75)
    label(img, "4 corners -> 8 unknowns -> H", (300, 480), 0.75, (150, 70, 60))
    return img


def ema():
    img = canvas(940, 520)
    rng = np.random.default_rng(3)
    xs = np.arange(60)
    truth = 260 - 140 * np.tanh((xs - 30) / 6.0)
    meas = truth + rng.normal(0, 14, xs.size)
    out, p = [], meas[0]
    for m in meas:
        p = 0.3 * m + 0.7 * p
        out.append(p)
    px = lambda i: 40 + int(i * 14)
    cv2.line(img, (40, 470), (900, 470), (150, 145, 135), 2)
    cv2.line(img, (40, 40), (40, 470), (150, 145, 135), 2)
    pts_m = np.array([[px(i), int(v)] for i, v in enumerate(meas)], np.int32)
    pts_s = np.array([[px(i), int(v)] for i, v in enumerate(out)], np.int32)
    cv2.polylines(img, [pts_m], False, (170, 170, 220), 2, cv2.LINE_AA)
    for pt in pts_m:
        cv2.circle(img, tuple(int(v) for v in pt), 3, (130, 130, 210), -1)
    cv2.polylines(img, [pts_s], False, (200, 80, 40), 4, cv2.LINE_AA)
    label(img, "raw measurement (noisy)", (560, 70), 0.7, (130, 130, 210))
    label(img, "smoothed, alpha = 0.3", (560, 105), 0.7, (200, 80, 40))
    label(img, "time (frames)", (380, 505), 0.7, (110, 100, 90), 1)
    return img


LESSON = {
    "version": 1,
    "title": "How a camera becomes a pointer",
    "author": "LuminaBoard demo lesson",
    "pages": [
        {"title": "How a camera becomes a pointer",
         "text": "LuminaBoard turns a wall, a webcam and a coloured marker into an interactive board.\n\n"
                 "- 5 ideas, 5 pages: pixels, colour, finding the marker, mapping to the board, smoothing\n"
                 "- Use the Next / Previous controls at the bottom of the board (left click with the remote)\n"
                 "- Everything written on a page stays there when you come back\n"
                 "- Press M or right-click for the menu",
         "image": "", "notes": "Introduce the project goal and show how the page controls work."},
        {"title": "1. What the camera really gives us",
         "text": "A picture is a grid of numbers.\n\n- Each pixel stores Blue, Green and Red\n"
                 "- Each value is 0 to 255\n- A 1280 x 720 frame is 921 600 pixels\n"
                 "- Everything that follows is arithmetic on this grid",
         "image": "demo/pixels.png", "notes": "OpenCV stores channels in B, G, R order."},
        {"title": "2. Colour is easier in HSV",
         "text": "RGB mixes colour and brightness; HSV separates them.\n\n"
                 "- H: which colour (0 to 179 in OpenCV)\n- S: how vivid\n- V: how bright\n"
                 "> keep pixels with H in [h1, h2], S >= s1, V >= v1\n"
                 "- A marker keeps its hue when the light changes",
         "image": "demo/hsv.png", "notes": "Red wraps around hue 0, so it needs two ranges."},
        {"title": "3. Finding the marker",
         "text": "Threshold, clean, then measure.\n\n- Opening removes specks, closing fills holes\n"
                 "- Connected components give one blob per object\n- The biggest convincing blob is the marker\n"
                 "> cx = m10 / m00     cy = m01 / m00",
         "image": "demo/segmentation.png", "notes": "The centroid is the average position of the white pixels."},
        {"title": "4. From camera pixels to the board",
         "text": "The camera sees the board at an angle.\n\n- Click the 4 corners once: this is calibration\n"
                 "- 4 point pairs give 8 equations for the 8 unknowns of H\n"
                 "> [x' y' w']^T = H [x y 1]^T ,  board = (x'/w', y'/w')\n- Then every camera pixel has a board position",
         "image": "demo/homography.png", "notes": "Solved with the DLT algorithm and an SVD."},
        {"title": "5. Smoothing the pointer",
         "text": "A raw centroid jitters by a few pixels.\n\n- Blend each new measurement with the previous position\n"
                 "> p(t) = alpha * m(t) + (1 - alpha) * p(t-1)\n"
                 "- Small alpha: smooth but slow;  alpha = 1: raw\n- Jumps are checked before they are accepted",
         "image": "demo/ema.png", "notes": "Exponential moving average."},
        {"title": "Your turn",
         "text": "Try the tools on this page.\n\n- Switch to Drawing mode and write your answer here\n"
                 "- Why does a red marker need two hue ranges?\n- Go back to page 3 with Previous and circle the centroid\n"
                 "- Come back: your notes are still on the page\n- Menu > Image lets you zoom and pan",
         "image": "", "notes": "Hue is circular: red is at both ends of the scale."},
    ],
}


def main() -> None:
    import json
    IMG.mkdir(parents=True, exist_ok=True)
    for name, fn in (("pixels", pixels), ("hsv", hsv), ("segmentation", segmentation), ("homography", homography),
                     ("ema", ema)):
        ok, buf = cv2.imencode(".png", fn())
        assert ok
        (IMG / f"{name}.png").write_bytes(buf.tobytes())
    (OUT / "demo_lesson.json").write_text(json.dumps(LESSON, indent=2, ensure_ascii=False), encoding="utf-8")
    print("written", OUT / "demo_lesson.json")


if __name__ == "__main__":
    main()
