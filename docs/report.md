# Smart Interactive Whiteboard — Project Report

*Computer Vision course project — draft, ~8 pages.*

> **Note on measurements.** Any value that requires physical hardware
> (camera FPS, detection latency, remote key codes, projector behaviour)
> is marked **[HARDWARE TEST REQUIRED]** and was *not* measured in the
> development environment (laptop only, no projector, no remote).

---

## 1. Introduction and objectives

Conventional whiteboards are passive: a teacher writes or projects content
but cannot interact with it directly.  This project transforms a whiteboard
into an **interactive surface** using only a camera and a cheap
two-button presentation remote.

**Objectives**

1. Detect the position of a coloured pointer/marker in a webcam image.
2. Map camera coordinates to board coordinates via perspective
   calibration (homography).
3. Provide a smooth, jitter-free on-screen pointer.
4. Control a Pygame interface (menus, lesson, drawing, image viewer)
   with a two-button remote — or a keyboard simulation when no remote
   is available.
5. Implement the essential computer-vision operations **manually with
   NumPy** so the system is academically defensible, not just a wrapper
   around library calls.

## 2. System description and architecture

The system is a single Python application (`python main.py`) organised in
layers:

```
camera frame ──► HSV segmentation ──► blob analysis ──► centroid
      │                                                    │
      │                                            homography (DLT)
      │                                                    │
      │                                            tracker (EMA)
      │                                                    │
      ▼                                                    ▼
 simulated camera                              board-space pointer
                                                          │
 remote (pynput) / keyboard sim ──► EventManager ──► click events
                                                          │
                                                          ▼
                                              Pygame screens (UI)
```

Modules: `camera/` (acquisition), `detection/` (segmentation, components,
tracker), `calibration/` (homography + calibration UI), `interaction/`
(remote + keyboard sim), `interface/` (Pygame app and screens),
`simulation/` (fake camera, mouse pointer), `utils/` (manual NumPy
primitives), `tools/` (diagnostics), `tests/` (pytest suite).

Three threads keep the interface fluid.  A *grabber* thread reads the
camera and always keeps only the latest frame.  A *detection worker*
thread runs the marker detection on that latest frame (frames are skipped,
never queued, so the pointer cannot lag behind reality).  The *UI thread*
runs at the display refresh rate (60 fps cap): each frame it takes the
newest detection, maps it through the homography, smooths it with the
tracker and draws.  Measured on the simulated camera, detection costs
about 100 ms per 720p frame when run naively on the UI thread, about
20 ms after sub-sampling the image to ~640 px width (centroid within 1 px),
and no longer blocks the UI at all because it runs on the worker thread.

## 3. Hardware and software environment

| Item | Development setup | Target setup |
|---|---|---|
| OS | Windows 11 | Windows |
| Python | 3.11.9 | 3.11 |
| Libraries | NumPy 2.x, OpenCV 5.x, Pygame 2.6, pynput 1.8, pytest 7.4 | same |
| Camera | laptop webcam (also simulated source) | webcam facing the board |
| Display | laptop screen (windowed) | projector, fullscreen |
| Remote | keyboard simulation (Z/X) | 2-button HID remote |

## 4. Camera calibration and coordinate systems

Three coordinate systems are used:

1. **Camera pixels** — the raw frame, e.g. 1280×720.
2. **Board coordinates** — the logical whiteboard, defined as the
   application window size (e.g. 1280×720).
3. **Screen pixels** — identical to board coordinates by design, so the
   pointer can be drawn directly.

**Calibration procedure.** The teacher opens *Calibration*, sees the live
camera image, and clicks the four physical board corners in the order
Top-Left, Top-Right, Bottom-Right, Bottom-Left.  These four camera points
are associated with the four corners of the board rectangle.  A homography
`H` is computed with a **direct linear transform solved manually in
NumPy**: each correspondence yields two linear equations; fixing `h33 = 1`
gives an 8×8 system solved by `np.linalg.solve`.  The result is validated
(distinct, non-collinear points, sufficient area) and stored in
`config/calibration.json` together with the clicked points, so it can be
reloaded at startup and recalibrated at any time.

