"""The menu structure (main menu + submenus).

Edit this file to add/rename entries; the screens themselves do not change.
Labels may be functions so toggles can show their current state.
"""
from __future__ import annotations

from .menu import MenuItem


def build_menu() -> MenuItem:
    def clear_drawing(ctx):
        ctx.drawing.clear()
        ctx.toast("Drawing cleared")

    def reset_zoom(ctx):
        ctx.viewer.reset_view()
        ctx.toast("Zoom reset")

    def start_lesson(ctx):
        ctx.lesson.restart()
        ctx.nav.push("lesson")

    def to_quiz(ctx):
        if ctx.lesson.goto_first("quiz"):
            ctx.nav.push("lesson")
        else:
            ctx.toast("This lesson has no quiz page")

    def shuffle(ctx):
        ctx.scene.reset()
        ctx.toast("Objects back to start")

    def toggle(name, text):
        def act(ctx):
            setattr(ctx, name, not getattr(ctx, name))
            ctx.toast(f"{text} {'ON' if getattr(ctx, name) else 'OFF'}", 1.4)
        return act

    def toggle_overlay(name, text):
        def act(ctx):
            setattr(ctx.overlays, name, not getattr(ctx.overlays, name))
            on = getattr(ctx.overlays, name)
            ctx.toast(f"{text} {'ON' if on else 'OFF'}  (works on every screen)", 2.0)
        return act

    def recalibrate(ctx):
        if ctx.mouse_mode:
            ctx.toast("Calibration is not needed in mouse mode")
        else:
            ctx.nav.push("calibration")

    def sensitivity(ctx):
        """Cycle the detection thresholds: high = also finds a dim dot, low = rejects more clutter."""
        presets = [("High", 0.60, 0.35), ("Medium", 0.75, 0.45), ("Low", 0.88, 0.55)]
        d = ctx.cfg.detection
        i = next((k for k, p in enumerate(presets) if abs(p[1] - d.val_min) < 0.02), 1)
        name, d.val_min, d.sat_min = presets[(i + 1) % 3]
        ctx.toast(f"Dot sensitivity: {name}", 2.0)

    def sens_label(ctx):
        v = ctx.cfg.detection.val_min
        return "Dot sensitivity: " + ("High" if v < 0.68 else "Medium" if v < 0.82 else "Low")

    def snapshot(ctx):
        ctx.toast("Snapshot saved: " + ctx.save_snapshot(), 3.0)

    def quit_app(ctx):
        ctx.quit = True

    return MenuItem("Main menu", children=[
        MenuItem("Draw", icon="pen", hint="pen, shapes, colours", children=[
            MenuItem("Free drawing", lambda c: c.nav.push("draw"), hint="pen / shapes / eraser", icon="pen"),
            MenuItem("Clear drawing", clear_drawing, hint="erase everything", icon="trash"),
            MenuItem("Save snapshot", snapshot, hint="PNG in ./snapshots", icon="save"),
        ]),
        MenuItem("Images", icon="image", hint="gallery, zoom, pan", children=[
            MenuItem("Gallery + zoom", lambda c: c.nav.push("images"), hint="zoom in / out / pan", icon="magnifier"),
            MenuItem("Reset zoom", reset_zoom, hint="back to the original view", icon="reset"),
        ]),
        MenuItem("Lesson", icon="book", hint="slides, quiz, annotation", children=[
            MenuItem("Start lesson", start_lesson, hint="from page 1", icon="play"),
            MenuItem("Continue", lambda c: c.nav.push("lesson"), hint="where you stopped", icon="next"),
            MenuItem("Quiz", to_quiz, hint="jump to the questions", icon="quiz"),
        ]),
        MenuItem("Objects", icon="shapes", hint="drag & drop exercise", children=[
            MenuItem("Drag & drop", lambda c: c.nav.push("objects"), hint="sort the shapes", icon="shapes"),
            MenuItem("Put objects back", shuffle, hint="restart the exercise", icon="reset"),
        ]),
        MenuItem("Tools", icon="spotlight", hint="spotlight, magnifier, timer", children=[
            MenuItem(lambda c: f"Spotlight: {'ON' if c.overlays.spotlight else 'OFF'}",
                     toggle_overlay("spotlight", "Spotlight"), hint="dim all but the pointer", icon="spotlight"),
            MenuItem(lambda c: f"Magnifier: {'ON' if c.overlays.magnifier else 'OFF'}",
                     toggle_overlay("magnifier", "Magnifier"), hint="lens follows the pointer", icon="magnifier"),
            MenuItem("Timer", lambda c: c.nav.push("timer"), hint="classroom countdown", icon="timer"),
            MenuItem("Pointer test", lambda c: c.nav.push("pointer_test"), hint="trajectory + accuracy", icon="target"),
        ]),
        MenuItem("Settings", icon="gear", hint="calibration, tracking", children=[
            MenuItem("Recalibrate", recalibrate, hint="camera <-> board", icon="camera"),
            MenuItem(sens_label, sensitivity, hint="red-dot thresholds", icon="sun"),
            MenuItem(lambda c: f"Pointer trail: {'ON' if c.show_trail else 'OFF'}", toggle("show_trail", "Pointer trail"),
                     hint="comet behind the dot", icon="pointer"),
            MenuItem(lambda c: f"Camera window: {'ON' if c.show_debug else 'OFF'}", toggle("show_debug", "Camera window"),
                     hint="operator view", icon="wifi"),
            MenuItem("Quit", quit_app, hint="close the application", icon="power"),
        ]),
    ])
