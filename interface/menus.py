"""Main menu, submenus and help screen.

The menu is data-driven: a list of items, each either an action or a link
to a submenu.  Navigation uses the app's screen stack, so the header's
*Back* button (and a right click) always return one level up, and *Home*
returns to the main menu from anywhere.

    Main menu
    |- Lesson
    |- Whiteboard  >  Blank board | Grid board | Dark board
    |- Images
    |- Setup       >  Board calibration | Marker colour | Settings
    |- Help
    `- Exit
"""

from __future__ import annotations

import pygame

from interface.components import (COLORS, FONT_M, FONT_MB, FONT_S, FONT_XL,
                                  HEADER_H, PAD, STATUS_H, Screen,
                                  TileButton, draw_card, fit_surface,
                                  wrap_text)

ACCENTS = [(64, 156, 255), (120, 210, 140), (255, 196, 66),
           (200, 130, 255), (255, 140, 100), (140, 200, 220)]


class MenuScreen(Screen):
    """A grid of large tiles.  ``items``: dicts with label, desc and
    either ``action`` (callable) or ``submenu`` (screen name)."""

    def __init__(self, app, title, items, root=False, subtitle=""):
        self.root = root
        self.show_header = not root
        super().__init__(app)
        self.title = title
        self.subtitle = subtitle
        self._items = items
        self._build_tiles()

    # -- layout ------------------------------------------------------------

    def _build_tiles(self):
        n = len(self._items)
        cols = 3 if n >= 3 else n
        rows = -(-n // cols)
        gap = 24
        top = 190 if self.root else HEADER_H + 40
        bottom = self.h - STATUS_H - 30
        avail_h = max(80, bottom - top)
        tile_w = min(380, (self.w - 2 * 48 - gap * (cols - 1)) // cols)
        tile_h = min(190, (avail_h - gap * (rows - 1)) // rows)
        total_w = cols * tile_w + (cols - 1) * gap
        total_h = rows * tile_h + (rows - 1) * gap
        x0 = (self.w - total_w) // 2
        y0 = top + max(0, (avail_h - total_h) // 2)
        self.buttons = []
        for i, item in enumerate(self._items):
            r, c = divmod(i, cols)
            rect = pygame.Rect(x0 + c * (tile_w + gap),
                               y0 + r * (tile_h + gap), tile_w, tile_h)
            if "submenu" in item:
                name = item["submenu"]
                action = (lambda n=name: self.app.go_to(n))
            else:
                action = item["action"]
            self.buttons.append(TileButton(
                rect, item["label"], item.get("desc", ""), action,
                ACCENTS[i % len(ACCENTS)], submenu="submenu" in item,
                danger=item.get("danger", False)))

    # -- behaviour ---------------------------------------------------------

    def on_right_click(self, pos):
        if not self.root:               # root has nowhere to go back to
            self.app.go_back()
        return True

    def draw_body(self, s):
        if not self.root:
            return
        title = fit_surface(FONT_XL.render(self.title, True, COLORS["text"]),
                            self.w - 80)
        s.blit(title, title.get_rect(center=(self.w // 2, 78)))
        sub = FONT_M.render(self.subtitle, True, COLORS["text_dim"])
        s.blit(sub, sub.get_rect(center=(self.w // 2, 132)))


# ---------------------------------------------------------------------------
# Menu tree
# ---------------------------------------------------------------------------

def build_menus(app) -> dict:
    """Return the menu screens keyed by screen name."""
    def open_board(style):
        def _go():
            app.screens["drawing"].set_board(style)
            app.go_to("drawing")
        return _go

    main = MenuScreen(app, "Smart Interactive Whiteboard", [
        {"label": "Lesson", "desc": "Guided 6-page lesson on computer "
         "vision. Click anywhere to turn the page.",
         "action": lambda: app.go_to("lesson")},
        {"label": "Whiteboard", "desc": "Draw and annotate. Choose a blank, "
         "grid or dark board.", "submenu": "menu_draw"},
        {"label": "Images", "desc": "Show a picture on the board, zoom in "
         "and out.", "action": lambda: app.go_to("image")},
        {"label": "Setup", "desc": "Calibrate the board, tune the marker "
         "colour, change settings.", "submenu": "menu_setup"},
        {"label": "Help", "desc": "How the pointer, the remote and the "
         "menus work.", "action": lambda: app.go_to("help")},
        {"label": "Exit", "desc": "Close the application.",
         "action": app.quit, "danger": True},
    ], root=True,
        subtitle="Point at the board with the marker, press a remote button to click")

    draw = MenuScreen(app, "Whiteboard", [
        {"label": "Blank board", "desc": "Plain white board for free "
         "drawing.", "action": open_board("blank")},
        {"label": "Grid board", "desc": "White board with a light grid, "
         "good for graphs and diagrams.", "action": open_board("grid")},
        {"label": "Dark board", "desc": "Chalkboard look; the pen colours "
         "adapt automatically.", "action": open_board("dark")},
    ], subtitle="Choose a drawing surface")

    setup = MenuScreen(app, "Setup", [
        {"label": "Board calibration", "desc": "Click the 4 board corners "
         "on the camera image.", "action": lambda: app.go_to("calibration")},
        {"label": "Marker colour", "desc": "Sample the colour of your "
         "marker so it can be tracked.",
         "action": lambda: app.go_to("hsv_calib")},
        {"label": "Settings", "desc": "Camera, pointer, tracking and "
         "display options.", "action": lambda: app.go_to("settings")},
    ], subtitle="Run these once before a lesson")

    return {"menu": main, "menu_draw": draw, "menu_setup": setup}


# Kept for backwards compatibility with older imports.
def MainMenuScreen(app):  # noqa: N802
    return build_menus(app)["menu"]


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

HELP_CARDS = [
    ("Pointer", [
        "Hold the coloured marker in front of the camera. Its position "
        "becomes the on-screen pointer (blue ring).",
        "If the marker is not visible, the mouse is used (auto mode).",
    ]),
    ("Remote / clicks", [
        "Button 1 (or key Z) = left click: select, start/stop the pen, "
        "next page.",
        "Button 2 (or key X) = right click: go back one step, undo, "
        "previous page.",
        "A ring flashes at the pointer on every click.",
    ]),
    ("Navigation", [
        "Point at a tile or button and click.",
        "Back (top left) or a right click goes up one level.",
        "Home (top right) returns to the main menu from anywhere.",
    ]),
    ("Whiteboard", [
        "Left click on the board puts the pen down; move to draw; click "
        "again to lift it. Leaving the board lifts the pen too.",
        "Right click = undo the last stroke. Clear asks for a second "
        "click to confirm.",
    ]),
    ("Images and lesson", [
        "Images: pick one from the gallery, use Zoom +/-, click on the "
        "image to centre the view there, Fit to reset.",
        "Lesson: click anywhere (or Next) for the next page, right click "
        "for the previous one.",
    ]),
    ("First-time setup", [
        "Setup > Board calibration: click the 4 board corners (top-left, "
        "top-right, bottom-right, bottom-left) then Save.",
        "Setup > Marker colour: put the marker in the yellow box, Sample, "
        "Apply.",
    ]),
]


class HelpScreen(Screen):
    title = "Help"
    subtitle = "How to control the whiteboard"

    def __init__(self, app):
        super().__init__(app)
        self._layout()

    def _layout(self):
        pad, gap = PAD + 8, 16
        body = self.body_rect.inflate(-2 * pad, -pad)
        body.y += pad // 2
        col_w = (body.w - gap) // 2
        per_col = 3
        self.cards = []              # (rect, title, wrapped lines)
        ys = [body.y, body.y]
        card_h = (body.h - gap * (per_col - 1)) // per_col
        for i, (title, paras) in enumerate(HELP_CARDS):
            col = i // per_col
            rect = pygame.Rect(body.x + col * (col_w + gap), ys[col],
                               col_w, card_h)
            ys[col] += card_h + gap
            lines = []
            for p in paras:
                wrapped = wrap_text(FONT_S, p, col_w - 36)
                lines.append(wrapped)
            self.cards.append((rect, title, lines))

    def draw_body(self, s):
        for rect, title, paras in self.cards:
            draw_card(s, rect, title)
            y = rect.y + 50
            for para in paras:
                for line in para:
                    if y + 22 > rect.bottom - 4:
                        break
                    s.blit(FONT_S.render(line, True, COLORS["text"]),
                           (rect.x + 18, y))
                    y += 23
                y += 5
