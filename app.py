"""app.py - Etat global et logique d'interaction : pile d'ecrans, pointeur, clics, messages."""
import time
import numpy as np
import config as C
import assets
from ui import put_text, draw_pointer, draw_ring, fill_rounded, get_background
from screens import MainMenu


class App:
    def __init__(self):
        self.stack, self.requests, self.pointer = [], [], None
        self.images = assets.load_images()
        self.board_base = get_background(False).copy()   # fond uni en degrade pour le dessin
        self.board_layer = self.board_base.copy()        # dessin libre persistant
        self._toast, self._flash = ("", 0.0), None
        self.push(MainMenu(self))

    # ---- navigation
    @property
    def current(self):
        return self.stack[-1]

    def push(self, screen):
        self.stack.append(screen)

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop()

    def home(self):
        del self.stack[1:]

    def reset(self):
        self.home()
        self.board_layer[:] = self.board_base
        self.toast("Application reset")

    # ---- messages et requetes vers la boucle principale (calibration, quitter...)
    def toast(self, msg, secs=1.8):
        self._toast = (msg, time.time() + secs)

    def request(self, name):
        self.requests.append(name)

    def pop_requests(self):
        r, self.requests = self.requests, []
        return r

    # ---- boucle
    def update(self, pointer):
        self.pointer = pointer
        self.current.update(pointer)

    def handle_event(self, ev):
        """ev = 'left' (Next) ou 'right' (Previous) : clic a la position courante du pointeur."""
        if self.pointer is None:
            self.toast("Pointer not detected")
            return
        x, y = self.pointer
        self._flash = (x, y, time.time(), ev)
        self.current.click(x, y, ev)

    def render(self):
        canvas = get_background(True).copy()
        self.current.render(canvas, self.pointer)
        now = time.time()
        if self._flash and now - self._flash[2] < 0.3:   # anneau de retour visuel du clic
            x, y, t0, ev = self._flash
            r = 22 + int((now - t0) / 0.3 * 40)
            draw_ring(canvas, x, y, r, r - 5, C.CLICK_LEFT if ev == "left" else C.CLICK_RIGHT,
                      alpha=1.0 - (now - t0) / 0.3)
        if self.pointer is not None:
            draw_pointer(canvas, self.pointer)
        if now < self._toast[1]:
            w = 40 + 17 * len(self._toast[0])                 # message sur fond arrondi
            fill_rounded(canvas, (C.UI_W - w) // 2, C.UI_H - 70, w, 46, 23, (20, 12, 8), 0.85)
            put_text(canvas, self._toast[0], C.UI_W // 2, C.UI_H - 47, 0.8, C.POINTER_COLOR, 2, center=True)
        return canvas