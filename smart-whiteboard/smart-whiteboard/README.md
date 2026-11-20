# Smart Interactive Whiteboard

Camera-based interactive whiteboard (USTHB – Computer Vision project 2026-2027, Python + NumPy).
A projector shows the interface on the wall, a fixed camera watches it, the **red dot** of a pointer is the
cursor, and the two buttons of a presentation remote are the **left / right click**.

```
camera frame → red-dot detection → image→board mapping → remote key → click at pointer → update interface
```

## Quick start

```bash
pip install -r requirements.txt

python main.py --mouse        # no hardware: mouse = pointer, mouse buttons = remote (UI development)
python main.py --synthetic    # whole vision pipeline on a simulated camera (self-test / demo)
python main.py                # real setup: camera + projector + remote
```

Real setup checklist
1. Projector = second monitor. Set `display.width/height` (projector resolution) and `display.window_x`
   (e.g. `1920`, the x-offset of the projector monitor) in `config.json`.
2. Plug the remote, run `python tools/key_finder.py`, press **Next** then **Previous**, copy the printed codes into
   `remote.next_codes` / `remote.prev_codes`.
3. Lower the camera exposure (`camera.exposure`) so the room is dark and the dot is the brightest red thing.
4. `python main.py` → the calibration screen opens on first start (see below).

## Controls

| Remote button | Click | Menus | Drawing | Images | Objects | Lesson |
|---|---|---|---|---|---|---|
| **Next** | LEFT | select | pen down / up, pick tool | zoom, grab image to pan | grab / drop shape | next page, annotate |
| **Previous** | RIGHT | back one level | lift pen, else back | release, else back | cancel grab, else back | lift pen / previous page |

The top bar (**Home**, **Reset**) is on every screen. Keyboard fallbacks (projector window focused):
`q`/`Esc` quit · `h` home · `r` reset · `c` recalibrate · `d` camera window on/off.

## Calibration (image → board coordinates)
1. Four targets appear at known board positions (TL, TR, BR, BL).
2. Aim the red dot at a target, press **Next**. (Or click the dot in the *operator camera window* with the mouse.)
3. A homography camera→board is computed (DLT, `vision/calibration.py`).
4. Validation: new targets, point + **Next**; the mean error in pixels is shown. **Next** = save (`calibration.json`),
   **Previous** = redo.

## Project structure – one folder / file per functionality

```
main.py                         entry point (--mouse / --synthetic / --windowed / --recalibrate)
config.json                     every tunable parameter (camera, detection, remote keys, ...)
smartboard/
  config.py                     dataclass configuration + JSON loading
  events.py                     ClickEvent, PointerSample
  context.py                    shared state given to every screen
  app.py                        main loop: pointer → remote → screens → render
  vision/
    imgproc.py                  OWN NumPy code: BGR→HSV, threshold, majority filter, dilation,
                                connected components, weighted centroid, bilinear resize
    camera.py                   threaded camera capture + SyntheticCamera (tests/demo)
    detector.py                 red-dot detection (HSV threshold + ROI + blob scoring)
    tracker.py                  One-Euro smoothing + lost-frame hold
    calibration.py              homography (DLT), save/load, residuals
    pointer_source.py           VisionPointerSource (camera) | MousePointerSource (simulation)
    debug_view.py               operator window (mask, board quad, dot)
  remote/remote_input.py        key codes → LEFT / RIGHT (opencv or pynput back-end)
  graphics/
    primitives.py               OWN NumPy drawing: segment, circle, ring, rect, polygon
    canvas.py  theme.py  widgets.py  hud.py   framebuffer, colours (NO red), buttons, top bar + cursor
  features/                     pure logic, no input/rendering code
    drawing.py                  strokes, colours, thickness, eraser, undo, clear
    image_viewer.py             load / zoom / pan / reset
    objects.py                  drag & drop shapes + drop zones
    lesson.py                   lesson loader (assets/lesson/lesson.json)
  screens/                      one screen per functionality
    menu.py + menu_tree.py      menus & submenus (edit menu_tree.py to change entries)
    draw.py  images.py  objects.py  lesson.py  calibration.py  navigator.py  base.py
assets/images, assets/lesson    demo content (regenerate images: python tools/make_assets.py)
tools/key_finder.py             find the key codes of your remote
tests/                          python -m pytest -q
```

## Requirement → where it is implemented

| Requirement | Module |
|---|---|
| Pointer tracking + visible pointer | `vision/detector.py`, `vision/tracker.py`, `graphics/hud.py` |
| Coordinate mapping (geometric transform) | `vision/calibration.py` |
| Remote control, 2 key codes → clicks | `remote/remote_input.py`, `tools/key_finder.py`, `config.json` |
| Menus + submenus | `screens/menu.py`, `screens/menu_tree.py` |
| Free drawing, ≥2 colours / thicknesses, clear | `features/drawing.py`, `screens/draw.py` |
| Image display + zoom + return to original | `features/image_viewer.py`, `screens/images.py` |
| Teaching content / coherent sequence | `features/lesson.py`, `screens/lesson.py`, `assets/lesson/lesson.json` |
| Basic usability: pointer, home, reset | `graphics/hud.py`, `screens/navigator.py` |
| Drag & drop (extra) | `features/objects.py`, `screens/objects.py` |

## Method notes (for the report)

* **Detection**: decimate ×2 → HSV → mask `hue within ±22° of red AND S ≥ 0.45 AND V ≥ 0.75` → keep only the
  calibrated board region → 3×3 majority filter → connected components → blob score
  (brightness × roundness × size, biased towards the previous position) → intensity-weighted centroid.
* **Stability**: One-Euro filter (little jitter when still, little lag when moving), the last position is held for
  `max_lost_frames` after a miss, board position clamped to the screen.
* **Limits**: red clothes / objects, strong ambient light, a saturated (white) laser spot, lens distortion
  (homography assumes a pinhole camera), board not perfectly planar, remote needs window focus with the `opencv`
  back-end (use `pynput` for a global hook). The UI never uses red, so the projector cannot create false dots.
* **Predefined functions used and why**: OpenCV only for camera capture, window display, image-file decoding and
  font rasterisation; `np.linalg.svd` for the DLT least-squares solution. Everything else is NumPy code in this repo.
* **Performance**: detection ≈ 13 ms/frame at 1280×720 with `downscale=2` (CPU, NumPy). No GPU is required;
  a GPU PC simply gives headroom for higher camera resolutions.

## Tests
```bash
python -m pytest -q          # geometry, detection accuracy, filters, every screen, calibration flow
SWB_SHOTS=shots python tests/test_app.py     # also saves screenshots of each screen
```
Synthetic-camera result: mean mapping error ≈ 0.8 px on a 1920×1080 board.

## Push to GitHub
```bash
cd smart-whiteboard
git init && git add . && git commit -m "Smart interactive whiteboard"
git branch -M main
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```