**Validation.** Unit tests verify that the four clicked corners map
exactly onto the board corners and that the quad centre maps near the
board centre.  Points outside the board are still transformed (the UI
simply clips rendering); degenerate clicks are rejected with a message.

## 5. Pointer detection method and limitations

**Pipeline** (each stage manual unless noted):

1. **BGR → HSV** — vectorised NumPy implementation of the standard
   algorithm; hue in degrees, saturation/value in [0,1].
2. **HSV thresholding** — boolean mask inside a configurable HSV box,
   with hue wrap-around support (e.g. reds near 0°/360°).
3. **Morphology** — binary opening (erosion then dilation) implemented
   as AND/OR combinations of shifted mask copies; removes speckle noise.
4. **Connected components** — labelling via `cv2.connectedComponents`
   (justified: efficient CCL is impractical in pure Python at 720p);
   **area, centroid and bounding box are computed manually** with
   `np.bincount` weighted by coordinate grids and `np.nonzero`.
5. **Blob selection** — area filtering (min area, max area ratio) and
   selection of the largest remaining blob; its centroid is the pointer.

**Tracking.** An exponential moving average (`α = 0.45`) smooths the
position; single-frame jumps beyond `max_jump` px are rejected (a second
consecutive far sample is accepted as a real teleport); a lost marker
keeps the last position for `loss_timeout` seconds before the pointer is
hidden.

**Limitations.** Colour-based detection is sensitive to lighting and to
backgrounds containing similar hues; the HSV auto-calibration tool
mitigates this.  Only one marker is tracked (the largest blob).  Occlusion
or very fast motion can cause brief pointer loss.  Real-camera accuracy
and latency are **[HARDWARE TEST REQUIRED]**.

## 6. Remote-button detection and click mapping

Presentation remotes are HID keyboards: each button emits a key press
(often Page_Up/Page_Down, but model-dependent).  The app uses `pynput`'s
global `keyboard.Listener` on a daemon thread; key names are normalised
and mapped through `remote_keys.left/right` in `config/settings.json`.
Events are debounced (no auto-repeat while held) and pushed through a
thread-safe queue drained once per frame.

A diagnostic tool (`tools/remote_key_detector.py`) prints every key name
the remote sends so the correct names can be configured.  The detected
key codes for the author's remote are **[HARDWARE TEST REQUIRED]**.

**Simulation fallback.** `Z` = left click, `X` = right click (configurable
via `sim_keys`), handled inside the Pygame event loop.  Both paths feed
the same `EventManager`, so switching modes needs no code changes.

Clicks are dispatched to the current screen together with the current
pointer position: left click activates/selects, right click performs the
secondary action (usually "back").

## 7. Interface, menus, drawing, image display and zoom

The Pygame interface uses a dark, high-contrast theme with large buttons
suited to a projected board.  Every screen is laid out from the same
geometry constants (header 72 px, toolbar 84 px, status bar 28 px) and
button rows are placed by a helper that shrinks them proportionally rather
than overflowing, so nothing can be hidden or pushed off the window at any
display size (this is covered by an automated test at four resolutions).
Each screen has a *Back* button (top left) and a *Home* button (top right).
The pointer is a two-tone ring so it stays visible on light and dark boards,
and every click triggers an expanding ring at the pointer position, which
gives visual feedback for the remote buttons.  A status bar shows the
current screen, camera state and fps, calibration state, input source and
pointer status.

**Click convention (identical on every screen):** *left click* = select /
activate; *right click* = go back one step (leave a menu level, previous
lesson page, undo a stroke, zoom out, undo a calibration point).

**Menus (main menu + submenus).**

```
Main menu
 |- Lesson
 |- Whiteboard  >  Blank board | Grid board | Dark board
 |- Images
 |- Setup       >  Board calibration | Marker colour | Settings
 |- Help
 `- Exit
