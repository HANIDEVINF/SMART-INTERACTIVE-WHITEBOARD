# Requirement traceability

| Requirement (specification) | Implemented in | Verified by |
|---|---|---|
| Dashboard with all entries, recent files, camera + tracking status | `ui/dashboard.py` | `test_gui` |
| Whiteboard: pen, eraser, line, rectangle, circle, text; colours; thickness; undo / redo; clear with confirmation | `tools/drawing.py`, `tools/primitives.py`, `ui/whiteboard.py`, `ui/toolbar.py` | `test_drawing`, `test_gui` |
| Save PNG, load drawing / image, mouse fallback, history | `ui/whiteboard.py` | `test_gui`, `test_drawing` |
| Save and load sessions | `tools/session_file.py`, `ui/whiteboard.py` | `test_session`, `test_gui_interaction` |
| Camera acquisition in a worker thread, selection, status, reconnection, diagnostics page | `core/camera.py`, `ui/camera_page.py` | `test_vision_pipeline`, `test_gui_vision`, `test_camera_live` |
| HSV colour-marker detection, mask, centroid, sensitivity, min area, smoothing, lost pointer, indicator | `core/detector.py`, `core/tracker.py`, `ui/settings_page.py`, `ui/video_view.py` | `test_detection`, `test_tracking`, `test_gui_vision` |
| Calibration wizard, homography, validation, JSON persistence, recalibration | `core/homography.py`, `core/calibration.py`, `ui/calibration_page.py` | `test_calibration` |
| Camera -> board -> canvas mapping, pointer position correct after resize | `core/coordinate_mapping.py`, `ui/whiteboard.py` | `test_mapping`, `test_gui_vision` |
| Visible smooth pointer, visibility toggle, detection-lost indication | `ui/whiteboard.py`, `ui/settings_page.py` | `test_gui_vision` |
| Navigation / Drawing / Selection modes, dwell confirmation, no repeated clicks | `core/interaction.py` | `test_interaction`, `test_gui_interaction` |
| Menus and submenus (main, drawing, image, presentation, settings), mouse + keyboard + pointer | `core/menu_model.py`, `ui/pointer_menu.py`, `ui/whiteboard.py` | `test_interaction`, `test_gui_interaction` |
| Image import (PNG / JPG / JPEG / BMP), zoom in / out / reset / fit, pan, aspect ratio, annotation over images | `tools/image_tools.py`, `core/view_transform.py`, `ui/whiteboard.py` | `test_view`, `test_gui_interaction` |
| Teaching mode: pages, titles, text, images, Previous / Next with page numbers, annotation, sample lesson, exit | `core/lesson.py`, `ui/teaching_page.py`, `ui/lesson_render.py`, `data/lessons/` | `test_lesson`, `test_gui_teaching` |
| Remote: Right = Next = left click, Left = Previous = right click, configurable keys, key diagnostics, debounce | `core/remote_control.py`, `ui/remote_panel.py` | `test_remote`, `test_gui_interaction` |
| Fullscreen, reset, return to home, shortcuts, confirmations, persistent settings | `ui/main_window.py`, `core/settings.py` | `test_gui`, `test_gui_interaction` |
| Tests: detection, centroid, transformation, calibration validation, drawing, zoom, remote mapping, synthetic images, real webcam | `tests/` | `docs/TEST_RESULTS.md` |
| Robustness: camera unavailable, pointer lost, invalid calibration, invalid image, reset, repeated remote events | various | `test_gui_vision`, `test_calibration`, `test_gui`, `test_gui_interaction`, `test_remote` |
| Documentation of algorithms, advantages and limitations of the detection method | module docstrings, `README.md`, `docs/REPORT_MATERIAL.md` | - |
