# Testing methodology and results

## Methodology

All tests run headless (`SDL_VIDEODRIVER=dummy`) so no display or camera
is required.  Synthetic data is used wherever hardware would be needed:
coloured circles drawn with OpenCV stand in for the physical marker, and
the `FakeCamera` generates a moving-marker scene.

Run everything with:

```powershell
python -m pytest tests -q
```

## Test coverage

| Module | File | What is tested |
|---|---|---|
| Image processing | `test_image_processing.py` | pixel access, grayscale, HSV conversion (known colours), thresholding, HSV range wrap-around, erosion/dilation/opening, component stats (centroid/bbox), line rasterisation |
| Detection | `test_detection.py` | single marker centroid, no-marker case, noise rejection, wrong-colour rejection, largest-blob selection, `None` frame |
| Homography | `test_homography.py` | identity, translation, scale, board-corner mapping, centre mapping, degenerate/collinear/duplicate rejection, quad validation, point-in-rect |
| Tracking | `test_tracking.py` | initialisation, EMA convergence, jitter reduction, single-frame jump rejection, teleport acceptance, loss grace period, loss timeout, recovery, reset |
| Drawing | `test_drawing.py` | stroke rasterisation, stroke separation, undo/redo, empty undo, clear, history limit, PNG export, two colours |
| Interaction | `test_interaction.py` | keyboard sim left/right, key debounce, event manager poll, remote key-name normalisation |
| Integration | `test_app_integration.py` | app boot and shutdown, restart without crash, Back/Home navigation, submenus, mouse-wheel is not a click, every button inside the usable area at 4 display sizes, calibration clicks + save, wrong corner order rejected, lesson right-click, pen toggle / undo / pen-up when leaving the board, Clear confirmation, image gallery / zoom / pan |
| Pipeline | `test_pipeline.py` | sub-sampled vs full-resolution detection at 640/1280/1920 px, automatic stride, red-marker hue wrap-around in HSV sampling, tracker loss timeout, corner-order check, layout rows never overflow, simulated camera -> detection -> homography -> pointer end to end |

## Results

Latest run: **77 tests, all passing** (`python -m pytest tests -q`).

## Synthetic test cases of note

- **Marker detection**: a `(0,255,0)` BGR circle of radius 25 on a dark
  frame is detected with centroid within 5 px of the true centre.
- **Homography**: four camera points mapped to board corners reproduce the
  corners exactly (atol 1e-6) and the quad centre lands near the board
  centre.
- **Tracking**: with `alpha=0.3`, alternating ±5 px jitter is smoothed to
  a peak-to-peak variation below 5 px.

## Known limitations

- Detection depends on colour contrast; markers similar in hue to the
  background or poor lighting reduce accuracy (mitigated by the HSV
  auto-calibration tool).
- The homography assumes a planar board; curved or heavily angled setups
  need re-calibration.
- `cv2.connectedComponents` labelling is OpenCV-provided (justified in
  `docs/algorithms.md`); all statistics are manual.
- The image viewer pans with buttons or click-to-centre, not by dragging
  (a pointer with two buttons cannot drag).

## Regression tests for bugs found in review

Each of these once failed and now has a test: calibration clicks ignored
(button compared to an integer while the app sends "left"/"right"),
lesson right-click never firing (same cause), toolbars overflowing the
window or hidden under the status bar, restart crashing because Pygame was
quit before relaunch, the mouse wheel acting as a right click, a wrongly
ordered set of calibration corners silently mirroring the pointer, the red
marker's hue range being clipped when sampling, a saved calibration
mapping to the wrong range after the window size changed, and the old integration
test patching a name that the application had already imported (so it
silently used the real camera).

## Measured performance (simulated camera, 1280x720 interface)

| | before | after |
|---|---|---|
| Marker detection, 720p frame | ~100 ms | ~21 ms (sub-sampled), on a worker thread |
| UI loop throughput, uncapped | ~31 iterations/s | ~450 iterations/s |
| Worst single UI frame | n/a | ~13 ms |

These are synthetic-camera numbers measured in a headless sandbox; real
webcam latency still has to be measured on the target machine.

## Hardware tests still required

The following **cannot** be verified without physical hardware and are
therefore untested in this environment:

- Real webcam frame rates and detection latency (measure with
  `tools/camera_viewer.py`).
- Physical presentation remote key codes (discover with
  `tools/remote_key_detector.py`, then set `remote_keys` in Settings).
- Projector output, fullscreen behaviour on the second display, and
  real-world lighting conditions.
- End-to-end latency from marker motion to pointer movement.
