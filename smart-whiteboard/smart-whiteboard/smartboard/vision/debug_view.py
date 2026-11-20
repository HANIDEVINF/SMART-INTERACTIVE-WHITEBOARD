"""Operator-facing camera window: what the computer sees (not projected)."""
from __future__ import annotations

from typing import Optional

import numpy as np

from .calibration import Calibration


def build_debug_image(frame: Optional[np.ndarray], detection, calib: Calibration,
                      sample, status: str, out_w: int = 640):
    """Return a BGR image: camera frame + detection mask tint + board quad + dot."""
    import cv2  # only used for drawing lines/text on the operator's window
    if frame is None:
        img = np.zeros((360, out_w, 3), np.uint8)
        cv2.putText(img, "no camera frame", (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
        return img, 1.0
    h, w = frame.shape[:2]
    scale = out_w / float(w)
    img = cv2.resize(frame, (out_w, int(h * scale)))

    if detection is not None and detection.mask is not None:
        k = frame.shape[1] / detection.mask.shape[1]
        ys, xs = np.nonzero(detection.mask)
        for x, y in zip(xs, ys):
            cv2.circle(img, (int((x + .5) * k * scale), int((y + .5) * k * scale)), 1, (0, 255, 255), -1)

    quad = calib.board_quad_in_camera()
    if quad is not None:
        cv2.polylines(img, [(quad * scale).astype(np.int32)], True, (0, 255, 0), 2)
    if detection is not None:
        p = (int(detection.x * scale), int(detection.y * scale))
        cv2.drawMarker(img, p, (255, 255, 0), cv2.MARKER_CROSS, 22, 2)
    cv2.rectangle(img, (0, 0), (out_w, 26), (0, 0, 0), -1)
    cv2.putText(img, status, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return img, scale
