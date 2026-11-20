"""Generate the sample images used by the demo lesson (no downloads needed).

    python tools/make_assets.py
"""
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "images")
os.makedirs(OUT, exist_ok=True)


def save(name, img):
    import cv2
    cv2.imwrite(os.path.join(OUT, name), img)
    print("wrote", name, img.shape)


def gradient_landscape(w=1600, h=900):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    sky = np.zeros((h, w, 3), np.float32)
    t = y / h
    sky[..., 0] = 255 * (1 - 0.5 * t)       # B
    sky[..., 1] = 200 * (1 - 0.6 * t) + 40
    sky[..., 2] = 90 + 60 * t               # R (kept low: no strong red)
    ridge = h * 0.62 + 70 * np.sin(x / 140.0) + 40 * np.sin(x / 57.0 + 1)
    ground = y > ridge
    sky[ground] = (60 + 40 * (y[ground] - ridge[ground]) / h)[:, None] * np.array([1.0, 1.9, 0.9])
    sun = (x - w * 0.75) ** 2 + (y - h * 0.25) ** 2 < 70 ** 2
    sky[sun] = (120, 230, 255)
    return np.clip(sky, 0, 255).astype(np.uint8)


def pipeline_diagram(w=1600, h=900):
    import cv2
    img = np.full((h, w, 3), (50, 40, 32), np.uint8)
    steps = ["Camera frame", "Red dot detection", "Image -> board", "Remote key", "Click", "Update UI"]
    n = len(steps)
    bw, bh, gap = 220, 120, 36
    x0 = (w - (n * bw + (n - 1) * gap)) // 2
    y0 = h // 2 - bh // 2
    for i, s in enumerate(steps):
        x = x0 + i * (bw + gap)
        cv2.rectangle(img, (x, y0), (x + bw, y0 + bh), (200, 150, 60), 3)
        words = s.split(" ", 1)
        for j, wd in enumerate(words):
            cv2.putText(img, wd, (x + 14, y0 + 52 + 36 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (245, 240, 235), 2, cv2.LINE_AA)
        if i < n - 1:
            cv2.arrowedLine(img, (x + bw + 4, y0 + bh // 2), (x + bw + gap - 4, y0 + bh // 2), (245, 240, 235), 3, tipLength=0.4)
    cv2.putText(img, "Main interaction pipeline", (w // 2 - 260, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (245, 240, 235), 3, cv2.LINE_AA)
    return img


def checker_grid(w=1600, h=900):
    """High-detail image: handy to test zoom (fine grid + coordinates)."""
    import cv2
    img = np.full((h, w, 3), 40, np.uint8)
    for x in range(0, w, 50):
        cv2.line(img, (x, 0), (x, h), (90, 80, 70) if x % 200 else (200, 170, 100), 1)
    for y in range(0, h, 50):
        cv2.line(img, (0, y), (w, y), (90, 80, 70) if y % 200 else (200, 170, 100), 1)
    for x in range(0, w, 200):
        for y in range(0, h, 200):
            cv2.putText(img, f"{x},{y}", (x + 4, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1, cv2.LINE_AA)
    cv2.circle(img, (w // 2, h // 2), 120, (110, 210, 120), 3)
    return img


if __name__ == "__main__":
    save("1_landscape.png", gradient_landscape())
    save("2_pipeline.png", pipeline_diagram())
    save("3_grid_zoom_test.png", checker_grid())
