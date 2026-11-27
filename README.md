# Smart Interactive Whiteboard

A computer-vision project that turns a conventional whiteboard into an
interactive teaching surface.  A camera tracks a coloured marker (or your
hand-held pointer) and a two-button presentation remote (or keyboard
simulation) controls a Pygame interface projected on the board.

## Main features

- **Camera acquisition** — configurable webcam or simulated source, FPS
  monitoring, graceful failure handling.
- **Marker detection** — manual HSV conversion, thresholding, morphology
  and blob analysis implemented with NumPy; centroid tracking with EMA
  smoothing, jump rejection and loss handling.
- **Board calibration** — four-corner perspective calibration with a
  homography solved manually (DLT, NumPy).
- **Two-button remote** — physical HID remote via `pynput` (global
  listener) or keyboard simulation (Z / X), same event interface.
- **Pygame interface** — main menu with submenus (Whiteboard, Setup),
  lesson viewer, freehand drawing on blank / grid / dark boards with
  undo/redo/save, image gallery with zoom and pan, settings, calibration
  and help screens.  Windowed or fullscreen.
- **Smooth pointer** — camera capture and marker detection run on their
  own threads, so the interface stays at 60 fps.
- **Extra features** — HSV auto-calibration by colour sampling (with a live
  preview), corner-order validation, click feedback rings, undo/redo for
  drawings, PNG export of the board.

## Requirements

- Windows, Python 3.11+ (tkinter is optional: only the *Browse...* button uses it)
- Dependencies: `numpy`, `opencv-python`, `pygame`, `pynput`, `pytest`

## Installation

```powershell
pip install -r requirements.txt
```

## Running

```powershell
python main.py
```

Diagnostic tools (optional):

```powershell
python tools/check_env.py        # verify environment + camera
python tools/camera_viewer.py    # live camera + detection overlay
python tools/camera_viewer.py --sim   # simulated camera source
python tools/remote_key_detector.py   # discover your remote's key names
```

## First-time setup

1. **Launch** `python main.py`.  The app starts in *auto* pointer mode:
   it uses the camera marker when visible and falls back to the mouse.
2. **Calibrate the board**: Main Menu → *Calibration*.  The live camera
   image is shown; click the four whiteboard corners in the order
   **Top-Left, Top-Right, Bottom-Right, Bottom-Left**, then press *Save*.
3. **Check marker detection**: hold a bright green/magenta marker in front
   of the camera — a blue ring pointer should appear.  If not, open
   *Settings → Marker Color Calib* and press *Sample* with the marker in
   the centre of the view, then *Apply*.

## Controls

| Action | Physical remote | Keyboard simulation |
|---|---|---|
| Left click (select) | Button 1 | `Z` |
| Right click (back)  | Button 2 | `X` |

**Right click = go back one step**, on every screen: up one menu level,
previous lesson page, undo the last stroke, zoom out, undo a calibration
point.  **Left click = select / activate**.  The *Back* (top left) and
*Home* (top right) buttons are on every screen, and `Esc` goes back.

On the lesson, a left click *anywhere* shows the next page, so you never
have to aim at a button.  A ring flashes at the pointer on each click.

## Configuration (`config/settings.json`)

Everything is editable in the in-app *Settings* screen or directly in the
JSON file:

- `camera_source`: `"real"` or `"simulated"`
- `pointer_mode`: `"auto"` (camera with mouse fallback), `"camera"`, `"mouse"`
- `remote_mode`: `"auto"`, `"physical"`, `"keyboard"`
- `remote_keys.left/right`: key names your remote sends
  (find them with `tools/remote_key_detector.py`; common values are
  `page_down` / `page_up`)
- `sim_keys.left/right`: default `z` / `x`
- `marker_hsv`: HSV thresholds for the marker colour
- `tracking_alpha`, `tracking_max_jump`, `tracking_loss_timeout`
- `display_width`, `display_height`, `fullscreen`

Display-size and fullscreen changes apply after *Restart App* in Settings.

## Projector setup

1. Connect the projector; Windows should mirror or extend the display.
2. In *Settings*, choose the matching display preset and enable
   *Fullscreen*, then *Restart App*.
3. If the projector is a second display, set Windows to duplicate the
   laptop screen (Win+P → Duplicate) so the board shows the interface.

## Whiteboard (drawing)

Main menu -> *Whiteboard* -> choose *Blank*, *Grid* or *Dark* board.

- **Left click on the board** puts the pen **down**; move the marker to
  draw; click again to lift the pen.  Leaving the board or losing the
  marker lifts it automatically, so ink never appears by surprise.
- **Right click** lifts the pen and **undoes** the last stroke.
- Toolbar: 4 colours, 4 thicknesses, Undo, Redo, **Clear** (click twice to
  confirm) and **Save** (PNG of the board with strokes, in `output/`).
- On the dark board the black pen becomes white.

## Images

Put pictures in `assets/images/` and they appear in the gallery (three
teaching images are included; regenerate them with
`python tools/make_sample_images.py`).  *Browse...* opens the system file
dialog if tkinter is available.  *Zoom +/-* and the arrows change the view,
a click on the image centres the view there, *Fit* resets, and a right
click steps back (zoom out, then back to the gallery).

## Tests

```powershell
python -m pytest tests -q
```

See `docs/testing.md` for methodology and known limitations.

## Project structure

```
smart_whiteboard/
├── main.py                  # single entry point
├── config/                  # settings.py, settings.json, calibration.json
├── camera/                  # webcam + simulated camera
├── detection/               # HSV segmentation, blobs, tracker
├── calibration/             # homography + calibration screens
├── interaction/             # remote listener, keyboard sim, events
├── interface/               # Pygame app, screens, drawing, viewer
├── simulation/              # fake camera, mouse pointer
├── utils/                   # manual NumPy image processing & geometry
├── assets/images/           # gallery pictures (sample images included)
├── tools/                   # camera viewer, remote detector, env check,
│                            # sample-image generator
├── tests/                   # pytest suite
└── docs/                    # algorithms.md, testing.md, report.md
```

## Troubleshooting

- **"CAM ERR" in the status bar** — webcam busy or unavailable; switch
  `camera_source` to `"simulated"` in Settings to keep developing.
- **Pointer stuck on mouse** — set `pointer_mode` to `"camera"` once the
  marker is calibrated, or keep `"auto"`.
- **Remote buttons do nothing** — run `tools/remote_key_detector.py`,
  press the buttons, and copy the printed key names into
  `remote_keys.left/right` in Settings.
- **Calibration says the corners are invalid** — click them in the order
  top-left, top-right, bottom-right, bottom-left, as they appear on screen.
- **Pointer feels laggy** — check the `CAM ..fps` value in the status bar;
  a webcam that only delivers a few fps in low light is the usual cause.
- **Detection flickers** — increase `tracking_alpha` smoothing or widen
  the HSV ranges slightly in Settings.
- **Clicks repeat while held** — this is already debounced; if your remote
  sends key *repeat* events, map it to keys that do not auto-repeat.
