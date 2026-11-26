# LuminaBoard - Smart Interactive Whiteboard

USTHB Computer Vision project 2026-2027 (Python + OpenCV + NumPy + PySide6).
A camera-based interactive whiteboard: a webcam tracks a coloured marker, a homography maps it onto the
board, two remote buttons (simulated by the arrow keys) will trigger left/right clicks.

**Status: Phases 1-6 are complete** - environment, interface, threaded camera + diagnostics, the computer-vision
engine (marker detection, tracking, four-point calibration, coordinate mapping), and now pointer interaction:
the two-button remote (keyboard simulation), Navigation / Drawing / Selection modes, the pointer-driven menus and the
key-diagnostics tool.
Phase 6 added the image viewer (zoom / pan / fit with annotation on the image), Teaching Mode (editable lessons, page
navigation on the board, a ready-made demo lesson) and the interface settings. Remaining: report material and polish (Phase 7).

## Install and run (Windows 11, PowerShell)

```powershell
cd smart_whiteboard
py --list                                  # check that 3.14 is listed
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1                                # creates .venv, installs everything, runs tests + smoke test
.\.venv\Scripts\python.exe main.py         # start the application
```

Manual alternative:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python main.py --smoke                     # headless launch check
python main.py                             # start the application
```

### Tests

```powershell
python -m pytest tests -q                              # everything (synthetic images + fake camera + GUI), ~25 s
python -m pytest tests/test_detection.py -v            # detector on synthetic images
python -m pytest tests/test_calibration.py tests/test_mapping.py -v
python -m pytest tests/test_camera_live.py -s -v       # REAL webcam (skipped when none is found); close Teams/Zoom first
```

`tests/synthetic.py` renders a board seen under perspective with a coloured marker at a known board position,
so the whole chain (detect -> smooth -> homography -> board coordinates -> pointer on the canvas) is checked
against ground truth without a webcam. `test_camera_live.py` runs the same chain on real frames and prints
resolution, camera FPS, tracking FPS and processing time.

### Dependency compatibility (Windows x64, Python 3.14)

| Package | Version | Wheel | Note |
|---|---|---|---|
| PySide6 | >= 6.8 (6.12) | `cp310-abi3-win_amd64` | stable ABI, works on 3.14 |
| opencv-python | 4.x (4.14) | `cp37-abi3-win_amd64` | pinned `<5`: 5.x is a new major release not validated here |
| numpy | >= 2.1 (2.5) | `cp314-win_amd64` | native 3.14 wheel |
| Pillow | >= 11 (13) | `cp314-win_amd64` | native 3.14 wheel |
| mediapipe | optional | - | **not used**: see "Detection method" below |

Install only `opencv-python` (never together with `opencv-contrib-python` / `-headless`).
The development and test runs for this delivery were done on Python 3.13 / Linux (headless Qt); the wheel
availability for 3.14 was checked, but the application has not been executed on a 3.14 interpreter by the author.

## First-time setup of the camera pointer (about 3 minutes)

1. **Marker** - use something with a saturated colour that is unusual in your room: a green or pink
   highlighter cap, a sticky-note tip, a coloured LED ball. Matte works best (glossy surfaces create highlights).
2. **Settings > Detection** - hold the marker in view and *click it in the live image*. The binary mask on the
   right must show it as one solid white blob and (almost) nothing else. Adjust *Sensitivity* or the HSV sliders;
   presets exist for green, blue, red (wrapped hue), yellow, orange and pink. Everything saves automatically.
3. **Calibration** - frame the whole board, press *Capture frame* (Space), click the four corners in the order
   Top-left, Top-right, Bottom-right, Bottom-left (drag to refine, right-click removes the last one), check that the
   projected grid follows the board, then *Save calibration*. Move the marker: the mini-map and the rectified
   preview show where the system thinks it is.
4. **Whiteboard** - press *Track* (or `K`). The pointer appears on the board; the chip shows
   *Tracking / Searching / Pointer lost / Outside the board / Not calibrated*.

The simulated "projection surface" is the computer screen: you can calibrate on any rectangular board in front of
the camera, e.g. a sheet of paper, and the app maps the marker onto the on-screen board.

## Remote control, modes and menus (Phase 5)

### The two-button remote

The physical remote does not exist yet, so two keys simulate it. They act **on the Whiteboard page only** (elsewhere the
arrow keys keep their normal meaning) and never while a dialog or a text field has focus.

| Remote button | Default keys | Action | Where |
|---|---|---|---|
| **Next** | `Right`, `PageDown` | **left click** | at the current pointer position |
| **Previous** | `Left`, `PageUp` | **right click** | at the current pointer position |

*Current pointer position* = the tracked marker when **Track** is on, otherwise the mouse cursor over the board
(so everything can be rehearsed without a camera). A click is shown as an expanding ring with a "Left click" /
"Right click" label. Holding a key (auto-repeat) is ignored, and a second press of the same button within the
**debounce** time (default 250 ms, Settings > Remote & Pointer) is dropped; Next and Previous are debounced independently.
Right mouse button = Previous.

What the clicks do depends on the mode (buttons above the board, or keys `1` `2` `3`):

| Mode | Pointer movement | Next (left click) | Previous (right click) |
|---|---|---|---|
| **Navigation** `1` | highlights the menu item under it | activates the highlighted item | back: up one menu level / open or close the menu |
| **Drawing** `2` | draws while the pen is down | on empty board: pen down / pen up at the pointer; on a menu item: activates it | lifts the pen; otherwise back |
| **Selection** `3` | resting on an item fills a progress ring; after the **dwell time** (1.2 s, adjustable) it is confirmed | confirms at once | back |

Safety rules: the pen is lifted automatically when the marker is lost, leaves the board, tracking is switched off, the
mode changes or the page is left; a stroke that was started is committed (never discarded). After a dwell
confirmation the same item cannot fire again until the pointer leaves it; a brief jitter off an item (< 200 ms) does not
restart the timer.

### Menus

`M`, the **Menu** button, or Previous (right click) with nothing else to cancel opens the menu painted on the board. Entries
are 340 x 84 board pixels (large targets for a shaky pointer) and work with the mouse, the keyboard (`Up` / `Down` /
`Enter` / `Backspace` / `Esc`) and the tracked pointer.

```
Menu
 +- Drawing      Pen, Eraser, Shapes > (Line, Rectangle, Circle), Text, Colours > (8), Thickness > (3 presets, +, -),
 |               Undo, Redo, Clear board > (confirmation: Yes / Cancel)
 +- Image        Open image..., Remove image, Save as PNG...
 +- Presentation Fullscreen, Show pointer, Home screen
 +- Mode         Navigation, Drawing, Selection
 +- Settings     Camera pointer, Calibration, Detection settings, Remote and keys, Reset whiteboard > (confirmation)
 +- Close menu
