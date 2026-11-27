# Report material - LuminaBoard (about 8 pages, English)

Draft text and figures for the PDF report required by the project specification. Section lengths are suggested page counts.
Replace the items marked **[TO FILL]** with your own measurements. Figures: take screenshots of the app (`F11` hides the sidebar; the
calibration page, the mask view, the menu, a zoomed annotated image, the diagnostics log).

## 1. Introduction and objectives (0.5 page)

LuminaBoard is a camera-based interactive whiteboard. A webcam observes a board; a coloured marker held by the presenter is
detected in every frame, its position is converted from camera pixels to board coordinates with a homography, and a two-button
remote performs a left click (Next) and a right click (Previous) at that position. The screen simulates the projection surface and the
keyboard simulates the remote, until the projector and the physical remote are available. The application offers a free-drawing
whiteboard, interactive menus, image display with zoom and pan, and a teaching mode.

## 2. System architecture (1 page)

```
Camera thread --latest frame--> Vision thread (detect -> track -> map) --Qt signals--> GUI thread
 core/camera.py                  core/vision_engine.py                                   ui/*, tools/drawing.py
```
* **Separation**: acquisition (`core/camera.py`), detection (`core/detector.py`), smoothing (`core/tracker.py`), geometry
  (`core/homography.py`, `core/calibration.py`, `core/coordinate_mapping.py`), interaction logic without Qt (`core/interaction.py`,
  `core/menu_model.py`, `core/remote_control.py`, `core/view_transform.py`, `core/lesson.py`), drawing (`tools/`), and the interface (`ui/`).
* **Threads**: the camera thread only reads frames and keeps the newest one (a one-slot mailbox), so a slow consumer never builds
  latency; the vision thread processes it; results reach the GUI as queued signals. The GUI never waits for the camera.
* **Coordinate systems**: camera pixels -> (H) -> board pixels (1600 x 900) -> widget pixels. The pointer is stored in board
  coordinates; only the last step depends on the window size, so resizing and fullscreen cannot shift it.
* **Extensibility**: the remote is a key filter with configurable bindings (a USB presenter sends PageUp / PageDown, already accepted);
  the projector only changes which window the board is shown on.

## 3. Pointer detection (1.5 pages)

Pipeline (`core/detector.py`, every stage written with NumPy; OpenCV only shrinks the frame):

1. **Shrink** the frame (speed; coordinates are mapped back).
2. **BGR -> HSV** with the explicit formulas: with `V = max(B,G,R)`, `S = 255 (V - min)/V`, and
   `H = 60 * ((G-B)/(V-min) mod 6)` (case R max), `60 * ((B-R)/(V-min) + 2)` (G max), `60 * ((R-G)/(V-min) + 4)` (B max), halved for the OpenCV 0-179 range.
3. **Threshold** each channel inside `[low, high]`; the hue range may wrap around 0 (red).
4. **Opening then closing** with a k x k square, implemented as separable min / max filters (erosion = minimum, dilation = maximum). Opening removes specks, closing fills holes.
5. **Connected components** by run-length labelling with union-find; for each component the area `m00`, first moments `m10, m01`
   and second moments are accumulated analytically from the runs.
6. **Filtering** by area window and a shape-confidence measure; the best component wins.
7. **Centroid** `(cx, cy) = (m10/m00, m01/m00)`, a sub-pixel position. The bounding box comes from the run extents.

**Smoothing and lost-pointer handling** (`core/tracker.py`): `p_t = alpha * m_t + (1 - alpha) * p_(t-1)`. Small alpha is smooth but lags
(time constant `tau = -dt / ln(1 - alpha)`). A measurement far from the current position must repeat for *confirm frames* before it is accepted;
with no measurement the position is held, flagged invalid, for the *lost timeout*, then the pointer is declared lost. The interaction engine lifts the pen as soon as the pointer is not valid.

**Why a colour marker and not MediaPipe**: no model files or extra wheels (Python 3.14 compatibility could not be verified), runs on any webcam,
fully explainable, a deliberate and unambiguous pointer. *Limitations*: needs a colour that is rare in the scene, sensitive to lighting changes
(re-tune or raise sensitivity), similarly coloured objects can be mistaken for the marker, the marker is lost when hidden by the hand or out of view.

## 4. Calibration and coordinate mapping (1.5 pages)

A flat board seen by a camera is related to the ideal rectangle by a homography `[x' y' w']^T = H [x y 1]^T`, board `= (x'/w', y'/w')`.
H has 8 degrees of freedom (scale is arbitrary); each point pair gives 2 equations, hence **four** correspondences, no three collinear.
Each pair contributes the rows `[-x -y -1 0 0 0 ux uy u]` and `[0 0 0 -x -y -1 vx vy v]`; stacking gives `A h = 0`, solved by the SVD
(right singular vector of the smallest singular value). Points are first normalised (Hartley: centroid at the origin, mean distance sqrt 2) for numerical stability (`core/homography.py`).

**Wizard**: capture a frame, click the four corners TL, TR, BR, BL (drag to refine), check the projected grid and the rectified preview, save.
**Validation** (`core/calibration.py`): four finite corners inside the frame, clockwise order, convex, minimum area, no near-collinear triple,
finite and well-conditioned H, zero corner reprojection error, the intersection of the diagonals maps to the board centre, round-trip check.
The JSON file stores corners, camera resolution and mirror flag; H is recomputed on load. A different resolution with the same aspect ratio is rescaled;
a different aspect ratio or mirror flag forces recalibration (the pointer is not mapped rather than mapped wrongly).

## 5. Interaction, remote and menus (1 page)

