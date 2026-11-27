# Demonstration script (about 8 minutes)

Dates: early demo 2 Dec 2026 - official demo 9 Dec 2026 - late demo 16 Dec 2026.
The specification asks the demo to show: **calibration, pointer tracking, both remote buttons, menu navigation, free
drawing, image display and zoom.** The script below shows them in that order, plus the teaching lesson.

## Before the demo (10 minutes, once)

1. `cd smart_whiteboard` then `.\.venv\Scripts\python.exe -m pytest tests -q` - everything green (3 tests skipped without a camera).
2. `.\.venv\Scripts\python.exe -m pytest tests\test_camera_live.py -s -v` - the real webcam test; close Teams / Zoom first.
3. Prepare the "board": a sheet of white paper or the room's board, well lit, fixed camera position (a book under the laptop screen).
4. Prepare the marker: a saturated, matte colour that is rare in the room (green highlighter cap, pink sticky note).
5. Start the app, **Settings > Detection**: click the marker in the live image, check the mask shows one solid blob. Add the physical remote later with **Settings > Remote & Pointer > Key diagnostics**.
6. Do the calibration once (below). It is saved; it only needs redoing if the camera or the board moves.

## The demo

| # | Say | Do | Shows |
|---|---|---|---|
| 1 | "LuminaBoard turns a webcam and a coloured marker into an interactive board." | Home screen: point at the camera / tracking status rows. | Dashboard, status |
| 2 | "The camera runs in its own thread; here are the diagnostics." | **Camera** page: resolution, FPS, connection state, *Stop* / *Start camera*. | Camera module, reconnection |
| 3 | "Calibration maps the camera view onto the board with a homography." | **Calibration**: Capture frame (Space), click TL, TR, BR, BL, show the projected grid and the rectified preview, *Save calibration*. | Calibration + homography |
| 4 | "The detector is written in NumPy: HSV, threshold, morphology, components, centroid." | **Settings > Detection**: click the marker, show the mask, move sensitivity. | Detection |
| 5 | "The pointer follows the marker." | **Whiteboard**, press **Track** (`K`): pointer on the board, move the marker, hide it -> "Pointer lost", the pen lifts. | Tracking, lost-pointer handling |
| 6 | "Next is a left click, Previous a right click." | Hover the marker over a toolbar-free area; press **Right** (ring "Left click"), **Left** (ring "Right click" and the menu opens). | Both remote buttons |
| 7 | "Menus have sub-levels and work with the pointer." | Menu: Drawing > Colours > Red; Back; Thickness > Thick; Image; Settings > Remote and keys. | Menu navigation |
| 8 | "Drawing mode: Next puts the pen down." | Press `2`, Next, move the marker, Next again; write a word in two colours / thicknesses; Undo / Redo. | Free drawing |
| 9 | "Selection mode confirms by dwell." | Press `3`, rest on a menu item until the ring completes. | Dwell selection |
| 10 | "Images can be zoomed and annotated." | Menu > Image > Open image; wheel or `+` to zoom, Pan, Fit; draw an arrow on the image. | Image display + zoom |
| 11 | "A short lesson." | **Teaching**: Present the demo lesson; Next / Previous at the bottom of the board with the remote; annotate page 4; go back and forth. | Teaching mode |
| 12 | "Everything can be saved." | Menu > Image > Save session; `F11` fullscreen and `Esc`. | Sessions, fullscreen |

## If something goes wrong

* **No webcam / camera busy**: the whiteboard still works with the mouse; the remote keys then use the mouse as the pointer, so steps 6-12 can be shown without a camera. Say so openly.
* **Pointer jumps or is lost**: Settings > Detection > raise *Sensitivity*, or re-pick the colour; check lighting. Re-run calibration if the board moved.
* **Physical remote sends other keys**: Settings > Remote & Pointer > *Add key...* and press the remote button.
* **Reset everything**: Settings > General > *Reset all settings* (keeps camera choice and calibration).