```
Check marks show the current tool, colour, thickness, mode and switches. Destructive actions (clear, reset) are
confirmed *inside* the menu, so they can be answered with the pointer alone. (Zoom / pan items are in the Image submenu; while a
lesson is presented a **Lesson** entry (page navigation, clear notes, leave) appears at the top of the main menu.)

### Finding the real remote's key codes (key diagnostics)

1. Plug in the remote's receiver. Open **Settings > Remote & Pointer > Key diagnostics** and press *Start diagnostics*.
2. Press each remote button. For every key the log shows the Qt name, the Qt key code, the **Windows virtual-key code**,
   the scan code and which button it is currently bound to; nothing is executed. The "Distinct keys" table under the log
   is what goes into the report. *Save log...* writes it to a text file.
3. Click **Change key...** (replace) or **Add key...** (extra key) next to Next / Previous and press the remote button.
   Bindings are saved in `config/settings.json`; a key cannot be bound to both buttons; *Restore default keys* undoes it.

Reference codes of the simulation keys (Windows): `Right` VK 0x27, `Left` VK 0x25, `PageDown` VK 0x22, `PageUp` VK 0x21
(Qt codes 0x01000014, 0x01000012, 0x01000017, 0x01000016). **The codes of the physical remote must be read on the
lecture-room PC with the diagnostics above and written into the report** - they are unknown until the remote is available;
presentation clickers normally send PageDown / PageUp, which are already accepted.

## Image viewer: zoom, pan, annotate (Phase 6)

Open an image (Home, `Ctrl+O`, or Menu > Image). It is fitted to the board with its aspect ratio kept; then:

| Action | Mouse / keyboard | Menu / buttons |
|---|---|---|
| Zoom in / out (1x to 8x, around the cursor) | wheel, `+` / `-` | Menu > Image > Zoom in / out, `-` `+` buttons under the board |
| Back to the whole board | `0` | Fit |
| Pan | middle-button drag, `Ctrl+Arrows` | **Pan** toggle: then drag with the left button *or the tracked marker* (Drawing mode: Next = grab / release); Menu > Image > Move view |

Zoom and pan are a transform of the board content (`core/view_transform.py`, formulas in its docstring):
`screen = content * zoom + offset`, clamped so the content always covers the board. The menu, the pointer and the click rings
stay in screen coordinates, while drawing is converted to content coordinates, so **annotations stay glued to the image**
at any zoom. When zoomed, the original full-resolution picture is drawn (not the 1600 x 900 copy), so details stay sharp.

## Teaching mode (Phase 6)

Sidebar > **Teaching**: a lesson is an ordered list of pages (title, text, optional picture, speaker notes), stored as a
JSON file (`data/lessons/*.json`, pictures relative to the file).

* **Editor**: page list (add / duplicate / move / delete - a lesson always keeps one page), text with a tiny format
  (`- bullet`, `> highlighted formula`, plain paragraph), picture chooser (a missing picture is flagged and shown as a
  placeholder, not a crash), live preview, New / Open / Save / Save as. Closing with unsaved changes asks Save / Discard / Cancel;
  a corrupt file is reported and the current lesson is kept.
* **Demo lesson** ("How a camera becomes a pointer", 7 pages: pixels, HSV, finding the marker, homography, smoothing,
  an exercise). It is generated by `python -m tools.make_demo_lesson` (pictures drawn with NumPy/OpenCV). It is built in:
  *Save* on it asks for a new file.
* **Presenting**: *Present from start / from this page* shows each page on the board. **Previous / Next** buttons and the
  page number sit at the bottom of the board and work like menu items: mouse, remote left click on the pointer (Navigation
  mode), dwell (Selection mode). Everything drawn on a page (pen, shapes, text, zoom) stays on that page while the lesson
  is open - go Next and Previous to check; undo history is per page visit. Menu > Lesson: previous / next / first / last
  page, clear this page's notes (confirmed), leave the lesson (confirmed). Pictures and Home navigation stay available;
  replacing the board image is blocked during a lesson.

## Interface settings

Settings > General > Interface: show / hide the mode-pen-pointer status pill, show / hide the click rings, menu size
(80 - 130 %; the menu re-flows so it always fits above the page controls).

## Shortcuts

| Action | Shortcut |
|---|---|
| Pen / Eraser / Line / Rectangle / Circle / Text | `P` `E` `L` `R` `C` `T` |
| Camera pointer on/off | `K` |
| Menu open/close | `M` (`Esc` closes it) |
| Mode: Navigation / Drawing / Selection | `1` `2` `3` |
| Menu keyboard | `Up` `Down` `Enter` `Backspace` |
| Zoom in / out / fit | `+` `-` `0` (wheel zooms at the cursor) |
| Pan the view | `Ctrl+Arrows`, middle mouse button, Pan toggle |
| Remote: Next = left click / Previous = right click | `Right` or `PageDown` / `Left` or `PageUp` (whiteboard only) |
| Thickness - / + | `[` `]` |
| Undo / Redo | `Ctrl+Z` / `Ctrl+Y` |
| Clear (asks for confirmation) | `Ctrl+Del` |
| Reset whiteboard | `Ctrl+Shift+R` |
| Open image / Save PNG | `Ctrl+O` / `Ctrl+S` |
| Home / Whiteboard | `Ctrl+H` or `Ctrl+1` / `Ctrl+2` |
| Fullscreen / Exit | `F11` / `Esc` |
| Capture frame (calibration) | `Space` |

The camera is opened only when a camera page (Camera, Calibration, Settings) or *Track* needs it, and released
20 s after it is no longer needed. *Stop camera* on the Camera page is respected by the other pages.

## Architecture

```
main.py                    entry point (--smoke = headless launch check)
config/settings.json       persistent settings          config/calibration.json   saved calibration
core/settings.py           JSON settings (atomic save, merged over defaults), recent files
core/app_state.py          Qt signals: camera / tracking / calibration status
core/camera.py             CameraWorker thread (reads frames) + FrameMailbox + camera scanner
core/detector.py           HSV colour-marker detector - every stage written in NumPy
core/tracker.py            exponential smoothing, jump rejection, lost-pointer handling
core/homography.py         DLT homography with Hartley normalisation (NumPy SVD)
core/calibration.py        four-corner calibration: validation, JSON persistence, resolution check
core/coordinate_mapping.py camera -> board -> canvas conversions, boundary handling
core/vision_engine.py      VisionWorker thread (detect -> track -> map) + VisionController (GUI side)
core/remote_control.py     RemoteMapper (debounce), KeyLog, RemoteController (application-wide key filter)
core/interaction.py        modes, dwell selector, InteractionEngine (pointer + clicks -> pen/menu commands)
core/menu_model.py         menu tree, navigation state, board-space layout and hit-testing
core/view_transform.py     zoom / pan transform of the board content
core/lesson.py             lesson model (pages, JSON persistence), presenting session, page-control geometry
tools/primitives.py        NumPy anti-aliased line + circle coverage maps, alpha compositing
tools/drawing.py           layered canvas, pen/eraser/shapes/text, patch-based undo/redo
tools/image_tools.py       Unicode-safe image I/O, aspect-ratio fitting
ui/main_window.py          sidebar, pages, camera lifecycle, fullscreen, reset
ui/dashboard.py            home                          ui/whiteboard.py + toolbar.py   board, tools, pointer overlay
ui/camera_page.py          diagnostics                   ui/calibration_page.py          calibration wizard
ui/settings_page.py        HSV tuning panel + options    ui/video_view.py                live view with overlays
ui/pointer_menu.py         paints the on-board menu, click ripples, mode HUD
ui/teaching_page.py        lesson editor / library        ui/lesson_render.py   draws a lesson page as an image
tools/make_demo_lesson.py  generates data/lessons/demo_lesson.json + pictures
ui/remote_panel.py         Settings > Remote & Pointer: key binding, debounce, dwell, key diagnostics
ui/styles.py icons.py brand.py widgets.py    visual identity
tests/                     256 tests (+3 that need a real webcam)
```

Threads: **camera thread** (reads frames, keeps only the latest) -> **vision thread** (detect, track, map) ->
queued Qt signals -> **GUI thread**. No thread other than the GUI touches a widget, and the GUI never waits for
the camera.

## Algorithms (full derivations are in the module docstrings)

**Detection pipeline** (`core/detector.py`): shrink the frame (speed) -> BGR to HSV with the explicit formulas
-> per-channel threshold (hue range may wrap around 0 for red) -> binary opening then closing with a k x k
square, implemented as separable min/max filters -> connected components via run-length labelling + union-find
-> area, centroid and second moments computed analytically from the runs -> reject blobs outside the area window
or with low shape confidence -> best remaining blob -> centroid `(m10/m00, m01/m00)` mapped back to camera pixels.
OpenCV is used only to resize the frame; `tests/test_detection.py` cross-checks the NumPy HSV conversion and
morphology against OpenCV.

**Smoothing** (`core/tracker.py`): `p_t = alpha * m_t + (1 - alpha) * p_(t-1)`, `0 < alpha <= 1`. `alpha = 1` is the
raw measurement; small alpha is smooth but laggy (time constant `tau = -dt / ln(1 - alpha)`). A measurement
far from the current position must repeat for *confirm frames* before it is accepted (kills single-frame outliers);
with no measurement the last position is held for the *lost timeout* but flagged invalid, then the pointer is
declared lost and nothing stale is ever shown as valid.

**Homography** (`core/homography.py`): a flat board seen by a camera is related to the ideal rectangle by
`[x' y' 1]^T ~ H [x y 1]^T`; the result is normalised by its third component. H has 8 degrees of freedom and each
point pair gives 2 equations, hence exactly **four** correspondences (no three collinear). Each pair gives
`-x -y -1 0 0 0 ux uy u` and `0 0 0 -x -y -1 vx vy v`; stacking them gives `A h = 0`, solved by the SVD (right singular
vector of the smallest singular value), after Hartley normalisation of both point sets for numerical stability.
`cv2.getPerspectiveTransform` solves the same system and is used in the tests as a reference.

**Calibration validation** (`core/calibration.py`): four finite corners, inside the frame, clockwise TL-TR-BR-BL,
convex, minimum area, no near-collinear triple, finite and well-conditioned H, zero corner reprojection error, the
intersection of the diagonals must map to the board centre, and a round-trip check. The file stores corners, camera
resolution and mirror flag; H is recomputed on load, so a corrupted file cannot inject a bad matrix. If the camera
resolution changes with the same aspect ratio, points are rescaled; with a different aspect ratio (or mirror flag)
the app asks you to recalibrate and does not map the pointer.

**Coordinates** (`core/coordinate_mapping.py`): camera pixels -> (H) -> board pixels -> (scale + offset) -> widget
pixels. The pointer is stored in *board* coordinates; only the last step depends on the window size, so it stays
correct when the window is resized or fullscreen is toggled. Points slightly outside the board are clamped; further
away they are rejected ("Outside the board").

## Detection method: advantages and limitations

The app always uses the OpenCV/NumPy **HSV colour-marker** tracker. MediaPipe hand tracking is not integrated: it
needs a separate model file and a Python 3.14 build that could not be verified, and the colour marker is the
fallback your specification asks for. The Settings page tells you whether MediaPipe happens to be installed.

*Advantages*: very fast (50+ FPS here on 640x360 synthetic frames), no model files, works on any webcam, fully
explainable step by step, precise sub-pixel centroid, and the marker gives a deliberate, unambiguous pointer
(a hand would also trigger by accident).

*Limitations*: needs a marker whose colour is rare in the scene; sensitive to lighting changes (re-tune or raise
*Sensitivity*); similarly coloured objects can be mistaken for the marker; a marker hidden behind the hand or
leaving the view is lost (the app reports it instead of guessing); it cannot tell a "click" from a "move" by itself -
clicks come from the remote keys (see "Remote control").

## Whiteboard

Pen, eraser, line, rectangle, circle (from its centre), text, 8 colours + custom, thickness slider, undo/redo
(stores only the changed region), clear with confirmation, save as PNG, open an image behind the drawing, fullscreen.
Strokes are anti-aliased and composited in NumPy (`tools/primitives.py`). The canvas takes board coordinates through
`pointer_down / pointer_move / pointer_up`, so the mouse and the tracked pointer (via the interaction engine) drive it the same way.

## Roadmap

1. Environment and project setup - done
2. Interface (dashboard, navigation, whiteboard, toolbars) - done
3. Threaded camera acquisition, diagnostics, reconnection - done
4. Marker detection, tracking, calibration wizard, homography, mapping, HSV tuning - done
5. Pointer interaction (draw with the marker, navigation/drawing/selection modes, dwell-confirmed selection), two-button remote via keyboard with key diagnostics, pointer-driven menus - done
6. Image viewer with zoom/pan, teaching mode with demo lesson, interface settings - done
7. Report material and polish
