"""Shared UI building blocks: theme, fonts, layout helpers, buttons, screens.

Design rules (they exist because the first version of the UI overflowed):

* Every screen is laid out from the *same* geometry constants below, so
  nothing is ever hidden under the status bar or pushed off the window.
* Rows of buttons are placed with :func:`layout_row`, which shrinks the
  buttons proportionally instead of overflowing when the window is small.
* Every screen derives from :class:`Screen`, which provides the header
  (title, Back, Home), the toast messages and the click dispatch, so the
  behaviour is identical everywhere:

      left click  = select / activate
      right click = go back one step
"""

from __future__ import annotations

import time

import pygame

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

COLORS = {
    "bg": (20, 23, 34),
    "panel": (36, 40, 58),
    "panel_alt": (50, 55, 78),
    "text": (240, 242, 248),
    "text_dim": (150, 157, 182),
    "accent": (64, 156, 255),
    "accent_hover": (96, 178, 255),
    "danger": (229, 72, 77),
    "warn": (255, 196, 66),
    "success": (80, 200, 120),
    "border": (70, 76, 104),
    "toolbar": (27, 30, 44),
    "paper": (247, 248, 252),     # whiteboard background
    "grid": (221, 225, 236),
    "chalk": (27, 30, 43),        # dark-board background
    "chalk_grid": (44, 49, 68),
}

# Geometry shared by every screen (pixels).
STATUS_H = 28      # bottom status bar, owned by the app
HEADER_H = 72      # title bar with Back / Home
TOOLBAR_H = 84     # bottom toolbar (sits just above the status bar)
PAD = 16


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    try:
        # A comma-separated list lets Pygame pick the first installed font.
        return pygame.font.SysFont("segoeui,arial,helvetica,dejavusans",
                                   size, bold=bold)
    except Exception:  # noqa: BLE001
        return pygame.font.Font(None, size)


FONT_S = _font(20)
FONT_M = _font(26)
FONT_MB = _font(26, bold=True)
FONT_H = _font(32, bold=True)
FONT_L = _font(44, bold=True)
FONT_XL = _font(60, bold=True)


# ---------------------------------------------------------------------------
# Text / layout helpers
# ---------------------------------------------------------------------------

