# Smart Interactive Whiteboard

Computer Vision project, USTHB 2026-2027 (Dr. ABADA Lyes). Python + NumPy.

A fixed camera watches a projected interface. The cursor is **your fingertip** (hand mode) or the **red dot**
of a pointer (red-dot mode), and the two buttons of a presentation remote are the mouse:
**Next = left click, Previous = right click**, always at the current pointer position.
The camera can be a **USB webcam or a phone** (see "Phone as camera").

```
camera frame -> hand / red-dot detection -> image->board mapping -> remote key -> click at pointer -> interface
   (thread)        detector.py          calibration.py        remote_input.py     app.py        screens/
```

## Run

```bash
pip install -r requirements.txt
python main.py --hand          # HAND mode: fingertip is the cursor (skin detection) + remote
python main.py                 # red-dot mode (default of config.json) + remote
python main.py --hand --source http://192.168.1.20:8080/video   # phone camera over Wi-Fi (URL of your app)
python main.py --mouse         # develop the interface at home: mouse = pointer, mouse buttons = remote
python main.py --synthetic     # whole vision pipeline on a simulated camera (self-test / demo)
python tools/key_finder.py     # find the key codes of YOUR remote -> put them in config.json (remote.*)
python tools/trajectory_bench.py   # accuracy of the tracking on a moving dot (numbers + picture)
python tools/screenshots.py       # PNG of every screen (for the report)
python -m pytest -q            # 34 tests, headless
```

Keyboard (operator): `q`/Esc quit, `h` home, `r` reset, `c` recalibrate, `d` camera window.

## Features

| Requirement of the subject | Where |
|---|---|
| Pointer tracking, shown on the interface | `vision/hand_detector.py` (+ `skin.py`, `fingertip.py`, `labeling.py`) or `vision/detector.py` (red dot), `vision/tracker.py`, `graphics/hud.py` (cursor, trail, X/Y readout) |
| Coordinate mapping (calibrated camera, geometric transform) | `vision/calibration.py` (homography by DLT + lens distortion k1) |
| Remote control, 2 buttons -> left / right click, key codes identified | `remote/remote_input.py`, `tools/key_finder.py`, `config.json` |
| Menus + submenus | `screens/menu.py`, `screens/menu_tree.py` |
| Free drawing, colours, thicknesses, clear | `features/drawing.py`, `screens/draw.py` |
| Image display + zoom + original view | `features/image_viewer.py`, `screens/images.py` |
| Teaching content: a small lesson | `features/lesson.py`, `screens/lesson.py`, `assets/lesson/lesson.json` |
| Usability: visible pointer, Home, Reset | `graphics/hud.py`, `screens/navigator.py` |
| Object drag & drop (figure of the subject) | `features/objects.py`, `screens/objects.py` |

Extra features: pen / eraser / line / arrow / box / circle tools with undo-redo and PNG snapshot, three board
backgrounds; **spotlight** and **magnifier** overlays that work on every screen; quiz pages with scoring;
classroom **timer**; **pointer test** (live trajectory + accuracy measurement); first-start **calibration
wizard** (9 targets, hold-still auto capture, validation); sensitivity setting for the dot thresholds.

## Phone as camera (or the laptop webcam)

Any camera that OpenCV can open works; calibration absorbs the camera position and angle, so just put it on a
tripod in front of the board so that the **whole projected area is visible**, and do not move it afterwards
(if it moves, recalibrate with `c`).

1. **USB webcam / laptop camera**: `camera.index` in `config.json` (0, 1, ...), or `--camera 1`.
2. **Phone, low latency**: install a "phone as webcam" app that also installs a PC client (e.g. DroidCam or
   Iriun); the phone then appears as a normal camera index on the PC - use `--camera N`.
3. **Phone over Wi-Fi (stream URL)**: install an IP-camera app (e.g. IP Webcam on Android, which typically serves
   `http://<phone-ip>:8080/video`; DroidCam typically uses port 4747). Check the URL **in a browser first**, then run
   `python main.py --hand --source http://<phone-ip>:8080/video` (or put it in `camera.source`). The exact URL depends on
   the app and version - use the one shown in the app. Same Wi-Fi network for phone and PC; 5 GHz is better.
   Wi-Fi streams add 100-300 ms of delay: pointing then feels slightly lagging, so prefer 2 or a USB cable.
