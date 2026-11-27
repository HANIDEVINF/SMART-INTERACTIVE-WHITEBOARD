# Algorithms and manually implemented operations

This document explains every core algorithm in the project, which parts
are implemented manually with NumPy, and which are delegated to OpenCV,
Pygame or other libraries — and why.

## 1. Image representation and pixel access

Frames are NumPy arrays of shape `(H, W, 3)` with dtype `uint8`, channel
order **BGR** (OpenCV convention).  A pixel at image coordinates `(x, y)`
is `image[y, x]` — column first, row second.  `utils/image_processing.py`
provides `get_pixel` / `set_pixel` with bounds checking.

## 2. Colour conversion

### BGR → grayscale (manual)
ITU-R BT.601 luma coefficients, computed with a weighted sum of the
extracted channels:

```
Y = 0.114·B + 0.587·G + 0.299·R
```

### BGR → HSV (manual, vectorised)
The standard RGB→HSV algorithm, implemented with NumPy `where` masks:

- `V = max(R,G,B)`, `C = V − min(R,G,B)`
- `S = C / V` (0 for black pixels)
- Hue is computed per pixel depending on which channel attains the
  maximum, then normalised to degrees `[0, 360)`.

Working in float32 avoids integer-division errors and makes hue
thresholds human-readable.  Hue is **circular**, so ranges that wrap
through 0° (e.g. red) are supported by `in_hsv_range`.

## 3. Thresholding and segmentation

`in_hsv_range` builds a boolean mask of pixels inside an HSV box
(H, S, V min/max).  This is the segmentation step: everything inside the
box is "marker", everything else is background.  A plain grayscale
threshold (`threshold_gray`) is also provided for completeness.

## 4. Noise reduction / morphology (manual)

Binary **erosion** and **dilation** with a square structuring element are
implemented as AND/OR combinations of shifted copies of the mask — the
discrete equivalents of min/max filters:

- Dilation: pixel becomes foreground if *any* neighbour in the
  structuring element is foreground (OR of shifts).
- Erosion: pixel stays foreground only if *all* neighbours are foreground
  (AND of shifts).

`morphological_open` (erosion → dilation) removes isolated specks;
`morphological_close` (dilation → erosion) fills small holes.  The
detector applies an opening before blob analysis.

## 5. Connected components

**Labelling** is delegated to `cv2.connectedComponents` (8-connectivity).
Justification: an efficient union-find / run-length CCL in pure Python is
impractical at 720p/30 fps, and OpenCV's implementation is mature and
well-tested.  Everything *after* labelling is manual:

- **Area** per label via `np.bincount` over the flattened label map.
- **Centroid** via `np.bincount` weighted by precomputed x/y coordinate
  grids: `cx = Σx·label / Σlabel`, `cy = Σy·label / Σlabel`.
- **Bounding box** via `np.nonzero` on each surviving component.

Area filtering rejects noise blobs and blobs larger than a configurable
fraction of the frame.  The largest surviving blob is the marker.

### Detection speed: sub-sampling and a worker thread

The manual NumPy HSV conversion costs about 100 ms for a 1280x720 frame.
The detector therefore works on a sub-sampled copy (`frame[::s, ::s]`,
`s = width // 640`, i.e. 2 at 720p): the pipeline then costs about 20 ms.
The area thresholds are divided by `s^2` and the centroid and bounding box
are multiplied back by `s`, so results are in full-resolution camera pixels
(on the test scene the centroid differs by under 1 px).  Detection runs on
its own thread and only ever processes the newest frame, so a slow
detection drops frames instead of delaying the pointer.

The BGR-to-HSV conversion computes the hue with a single division for the
three "which channel is the maximum" cases (the first version divided
three times); the output is identical to within 0.0003 degrees.

## 6. Homography and perspective transformation (manual)

A homography `H` (3×3) maps camera pixels to board coordinates:

```
x' = (h11·x + h12·y + h13) / (h31·x + h32·y + h33)
y' = (h21·x + h22·y + h23) / (h31·x + h32·y + h33)
```

Cross-multiplying yields two **linear** equations per point
correspondence.  With 4 correspondences (the four clicked board corners)
we get an 8×8 system solved directly with `np.linalg.solve` after fixing
`h33 = 1` (homography scale is arbitrary) — the classic DLT restricted to
4 points.  `transform_points` applies `H` with an explicit perspective
divide.  Degenerate inputs (collinear or duplicate points) are rejected
by `is_valid_quad` and by the solver's `LinAlgError`.

The click order is validated too (`is_clockwise_convex`): the four points
must form a convex quadrilateral turning the same way at every corner
(top-left, top-right, bottom-right, bottom-left).  Another order would
produce a mirrored homography and a silently flipped pointer, so it is
rejected with an explanatory message.

`cv2.getPerspectiveTransform` / `cv2.warpPerspective` are deliberately
**not** used: the requirement is to implement and be able to defend the
maths, which the DLT solver does.

## 7. Pointer smoothing (EMA + jump rejection)

`PointerTracker` applies an exponential moving average:

```
p ← α·p_new + (1−α)·p_old        (α configurable, default 0.45)
```

- **Jump rejection**: a sample farther than `max_jump` px from the
  estimate is ignored once; if the *next* sample is also far away the
  tracker accepts the teleport (fast real motion stays possible while
  single-frame false detections are rejected).
- **Loss handling**: when the marker disappears the last position is
  reported for `loss_timeout` seconds, then the pointer is reported lost
  and hidden.

## 8. Drawing rasterisation (manual)

`rasterize_line` draws thick segments on a NumPy RGBA layer using a DDA:
step along the segment at sub-pixel intervals and stamp a filled circular
brush (a NumPy meshgrid distance test) at each step, alpha-compositing
into the layer.  Strokes are stored as point lists; undo/redo rebuilds
the layer by replaying strokes, which keeps memory bounded.

## 9. Remote input

`pynput`'s global `keyboard.Listener` runs on a daemon thread and pushes
click events into a `queue.Queue`; the Pygame loop drains it once per
frame (debounced — holding a button cannot repeat clicks).  The keyboard
simulator maps configured Pygame keys to the same "left"/"right" button
names, so both input paths feed one `EventManager`.

## 10. What is delegated to libraries

| Operation | Library | Why |
|---|---|---|
| Video capture | OpenCV `VideoCapture` | reliable cross-driver webcam access |
| Component labelling | OpenCV `connectedComponents` | performance (see §5) |
| Image file loading (viewer) | Pygame `image.load` | we need a Surface anyway |
| PNG export | Pygame `image.save` | native surface export |
| File dialog | tkinter | standard, no extra deps |
| Global key listener | pynput | only practical Windows global-HID option |
| Rendering/UI | Pygame | project requirement |
