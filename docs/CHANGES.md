# Review changes

## Interface
- One shared layout system (header, toolbar, status bar); no screen can
  overflow the window or hide under the status bar (tested at 4 sizes).
- Main menu redesigned as tiles, **with submenus** (Whiteboard, Setup) as
  the brief requires.  Back / Home on every screen, Esc = back.
- Whiteboard: click-to-toggle pen, right click = undo, real colour swatches,
  blank / grid / dark boards, Clear needs confirmation, Save includes the
  board background.
- Image viewer: on-board gallery (no OS dialog needed), pan, click-to-centre,
  cached rendering.  Lesson: click anywhere = next page, wrapped text,
  diagrams scaled to fit.  Settings: two grouped columns, (R) = restart.
- Click feedback rings; two-tone pointer visible on light and dark boards.

## Bugs fixed
- Calibration clicks were never registered (`button != 1` vs "left"/"right").
- Lesson right-click never worked (same cause).
- Restart crashed (Pygame was quit before relaunching).
- Mouse wheel counted as a right click.
- Wrong corner order silently mirrored the pointer (now rejected).
- Red markers: HSV sampling clipped the hue range (now wraps 0/360).
- Saved calibration mapped to the wrong range after a window-size change.
- Importing tkinter at start-up crashed the app where it is missing.
- Integration test patched the wrong name and used the real camera.

## Performance
- Detection ~100 ms -> ~21 ms per 720p frame (sub-sampling), on a worker
  thread; camera capture on its own thread.  UI loop 31 -> ~450
  iterations/s on the simulated camera.

## Not verifiable here (needs your hardware)
Real webcam latency, the physical remote's key codes, projector behaviour,
the Windows-only DirectShow path and the tkinter *Browse* dialog.