4. Landscape orientation, resolution 1280x720 is enough; lock exposure / focus / white balance in the app if it can
   (changing exposure changes skin colour and the detector thresholds).

## Hand mode (what to know)

Pointer = the **tip of the extended index finger**; the arm should enter the board area from a side or from below.
The remote still gives the clicks (Next = left, Previous = right). Optional: *Settings > Hold-to-click* lets you
click without the remote by resting the fingertip on a button for 1.3 s (a ring around the cursor fills up).

First time: **Settings > Learn skin colour** (after calibration): cover the lit square with your open hand and press
NEXT - the skin thresholds are fitted to your hand under the projector light and saved in `config.json`.
If other things are detected (a face in front of the board, wooden furniture) or your hand is missed, learn the
colour again, improve the room lighting, and keep the camera exposure fixed.

## Controls (what the teacher does)

* Point with your finger (or the red dot); the interface shows a glowing cursor with a short trail.
* **Next (left click)**: select a button / pen down-up / grab-drop / place a shape corner.
* **Previous (right click)**: cancel / lift the pen / back one level (menu, page, screen).
* The top bar always shows **X / Y** of the pointer and lights **PREV / NEXT** when a button is received.
* Drawing has no "hold" (the remote cannot hold a button), so everything works with toggling clicks:
  click = pen down, move, click = pen up. Shapes: click first corner, move, click second corner.

## Code layout (one file per functionality)

```
main.py                       entry point and run modes
config.json                   all settings (camera, detection thresholds, key codes, ...)
smartboard/
  app.py  context.py  events.py  config.py
  vision/      camera.py  imgproc.py (own HSV/threshold/morphology/blobs)  detector.py  tracker.py
               calibration.py  pointer_source.py (thread, click stabilisation)  debug_view.py
  remote/      remote_input.py
  graphics/    primitives.py (anti-aliased SDF shapes)  text.py  icons.py  sprite.py  widgets.py
               panels.py  hud.py  theme.py  canvas.py  anim.py
  features/    drawing.py  image_viewer.py  lesson.py  objects.py  overlays.py  timer.py     (logic only)
  screens/     menu.py  menu_tree.py  draw.py  images.py  lesson.py  objects.py  timer.py
               pointer_test.py  calibration.py  navigator.py  base.py                        (one per feature)
tests/  tools/  assets/
```

## Methods (for the report)

**Hand detection (hand mode) - skin segmentation + fingertip.** decimate the frame 3x -> BGR to YCrCb (own code:
`Y = .299R+.587G+.114B`, `Cr = .713(R-Y)+128`, `Cb = .564(B-Y)+128`) -> threshold Cr / Cb / Y (skin box) -> keep the
board region -> 5-of-8 neighbour majority filter -> connected components (own vectorised labelling on a coarse mask)
-> hand blob = right size, close to the previous position -> **fingertip** = the blob pixel farthest from the place where
the arm enters the picture (the pixels touching the border / ROI edge), then sharpened on the full-resolution mask: the
finger axis is the direction from the centroid of the finger body behind the tip to the tip, and the tip is the mean of
the extreme pixels along that axis. Limits: skin-coloured objects and faces in the board area, coloured projector light
that shifts skin colour (the UI avoids orange / yellow fills; *Learn skin colour* adapts the thresholds), very dark or
back-lit scenes, a closed fist or several fingers (the farthest point is then not "the" fingertip).

**Pointer detection - colour-marker segmentation (red dot).** crop a small window around the last
position (full board when lost) -> BGR to HSV (own code) -> threshold: hue near red, saturated, *bright*
-> add the white-saturated core of a strong laser -> restrict to the calibrated board region -> 3x3
majority filter -> connected components -> keep the most dot-like blob (compact, round, bright, close to the
previous position) -> intensity-weighted centroid = sub-pixel position. Limits: other bright red objects,
very bright ambient light, camera auto-exposure. Stabilisation: ROI, shape/brightness scoring, gating on the
previous position, One-Euro filter (smooth when still, little lag when moving), hold of the last position
for a few frames after a miss. The interface never uses red, so the projector cannot create false dots
(`test_no_red_anywhere_in_the_interface` checks every screen).