def wrap_text(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    """Greedy word wrap: returns the lines of ``text`` that fit ``max_w``."""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if not cur or font.size(trial)[0] <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def fit_surface(surf: pygame.Surface, max_w: int) -> pygame.Surface:
    """Shrink a rendered text surface so it never exceeds ``max_w``."""
    if max_w > 0 and surf.get_width() > max_w:
        k = max_w / surf.get_width()
        return pygame.transform.smoothscale(
            surf, (max(1, int(max_w)), max(1, int(surf.get_height() * k))))
    return surf


def layout_row(rect: pygame.Rect, widths: list, gap: int = 10,
               group_gap: int = 28, align: str = "center") -> list[pygame.Rect]:
    """Place buttons side by side inside ``rect``.

    ``widths`` holds the desired width of each button; ``None`` inserts a
    wider gap (a visual group separator).  When the row is too wide for
    ``rect`` every width is scaled down proportionally, so the row can
    never overflow the window.  Returns one Rect per non-None entry.
    """
    items = []                                   # (kind, width)
    for i, w in enumerate(widths):
        items.append(("sep", group_gap) if w is None else ("btn", int(w)))
    total = 0
    for i, (kind, w) in enumerate(items):
        total += w
        nxt = items[i + 1][0] if i + 1 < len(items) else None
        if kind == "btn" and nxt == "btn":
            total += gap
    scale = min(1.0, rect.w / total) if total > 0 else 1.0
    total_scaled = int(total * scale)
    if align == "center":
        x = rect.x + (rect.w - total_scaled) // 2
    elif align == "right":
        x = rect.right - total_scaled
    else:
        x = rect.x
    rects = []
    for i, (kind, w) in enumerate(items):
        ws = max(1, int(w * scale))
        if kind == "btn":
            rects.append(pygame.Rect(x, rect.y, ws, rect.h))
        x += ws
        nxt = items[i + 1][0] if i + 1 < len(items) else None
        if kind == "btn" and nxt == "btn":
            x += max(2, int(gap * scale))
    return rects


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------

_STYLES = {
    "primary": (COLORS["accent"], COLORS["text"]),
    "secondary": (COLORS["panel_alt"], COLORS["text"]),
    "danger": (COLORS["danger"], COLORS["text"]),
    "success": (COLORS["success"], (12, 20, 16)),
    "ghost": (COLORS["panel"], COLORS["text"]),
}


class Button:
    """A large, board-friendly button with hover and click feedback."""

    def __init__(self, x, y, w, h, label="", on_click=None, color=None,
                 font=None, enabled=True, style="primary", swatch=None,
                 icon=None, selected=False):
        self.rect = pygame.Rect(int(x), int(y), int(w), int(h))
        self.label = label
        self.on_click = on_click
        base, text = _STYLES.get(style, _STYLES["primary"])
        self.color = color or base
        self.text_color = text
        self.font = font or FONT_M
        self.enabled = enabled
        self.visible = True
        self.selected = selected
        self.swatch = swatch          # RGB tuple -> draws a colour disc
        self.icon = icon              # callable(surface, rect, color)
        self.hovered = False
        self._pressed_until = 0.0
        self._cache: dict = {}

    # -- state -------------------------------------------------------------

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = pygame.Rect(rect)
        self._cache.clear()

    def set_label(self, label: str) -> None:
        self.label = label
        self._cache.clear()

    def contains(self, pos) -> bool:
        return self.visible and self.rect.collidepoint(pos)

    def update(self, pointer_pos) -> None:
        self.hovered = (self.visible and pointer_pos is not None
                        and self.enabled and self.contains(pointer_pos))

    def handle_click(self, pos) -> bool:
        """Returns True if the click was consumed by this button."""
        if self.visible and self.enabled and self.contains(pos):
            self._pressed_until = time.time() + 0.18
            if self.on_click:
                self.on_click()
            return True
        return False

    # -- drawing -----------------------------------------------------------

    def _text(self, color):
        key = (self.label, color, self.rect.w)
        surf = self._cache.get(key)
        if surf is None:
            surf = fit_surface(self.font.render(self.label, True, color),
                               self.rect.w - 14)
            self._cache[key] = surf
        return surf

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        if self.enabled:
            fill, text_color = self.color, self.text_color
            if time.time() < self._pressed_until:
                fill = tuple(min(255, c + 60) for c in fill)
            elif self.hovered:
                fill = tuple(min(255, c + 30) for c in fill)
        else:
            fill, text_color = COLORS["panel"], COLORS["text_dim"]
        radius = max(6, min(14, self.rect.h // 4))
        if self.selected:
            pygame.draw.rect(surface, COLORS["warn"],
                             self.rect.inflate(8, 8), border_radius=radius + 3)
        pygame.draw.rect(surface, fill, self.rect, border_radius=radius)
        pygame.draw.rect(surface, COLORS["border"], self.rect, 2,
                         border_radius=radius)
        if self.swatch is not None:
            r = max(6, min(self.rect.w, self.rect.h) // 2 - 9)
            pygame.draw.circle(surface, self.swatch, self.rect.center, r)
            pygame.draw.circle(surface, (255, 255, 255), self.rect.center,
                               r, 2)
        if self.icon is not None:
            self.icon(surface, self.rect, text_color)
        if self.label:
            t = self._text(text_color)
            surface.blit(t, t.get_rect(center=self.rect.center))


class TileButton(Button):
    """Large menu tile: coloured stripe, title, description, chevron."""

    def __init__(self, rect, title, desc, on_click, accent, submenu=False,
                 danger=False):
        super().__init__(rect.x, rect.y, rect.w, rect.h, title,
                         on_click=on_click, font=FONT_MB)
        self.title = title
        self.desc = desc
        self.accent = COLORS["danger"] if danger else accent
        self.submenu = submenu

    def draw(self, surface):
        if not self.visible:
            return
        r = self.rect
        fill = COLORS["panel_alt"] if self.hovered else COLORS["panel"]
        if time.time() < self._pressed_until:
            fill = tuple(min(255, c + 40) for c in fill)
        pygame.draw.rect(surface, fill, r, border_radius=16)
        border = self.accent if self.hovered else COLORS["border"]
        pygame.draw.rect(surface, border, r, 3 if self.hovered else 2,
                         border_radius=16)
        # Accent stripe on the left edge.
        stripe = pygame.Rect(r.x + 14, r.y + 18, 8, r.h - 36)
        pygame.draw.rect(surface, self.accent, stripe, border_radius=4)
        tx = r.x + 40
        max_w = r.w - 40 - (52 if self.submenu else 24)
        title = fit_surface(FONT_MB.render(self.title, True, COLORS["text"]),
                            max_w)
        surface.blit(title, (tx, r.y + 18))
        y = r.y + 18 + title.get_height() + 6
        for line in wrap_text(FONT_S, self.desc, max_w)[:3]:
            surface.blit(FONT_S.render(line, True, COLORS["text_dim"]),
                         (tx, y))
            y += 24
        if self.submenu:                      # chevron  >
            cx, cy = r.right - 30, r.centery
            pygame.draw.lines(surface, self.accent, False,
                              [(cx - 6, cy - 12), (cx + 6, cy),
                               (cx - 6, cy + 12)], 4)


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------

def draw_bar(surface, rect, border_top=True, border_bottom=False):
    pygame.draw.rect(surface, COLORS["toolbar"], rect)
    if border_top:
        pygame.draw.line(surface, COLORS["border"], rect.topleft,
                         rect.topright, 2)
    if border_bottom:
        pygame.draw.line(surface, COLORS["border"], rect.bottomleft,
                         rect.bottomright, 2)


def draw_card(surface, rect, title=None, accent=None):
    pygame.draw.rect(surface, COLORS["panel"], rect, border_radius=14)
    pygame.draw.rect(surface, COLORS["border"], rect, 2, border_radius=14)
    if title:
        t = FONT_MB.render(title, True, accent or COLORS["accent"])
        surface.blit(t, (rect.x + 18, rect.y + 12))


class Label:
    """Simple text label helper."""

    def __init__(self, x, y, text, font=None, color=None):
        self.x, self.y = x, y
        self.font = font or FONT_M
        self.color = color or COLORS["text"]
        self.set_text(text)

    def set_text(self, text: str) -> None:
        self.surf = self.font.render(text, True, self.color)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.surf, (self.x, self.y))


# ---------------------------------------------------------------------------
# Screen base class
# ---------------------------------------------------------------------------

class Screen:
    """Base class: header (title + Back + Home), toast, click dispatch.

    Subclasses set ``title`` / ``subtitle``, append their buttons to
    ``self.buttons`` and override ``draw_body`` / ``on_body_click`` /
    ``on_right_click`` as needed.
    """

    title = ""
    subtitle = ""
    show_header = True
    has_toolbar = False
    raw_mouse = False        # True: real mouse clicks always accepted

    def __init__(self, app):
        self.app = app
        self.w = app.settings["display_width"]
        self.h = app.settings["display_height"]
        self.buttons: list[Button] = []
        self._toast = ""
        self._toast_until = 0.0
        # Header buttons (always present on every screen except the root).
        self.btn_home = Button(self.w - PAD - 130, 9, 130, HEADER_H - 18,
                               "Home", on_click=app.go_home,
                               style="secondary", font=FONT_S)
        self.btn_back = Button(PAD, 9, 130, HEADER_H - 18, "< Back",
                               on_click=app.go_back, style="secondary",
                               font=FONT_S)
        self.header_buttons = [self.btn_back, self.btn_home]

    # -- geometry ----------------------------------------------------------

    @property
    def header_rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, self.w, HEADER_H if self.show_header else 0)

    @property
    def toolbar_rect(self) -> pygame.Rect:
        if not self.has_toolbar:
            return pygame.Rect(0, self.h - STATUS_H, self.w, 0)
        return pygame.Rect(0, self.h - STATUS_H - TOOLBAR_H, self.w,
                           TOOLBAR_H)

    @property
    def body_rect(self) -> pygame.Rect:
        top = self.header_rect.bottom
        bottom = self.toolbar_rect.top
        return pygame.Rect(0, top, self.w, max(0, bottom - top))

    def toolbar_row_rect(self) -> pygame.Rect:
        t = self.toolbar_rect
        return pygame.Rect(PAD, t.y + 12, self.w - 2 * PAD, t.h - 24)

    # -- helpers -----------------------------------------------------------

    def flash(self, msg: str, seconds: float = 2.5) -> None:
        self._toast = msg
        self._toast_until = time.time() + seconds

    def all_buttons(self) -> list[Button]:
        hdr = self.header_buttons if self.show_header else []
        return list(self.buttons) + list(hdr)

    def on_enter(self) -> None:
        """Called by the app each time this screen becomes current."""

    # -- interaction -------------------------------------------------------

    def on_click(self, pos, button):
        if button == "right":
            return self.on_right_click(pos)
        for b in self.all_buttons():
            if b.handle_click(pos):
                return True
        return self.on_body_click(pos)

    def on_body_click(self, pos):
        return False

    def on_right_click(self, pos):
        """Default secondary action: go back one step."""
        self.app.go_back()
        return True

    def on_hover(self, pos):
        pass

    # -- per frame ---------------------------------------------------------

    def update(self, dt):
        self.btn_back.visible = bool(self.app.screen_stack)
        pointer = self.app.pointer_pos if self.app.pointer_visible else None
        for b in self.all_buttons():
            b.update(pointer)

    # -- rendering ---------------------------------------------------------

    def draw_background(self, s):
        s.fill(COLORS["bg"])

    def draw_body(self, s):
        pass

    def draw_header(self, s):
        r = self.header_rect
        draw_bar(s, r, border_top=False, border_bottom=True)
        left = PAD + (140 if self.btn_back.visible else 0)
        title = FONT_H.render(self.title, True, COLORS["text"])
        title = fit_surface(title, self.w - left - 160 - PAD)
        s.blit(title, (left, 6))
        if self.subtitle:
            sub = fit_surface(FONT_S.render(self.subtitle, True,
                                            COLORS["text_dim"]),
                              self.w - left - 160 - PAD)
            s.blit(sub, (left, 6 + title.get_height() - 2))

    def draw_toast(self, s):
        if self._toast and time.time() < self._toast_until:
            t = FONT_M.render(self._toast, True, COLORS["bg"])
            pill = t.get_rect(center=(self.w // 2,
                                      self.toolbar_rect.top - 34)).inflate(36, 18)
            pygame.draw.rect(s, COLORS["success"], pill, border_radius=18)
            s.blit(t, t.get_rect(center=pill.center))

    def draw(self):
        s = self.app.screen
        self.draw_background(s)
        self.draw_body(s)
        if self.has_toolbar:
            draw_bar(s, self.toolbar_rect)
        if self.show_header:
            self.draw_header(s)
        for b in self.all_buttons():
            b.draw(s)
        self.draw_toast(s)