```

The menus are data-driven (`interface/menus.py`); navigation uses a screen
stack, so *Back* and a right click always return one level up and *Home*
returns to the main menu from anywhere.

**Lesson.**  A 6-page computer-vision lesson with vector diagrams.  A left
click anywhere on the page (or *Next*) shows the next page and a right click
the previous one, so the presenter never has to aim at a small button.

**Whiteboard (free drawing).**  Strokes live in a transparent NumPy RGBA
layer; they are stored as point lists and rasterised with a manual DDA +
circular-brush algorithm.  Undo/redo rebuild the layer from the stroke
history (bounded by `history_limit`).  Interaction is designed for a
pointer plus two buttons: a left click on the board puts the pen down, the
marker then draws, and a second click lifts the pen; leaving the board or
losing the marker lifts it automatically.  A right click undoes the last
stroke.  The toolbar offers 4 colours (shown as real colour swatches),
4 thicknesses, Undo, Redo, Clear (asks for a second click) and Save (PNG of
the board background plus strokes, written to `output/`).  On the dark board
the ink colour switches from black to white.

**Image viewer.**  Because a projected board has no keyboard, pictures
placed in `assets/images/` appear in an on-board gallery (three teaching
images are provided and can be regenerated with
`tools/make_sample_images.py`); a *Browse* button opens the native file
dialog when tkinter is available.  The view is described by a zoom factor
(1-8x) and a centre point.  Only the visible region is cropped and scaled
and the result is cached until the view changes.  Zoom +/- and four arrow
buttons change the view, a click on the image re-centres it there, and *Fit*
resets.

**Settings.**  Two columns of grouped rows (camera and pointer, tracking,
marker HSV, display); values apply live except those marked (R), which are
read at start-up and need *Restart app*.

## 8. Algorithms and manually implemented operations

Implemented manually with NumPy (see `docs/algorithms.md` for details):
pixel access, channel handling, BGR→grayscale, BGR→HSV, thresholding and
HSV range masking, binary erosion/dilation/opening/closing, connected-
component statistics (area, centroid, bounding box), homography estimation
(DLT) and point transformation, EMA pointer smoothing with jump rejection,
and thick-line rasterisation for drawing.

Delegated to libraries (with justification): video capture
(`cv2.VideoCapture`), component *labelling* (`cv2.connectedComponents` —
performance), image file loading and PNG export (Pygame), global key
listening (pynput), rendering (Pygame).

## 9. Tests, results and known limitations

**77 automated tests pass** (`python -m pytest tests -q`), covering image
processing, detection on synthetic markers (including equivalence of the
sub-sampled and full-resolution detector at three resolutions), homography
correctness and degenerate cases (including corner-order validation),
tracking behaviour, drawing/undo/redo/export, keyboard simulation, and
integration tests that start the whole application headless, visit every
screen, check that all buttons stay inside the usable area at four display
sizes, exercise menu/submenu navigation, calibration clicks, the lesson,
drawing and image-viewer interaction, application restart, and the full
simulated-camera to pointer pipeline.  See `docs/testing.md`.

**Known limitations:** colour-based detection is lighting-sensitive (the
projector's own light changes the colours the camera sees);
single-marker tracking; the board is assumed planar; the detector keeps
only the largest blob, so a marker split by a reflection is tracked by its
largest part; physical remote key codes, real webcam latency and projector
behaviour are untested **[HARDWARE TEST REQUIRED]**.

## 10. Conclusion and possible improvements

The project delivers a complete, runnable, academically defensible smart
whiteboard: manual NumPy implementations of the core CV operations, a
validated homography calibration, robust pointer tracking, dual remote
input paths, and a full Pygame interface with lesson, drawing, image
viewing, calibration and settings — all testable without hardware thanks
to the simulation layer.

**Possible improvements:** multi-marker / hand tracking (e.g. MediaPipe),
DLT with more than 4 points (least squares) for robustness, image pan in
the viewer, gesture-based pen up/down, and automatic exposure/white-balance
handling for varying classroom lighting.
