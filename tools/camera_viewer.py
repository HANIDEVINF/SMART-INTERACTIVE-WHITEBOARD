"""Camera debug viewer.

Opens the webcam (or simulated source), shows the live feed with the
detected marker centroid and blob bounding boxes overlaid, and prints FPS.

Run:  python tools/camera_viewer.py [--sim] [--index N]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import load_settings
from detection.color_detector import ColorDetector


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", action="store_true",
                        help="use the simulated camera source")
    parser.add_argument("--index", type=int, default=None,
                        help="camera index (default: from settings)")
    args = parser.parse_args()

    settings = load_settings()
    if args.sim:
        settings["camera_source"] = "simulated"
    if args.index is not None:
        settings["camera_index"] = args.index

    from camera.camera_manager import CameraManager
    cam = CameraManager(settings)
    if not cam.open():
        print(f"ERROR: {cam.last_error}")
        sys.exit(1)

    detector = ColorDetector(settings["marker_hsv"],
                             min_area=settings.get("marker_min_area", 400))

    print("Camera viewer running. Press Q or ESC to quit.")
    fps_time = time.time()
    fps_frames = 0
    fps = 0.0

    try:
        while True:
            frame = cam.read()
            if frame is None:
                print("Frame lost, retrying...")
                time.sleep(0.05)
                continue

            mask, blobs = detector.detect_debug(frame)
            if mask is not None:
                # Overlay the mask in red.
                overlay = frame.copy()
                overlay[mask] = (0, 0, 255)
                cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)
                for b in blobs[:5]:
                    x0, y0, x1, y1 = b["bbox"]
                    cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 255, 255), 2)
                    cx, cy = b["centroid"]
                    cv2.circle(frame, (int(cx), int(cy)), 6, (0, 255, 0), -1)
                    cv2.putText(frame, f"area={b['area']}", (x0, max(0, y0 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            fps_frames += 1
            now = time.time()
            if now - fps_time >= 0.5:
                fps = fps_frames / (now - fps_time)
                fps_frames = 0
                fps_time = now

            cv2.putText(frame, f"FPS: {fps:.1f}  src: {cam.source_name}",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 255, 0), 2)
            cv2.imshow("Camera Debug", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
