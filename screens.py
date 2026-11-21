"""screens.py - Les ecrans de l'application (menus, dessin, images/zoom, cours, reglages).

Chaque ecran a : render(canvas, pointer), update(pointer), click(x, y, 'left'|'right').
Clic gauche (Next) = selection ; clic droit (Previous) = retour (ou action speciale).
"""
import cv2
import numpy as np
import config as C
import assets
import ui
from ui import (Button, ICONS, fill_rect, fill_gradient, fill_rounded, fill_rounded_grad, draw_rounded_border,
                put_text, stamp_disc, draw_line, resize_nearest, shade, get_background, diamond, flourish,
                FONT_TITLE, FONT_SUB)

TOP = 90  # hauteur de la barre superieure


def draw_header(canvas, title):
    fill_gradient(canvas, 0, 0, C.UI_W, TOP, (84, 34, 150), (46, 18, 88))   # velours
    fill_rect(canvas, 0, TOP - 7, C.UI_W, 3, C.GOLD)                          # double filet dore
    fill_rect(canvas, 0, TOP - 2, C.UI_W, 1, C.GOLD_DARK)
    if title:
        diamond(canvas, 252, TOP // 2 - 3, 7, C.GOLD_LIGHT)
        put_text(canvas, title, 275, TOP // 2 - 3, 1.1, C.GOLD_LIGHT, 2, shadow=True, vmid=True)


def pill(canvas, x, y, w, h, color, text, text_color=C.BG_BOTTOM, scale=0.7):
    fill_rounded_grad(canvas, x, y, w, h, h // 2, shade(color, 1.2), shade(color, 0.8))
    draw_rounded_border(canvas, x, y, w, h, h // 2, C.GOLD_DARK, 2)
    put_text(canvas, text, x + w // 2, y + h // 2, scale, text_color, 2, center=True)


def nav_buttons(app):
    return [Button("Home", 10, 10, 110, 70, app.home, icon=ICONS["home"], radius=14),
            Button("Back", 130, 10, 110, 70, app.pop, icon=ICONS["back"], radius=14)]


class Screen:
    def __init__(self, app):
        self.app = app
        self.buttons = []

    def update(self, pointer):
        pass

    def draw_buttons(self, canvas, pointer):
        for b in self.buttons:
            b.draw(canvas, pointer)

    def click(self, x, y, button):
        if button == "left":
            for b in self.buttons:
                if b.contains(x, y):
                    b.action()
                    return
            self.on_background_click(x, y)
        else:
            self.on_right_click()

    def on_background_click(self, x, y):
        pass

    def on_right_click(self):
        self.app.pop()


# ------------------------------------------------------------------ menu principal
class MainMenu(Screen):
    def __init__(self, app):
        super().__init__(app)
        items = [("Draw", "Free drawing", "pencil", lambda: app.push(DrawScreen(app, app.board_layer, app.board_base))),
                 ("Images", "Display and zoom", "image", lambda: app.push(ImagesScreen(app))),
                 ("Lesson", "Guided slides", "book", lambda: app.push(LessonScreen(app))),
                 ("Settings", "Calibration and reset", "gear", lambda: app.push(SettingsScreen(app)))]
        bw, bh, gap = 440, 150, 30
        x0, y0 = (C.UI_W - 2 * bw - gap) // 2, 205
        for i, (lbl, sub, ic, act) in enumerate(items):
            r, c = divmod(i, 2)
            self.buttons.append(Button(lbl, x0 + c * (bw + gap), y0 + r * (bh + gap), bw, bh, act,
                                       color=C.CARD_COLORS[i], icon=ICONS[ic], scale=1.3, sub=sub, radius=16))

    def on_right_click(self):
        self.app.toast("Already at the main menu")

    def render(self, canvas, pointer):
        put_text(canvas, "~ ESTABLISHED 2026 ~", C.UI_W // 2, 48, 0.6, C.GOLD, 1, center=True, font=FONT_SUB)
        put_text(canvas, "Smart Whiteboard", C.UI_W // 2, 100, 2.6, C.GOLD_LIGHT, 3, center=True, shadow=True, font=FONT_TITLE)
        flourish(canvas, C.UI_W // 2, 138, 250)
        put_text(canvas, "Point with the marker, then press a remote button", C.UI_W // 2, 172, 0.8,
                 C.TEXT, 1, center=True, font=FONT_SUB)
        self.draw_buttons(canvas, pointer)
        pill(canvas, C.UI_W // 2 - 340, 625, 320, 50, C.CLICK_LEFT, "NEXT: left click")
        pill(canvas, C.UI_W // 2 + 20, 625, 320, 50, C.CLICK_RIGHT, "PREVIOUS: right click")


# ------------------------------------------------------------------ dessin libre
class DrawScreen(Screen):
    def __init__(self, app, layer, base):
        super().__init__(app)
        self.layer, self.base = layer, base       # layer modifie en place (dessin persistant)
        self.color_idx, self.thick_idx = 0, 1
        self.pen_down, self.last = False, None
        self.color_btns = [Button("", 250 + i * 68, 10, 60, 70, lambda i=i: self.set_color(i), color=col, radius=14)
                           for i, col in enumerate(C.PEN_COLORS)]
        self.thick_btns = [Button("", 610 + j * 68, 10, 60, 70, lambda j=j: self.set_thick(j), radius=14,
                                  icon=lambda img, cx, cy, s, col, t=t: stamp_disc(img, cx, cy, t / 2, col))
                           for j, t in enumerate(C.PEN_SIZES)]
        self.buttons = (nav_buttons(app) + self.color_btns + self.thick_btns +
                        [Button("Clear", 830, 10, 110, 70, self.clear, icon=ICONS["trash"], radius=14)])
        self.refresh()

    def refresh(self):
        for i, b in enumerate(self.color_btns):
            b.selected = i == self.color_idx
        for j, b in enumerate(self.thick_btns):
            b.selected = j == self.thick_idx

    def set_color(self, i):
        self.color_idx = i
        self.refresh()

    def set_thick(self, j):
        self.thick_idx = j
        self.refresh()

    def clear(self):
        self.layer[:] = self.base
        self.last = None

    def update(self, pointer):
        if pointer is None or pointer[1] < TOP:
            self.last = None                      # on casse le trait
            return
        if self.pen_down:
            col, size = C.PEN_COLORS[self.color_idx], C.PEN_SIZES[self.thick_idx]
            if self.last is None:
                stamp_disc(self.layer, pointer[0], pointer[1], size / 2, col)
            else:
                ui.draw_line(self.layer, self.last, pointer, size, col)
            self.last = pointer

    def on_background_click(self, x, y):
        if y > TOP:                               # clic gauche = pen down / pen up
            self.pen_down = not self.pen_down
            self.last = (x, y) if self.pen_down else None

    def on_right_click(self):
        if self.pen_down:                         # clic droit : leve le stylo, sinon retour
            self.pen_down, self.last = False, None
        else:
            self.app.pop()

    def render(self, canvas, pointer):
        canvas[:] = self.layer
        draw_header(canvas, "")
        self.draw_buttons(canvas, pointer)
        if self.pen_down:
            pill(canvas, 975, 22, 240, 46, C.POINTER_COLOR, "PEN DOWN")
        else:
            pill(canvas, 975, 22, 240, 46, C.PANEL, "PEN UP", C.GRAY)


# ------------------------------------------------------------------ images + zoom
class ImagesScreen(Screen):
    """Sous-menu : liste des images disponibles."""
    def __init__(self, app):
        super().__init__(app)
        self.buttons = nav_buttons(app)
        for i, (name, img) in enumerate(app.images[:6]):
            self.buttons.append(Button(name, 290, 135 + i * 90, 700, 74,
                                       lambda n=name, im=img: app.push(ImageViewer(app, n, im)),
                                       color=C.CARD_COLORS[i % 4], icon=ICONS["image"], scale=0.95))

    def render(self, canvas, pointer):
        draw_header(canvas, "Images")
        self.draw_buttons(canvas, pointer)


class ImageViewer(Screen):
    def __init__(self, app, name, img):
        super().__init__(app)
        self.name, self.img = name, img
        self.zoom = 1.0
        self.cx, self.cy = img.shape[1] / 2, img.shape[0] / 2
        self.geom = None
        self.buttons = nav_buttons(app) + [
            Button("Zoom +", 260, 10, 130, 70, self.zoom_in, icon=ICONS["plus"], radius=14),
            Button("Zoom -", 400, 10, 130, 70, self.zoom_out, icon=ICONS["minus"], radius=14),
            Button("Reset", 540, 10, 130, 70, self.reset_view, icon=ICONS["fit"], radius=14)]

    def zoom_in(self):
        self.zoom = min(self.zoom * 1.5, 16.0)

    def zoom_out(self):
        self.zoom = max(self.zoom / 1.5, 1.0)

    def reset_view(self):
        self.zoom = 1.0
        self.cx, self.cy = self.img.shape[1] / 2, self.img.shape[0] / 2

    def on_background_click(self, x, y):
        """Clic dans l'image : recentre la vue sur ce point (et zoome si zoom = 1)."""
        if self.geom is None:
            return
        xi, yi, s, ox, oy, ow, oh = self.geom
        if ox <= x < ox + ow and oy <= y < oy + oh:
            self.cx, self.cy = xi + (x - ox) / s, yi + (y - oy) / s
            if self.zoom == 1.0:
                self.zoom_in()

    def render(self, canvas, pointer):
        ih, iw = self.img.shape[:2]
        vw, vh = C.UI_W, C.UI_H - TOP
        s = min(vw / iw, vh / ih) * self.zoom                    # echelle image -> ecran
        cw, ch = min(iw, vw / s), min(ih, vh / s)                # zone visible (pixels image)
        x0 = min(max(self.cx - cw / 2, 0), iw - cw)
        y0 = min(max(self.cy - ch / 2, 0), ih - ch)
        xi, yi = int(x0), int(y0)
        cwi, chi = min(max(1, round(cw)), iw - xi), min(max(1, round(ch)), ih - yi)
        ow, oh = min(int(cwi * s), vw), min(int(chi * s), vh)
        ox, oy = (vw - ow) // 2, TOP + (vh - oh) // 2
        canvas[oy:oy + oh, ox:ox + ow] = resize_nearest(self.img[yi:yi + chi, xi:xi + cwi], oh, ow)
        self.geom = (xi, yi, s, ox, oy, ow, oh)
        draw_header(canvas, "")
        self.draw_buttons(canvas, pointer)
        put_text(canvas, self.name, 710, 36, 0.8, C.TEXT, 1, vmid=True)
        pill(canvas, 710, 52, 120, 30, C.GOLD, f"x{self.zoom:.1f}", scale=0.6)


# ------------------------------------------------------------------ cours
class LessonScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.i = 0
        bot = C.UI_H - 85
        self.buttons = nav_buttons(app) + [
            Button("Prev", 40, bot, 220, 70, self.prev, icon=ICONS["back"], scale=0.9),
            Button("Annotate", C.UI_W // 2 - 150, bot, 300, 70, self.annotate, icon=ICONS["pencil"],
                   color=C.CARD_COLORS[0], scale=0.9),
            Button("Next", C.UI_W - 260, bot, 220, 70, self.next, icon=ICONS["next"], scale=0.9)]

    def prev(self):
        self.i = max(0, self.i - 1)

    def next(self):
        self.i = min(len(assets.SLIDES) - 1, self.i + 1)

    def annotate(self):
        bg = np.empty((C.UI_H, C.UI_W, 3), np.uint8)
        self.render_slide(bg)
        self.app.push(DrawScreen(self.app, bg.copy(), bg))      # dessin par-dessus la diapo

    def on_right_click(self):
        if self.i > 0:
            self.prev()
        else:
            self.app.pop()

    def render_slide(self, canvas):
        canvas[:] = get_background(True)
        sl = assets.SLIDES[self.i]
        draw_header(canvas, sl["title"])
        n = len(assets.SLIDES)
        fill_rect(canvas, 0, TOP - 7, int(C.UI_W * (self.i + 1) / n), 3, C.GOLD_LIGHT)  # progression
        fill_rounded(canvas, 50, 125, C.UI_W - 100, 445, 14, (10, 4, 22), 0.55)            # carte de contenu
        draw_rounded_border(canvas, 50, 125, C.UI_W - 100, 445, 14, C.GOLD, 3)
        draw_rounded_border(canvas, 58, 133, C.UI_W - 116, 429, 10, C.GOLD_DARK, 1)
        for k, line in enumerate(sl["lines"]):
            y = 190 + k * 80
            diamond(canvas, 98, y, 11, C.GOLD_LIGHT)
            diamond(canvas, 98, y, 5, C.BG_BOTTOM)
            put_text(canvas, line, 130, y, 1.0, C.TEXT, 2, vmid=True)
        if sl.get("diagram"):
            quad = [(760, 405), (960, 380), (1000, 500), (720, 520)]
            rect = [(1070, 390), (1210, 390), (1210, 510), (1070, 510)]
            for poly, col in ((quad, C.GOLD_LIGHT), (rect, C.CLICK_RIGHT)):
                for a, b in zip(poly, poly[1:] + poly[:1]):
                    draw_line(canvas, a, b, 5, col)
            draw_line(canvas, (1015, 450), (1055, 450), 5, C.POINTER_COLOR)
            draw_line(canvas, (1042, 438), (1056, 450), 5, C.POINTER_COLOR)
            draw_line(canvas, (1042, 462), (1056, 450), 5, C.POINTER_COLOR)
        pill(canvas, C.UI_W - 150, 28, 110, 34, C.GOLD, f"{self.i + 1} / {n}", scale=0.65)

    def render(self, canvas, pointer):
        self.render_slide(canvas)
        self.draw_buttons(canvas, pointer)


# ------------------------------------------------------------------ reglages (sous-menu)
class SettingsScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        acts = [("Recalibrate board", "fit", lambda: app.request("calibrate")),
                ("Pick marker color", "target", lambda: app.request("marker")),
                ("Toggle camera view", "camera", lambda: app.request("debug")),
                ("Reset application", "trash", app.reset),
                ("Quit", "close", lambda: app.request("quit"))]
        self.buttons = nav_buttons(app)
        for i, (lbl, ic, act) in enumerate(acts):
            self.buttons.append(Button(lbl, 340, 125 + i * 98, 600, 80, act, icon=ICONS[ic], scale=0.95,
                                       color=C.CARD_COLORS[0] if lbl == "Quit" else None))

    def render(self, canvas, pointer):
        draw_header(canvas, "Settings")
        self.draw_buttons(canvas, pointer)