* **Remote**: Next = left click, Previous = right click at the pointer position (the tracked marker, or the mouse when tracking is off). Default keys Right / Left (+ PageDown / PageUp). Auto-repeat ignored; per-button debounce (250 ms default); keys never steal input from dialogs or text fields.
* **Key diagnostics** (Settings > Remote & Pointer): logs name, Qt key code, Windows virtual-key code and scan code of every key; nothing is executed. **[TO FILL]** the table below with the physical remote's codes:

  | Button | Key name | Qt code | Windows VK | Scan code | Bound to |
  |---|---|---|---|---|---|
  | Right arrow (simulation) | Right | 0x01000014 | 0x27 | 77 (typical) | Next = left click |
  | Left arrow (simulation) | Left | 0x01000012 | 0x25 | 75 (typical) | Previous = right click |
  | Remote "next" **[TO FILL]** | | | | | |
  | Remote "previous" **[TO FILL]** | | | | | |

* **Modes**: Navigation (Next activates the item under the pointer), Drawing (Next = pen down / up, moving draws), Selection (resting on an item for the dwell time, 1.2 s by default, confirms it; a progress ring shows it).
* **Reliability against noisy tracking**: dwell with hysteresis (a jitter of less than 200 ms does not restart the timer), no repeat after firing until the pointer leaves the item, debounce on the remote, pen lifted when the pointer is lost.
* **Menus**: Main -> Drawing (tools, shapes, colours, thickness, undo / redo, clear with confirmation), Image (open, zoom, pan, save), Presentation, Mode, Settings, plus Lesson while presenting. 340 x 84 px targets (board units); usable with mouse, keyboard and pointer.

## 6. Drawing, images and teaching (1 page)

* **Drawing** (`tools/primitives.py`, `tools/drawing.py`): strokes are anti-aliased with a *coverage map* (distance from each pixel to the segment, clamped to a 1-pixel ramp) and composited in NumPy: `out = bg * (1 - a) + ink * a`. Undo / redo store only the changed region. 8 colours + custom, thickness 1-40 px.
* **Image viewer** (`core/view_transform.py`): `screen = content * zoom + offset`, 1x-8x, zoom keeps the point under the cursor fixed (`offset' = anchor - (anchor - offset) * z'/z`), the content always covers the board, aspect ratio preserved (`scale = min(W/w, H/h)`). Annotations are stored in content coordinates, so they stay on the image; the original full-resolution image is drawn when zoomed.
* **Teaching mode** (`core/lesson.py`): a lesson is a JSON list of pages (title, text, image, notes); the demo lesson "How a camera becomes a pointer" has 7 pages; Previous / Next controls on the board work with mouse, remote and dwell; notes are kept per page.
* **Sessions**: `.lumina` files (compressed NumPy archive, no pickle) store drawing, image and view.

## 7. Testing and results (1 page)

265 automated tests pass (3 more need a real webcam); full list in `docs/TEST_RESULTS.md`. Synthetic images (a board seen in perspective with a marker at a known position) allow the whole chain to be checked against ground truth without a camera.

Measured with `python -m tools.benchmark` (300 synthetic frames 640 x 360, random marker positions, noise sigma 3; Python 3.13, Linux sandbox):

| Metric | Value |
|---|---|
| Marker found | 300 / 300 |
| Board error, mean / median / 95th percentile / max | 2.07 / 2.14 / 3.56 / 4.19 px (board 1600 x 900) |
| Detection time, mean (95th percentile) | 6.6 ms (7.7 ms), about 150 frames/s |

**[TO FILL]** on the laptop: `python -m pytest tests\test_camera_live.py -s -v` prints the real resolution, camera FPS, tracking FPS and processing time; add them here, with a note of the lighting and the marker used. Robustness tests: camera unavailable, pointer lost, invalid / degenerate calibration, invalid or corrupt image / lesson / session files, application reset, repeated remote events.

## 8. Use of predefined functions - justification (0.5 page)

| Function | Where | Why it is acceptable |
|---|---|---|
| `cv2.VideoCapture`, `cv2.flip` | `core/camera.py` | camera access is hardware / driver work; mirror is a trivial index reversal |
| `cv2.resize` | `core/detector.py`, `tools/image_tools.py` | resampling for speed and for fitting images; not part of the algorithms to be demonstrated |
| `cv2.imdecode`, `cv2.imencode`, `cv2.imwrite`, `cv2.convertScaleAbs`, `cv2.cvtColor` (gray to BGR) | `tools/image_tools.py` | file formats (Unicode paths on Windows) and bit-depth normalisation of imported images |
| `cv2.warpPerspective` | `ui/calibration_page.py` | only the *preview* of the rectified board; the matrix H is our own |
| `cv2.getPerspectiveTransform`, `cv2.cvtColor` (BGR -> HSV), OpenCV morphology | tests only | independent references to validate our implementations |
| NumPy `linalg.svd` | `core/homography.py` | numerical linear algebra primitive; the DLT system and the normalisation are ours |

Everything else - HSV conversion, thresholding, morphology, components, moments, centroid, smoothing, homography, coordinate mapping, drawing primitives, compositing, zoom / pan - is implemented in the project.

## 9. Conclusion and perspectives (0.5 page)

All required functions are implemented and tested. Perspectives: automatic corner detection, MediaPipe hand tracking as an optional back end, a projector window, the physical remote, a second marker for a two-pointer interaction, adaptive colour tracking against lighting drift.
Known limits to state honestly: colour-marker sensitivity to lighting, single-pointer only, the application was developed and tested on Python 3.13 / Linux headless; **[TO FILL]** the Windows 3.14 test results.

## Appendix - requirement traceability

See `docs/REQUIREMENTS_MATRIX.md`.
