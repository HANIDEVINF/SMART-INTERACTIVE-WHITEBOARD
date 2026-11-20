"""The menu structure (main menu + one level of submenus).

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

    def shuffle(ctx):
        ctx.scene.reset()
        ctx.toast("Objects back to start")

    def toggle_trail(ctx):
        ctx.show_trail = not ctx.show_trail

    def toggle_debug(ctx):
        ctx.show_debug = not ctx.show_debug

    def recalibrate(ctx):
        if ctx.mouse_mode:
            ctx.toast("Calibration is not needed in mouse mode")
        else:
            ctx.nav.push("calibration")

    def quit_app(ctx):
        ctx.quit = True

    return MenuItem("Main menu", children=[
        MenuItem("Draw", children=[
            MenuItem("Free drawing", lambda c: c.nav.push("draw"), hint="pen / colours / thickness"),
            MenuItem("Clear drawing", clear_drawing),
        ]),
        MenuItem("Images", children=[
            MenuItem("Gallery + zoom", lambda c: c.nav.push("images"), hint="zoom in / out / pan"),
            MenuItem("Reset zoom", reset_zoom),
        ]),
        MenuItem("Lesson", children=[
            MenuItem("Start lesson", start_lesson, hint="from page 1"),
            MenuItem("Continue", lambda c: c.nav.push("lesson"), hint="where you stopped"),
        ]),
        MenuItem("Objects", children=[
            MenuItem("Drag & drop", lambda c: c.nav.push("objects"), hint="sort the shapes"),
            MenuItem("Put objects back", shuffle),
        ]),
        MenuItem("Settings", children=[
            MenuItem("Recalibrate", recalibrate, hint="camera <-> board"),
            MenuItem(lambda c: f"Pointer trail: {'ON' if c.show_trail else 'OFF'}", toggle_trail),
            MenuItem(lambda c: f"Camera window: {'ON' if c.show_debug else 'OFF'}", toggle_debug),
            MenuItem("Quit", quit_app),
        ]),
    ])