**Calibration and mapping.** Targets at known board pixels (origin = top-left corner, x right, y down); the
dot is captured at each. A homography H (camera -> board) is estimated with the DLT (SVD). With 9 points a
radial lens distortion k1 is also estimated: `p_u = c + (p - c)(1 + k1 r^2)`, k1 chosen on a grid by
leave-one-out cross-validation and kept only if it clearly lowers the error. Validation: new targets,
the error is shown in board pixels. Saved in `calibration.json`.

**Click stabilisation.** Pressing a remote button shakes the hand a few pixels just before the key event
arrives. The click therefore uses the dot position 0.10 s earlier (`tracking.click_lookback_s`), unless the
pointer moved a lot since (a deliberate fast move). Buttons also accept a 10 px hit margin.

**Threading.** Camera, detection, filtering and mapping run in their own thread, so rendering a 1080p screen
can never delay tracking.

**Remote (both modes).** A clicker is a USB HID keyboard: Next -> Page Down (or Right), Previous -> Page Up (or Left).
The exact codes depend on the model: measure them with `tools/key_finder.py` and write them in `config.json`.
Defaults are provided; `remote.backend = "pynput"` gives a global hook (works without window focus).

**Library use (to justify in the report).** Own NumPy code: colour conversion, thresholding, morphology,
blobs, centroid, filter, homography/DLT, distortion model, all drawing primitives, resize, zoom/pan, overlays.
OpenCV: camera capture, window display, key events, reading/writing image files. Pillow: rasterising the
Inter font to a bitmap (falls back to `cv2.putText`). `np.linalg.svd` solves the DLT system.

## Measured results (simulated camera - NOT yet your hardware)

* Detection + mapping: about 3 ms per frame on a CPU (no GPU needed).
* Simulated oblique camera with barrel distortion (k1 = 0.12): calibration with 4 corners -> 11.9 px mean
  error over the board; 9 points + k1 -> 0.5 px (k1 recovered: 0.125).
* Moving dot (figure-8) on a 1920x1080 board, `tools/trajectory_bench.py`: mean error 1.7 px at ~375 px/s and
  2.4 px at ~970 px/s (very fast); static dot: 0.1 px.
* Hand mode, simulated skin-coloured hand with the same distorted lens (`tools/trajectory_bench.py 5 30 0.4 0.15 1.5 hand`):
  fingertip error 1.6 px static, 2.2 px at ~360 px/s, 2.9 px at ~970 px/s, about 6 ms per frame; lens k1 recovered. Real
  hands are messier than the synthetic one (shadows, background skin tones), so expect larger errors: measure yours with
  Tools > Pointer test.
* 34 automated tests: menus, drawing, zoom, drag & drop, lesson/quiz, timer, overlays, calibration with a
  distorted lens, dwell capture, click stabilisation, threaded tracking, no red or skin-like colour in the UI, hand
  calibration and clicking, skin learning, hold-to-click, pointer mode toggle.

These numbers come from a synthetic camera; real values depend on your camera, lighting and projector.

## Before the demo (on the real setup)

0. Hand mode: fix the camera, run `python main.py --hand`, calibrate by pointing with your index finger, then
   Settings > Learn skin colour.
1. `python tools/key_finder.py`, press Next / Previous, copy the codes into `config.json`.
2. `display.window_x` = x offset of the projector monitor; check the window is fullscreen on it.
3. Lower the camera exposure (`camera.exposure`) so the dot is the brightest red; check the camera window (`d`).
4. Settings > *Dot sensitivity* if the dot is missed (High) or other things are detected (Low).
5. Calibrate (automatic on first start; `c` to redo), then run **Tools > Pointer test** and read the mean error.
6. Replace the placeholder lesson (`assets/lesson/lesson.json`) and images (`assets/images`) with your content.

## GitHub

```bash
git init && git add . && git commit -m "Smart interactive whiteboard"
git branch -M main && git remote add origin <URL> && git push -u origin main
```

`assets/fonts/Inter-*.otf` are under the SIL Open Font License (`Inter-LICENSE.txt`).
