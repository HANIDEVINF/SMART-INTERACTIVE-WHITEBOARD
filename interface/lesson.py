"""Teaching lesson content and lesson screen.

The lesson is a list of page dictionaries -- easy to extend or replace.
Each page has a title and a list of text lines (\"- \" prefix renders as a
bullet, a 4-space indent renders as code).  Four pages include simple
vector diagrams drawn with Pygame shapes (UI drawing, not part of the CV
pipeline).

Controls: left click anywhere on the page (or Next) = next page; right
click (or Previous) = previous page, and back to the menu from page 1.
That way the presenter never has to aim at a small button.
"""

from __future__ import annotations

import pygame

from interface.components import (Button, COLORS, FONT_M, FONT_S, PAD, Screen,
                                  draw_card, layout_row, wrap_text)

# ---------------------------------------------------------------------------
# Lesson content (easy to edit / extend)
# ---------------------------------------------------------------------------

LESSON_PAGES = [
    {
        "title": "Computer Vision -- Lesson 1",
        "lines": [
            "Welcome! Today we explore how computers 'see'.",
            "",
            "- A camera captures light as a grid of pixels.",
            "- Each pixel stores colour information (BGR).",
            "- Algorithms transform pixels into understanding.",
            "",
            "This whiteboard itself uses computer vision!",
        ],
        "diagram": None,
    },
    {
        "title": "What is an Image?",
        "lines": [
            "- An image is a 2D array of numbers.",
            "- Shape: (height, width, channels).",
            "- Grayscale: 1 channel. Colour: 3 channels (BGR).",
            "",
            "Pixel (x, y) access is the most basic operation:",
            "    value = image[y, x]",
        ],
        "diagram": "pixel_grid",
    },
    {
        "title": "Image Processing Pipeline",
        "lines": [
            "- Step 1: Convert colour spaces (BGR -> HSV).",
            "- Step 2: Threshold to isolate a colour range.",
            "- Step 3: Clean noise with morphology.",
            "- Step 4: Find connected regions (blobs).",
            "- Step 5: Compute centroid = pointer position.",
            "",
            "Each step is implemented manually with NumPy!",
        ],
        "diagram": "pipeline",
    },
    {
        "title": "Object Detection with Colour",
        "lines": [
            "- A bright marker has a distinctive HSV signature.",
            "- HSV separates 'hue' (colour) from lighting.",
            "- Thresholding produces a binary mask of the marker.",
            "- The largest blob's centroid becomes the pointer.",
            "",
            "Limitations: lighting changes, similar-coloured objects.",
        ],
        "diagram": "blob",
    },
    {
        "title": "Perspective & Homography",
        "lines": [
            "- The camera sees the board at an angle (perspective).",
            "- A homography (3x3 matrix) maps camera -> board coords.",
            "- We solve it with 4 clicked corner points (DLT).",
            "- After calibration, pointer positions are accurate.",
        ],
        "diagram": "homography",
    },
    {
        "title": "Summary & Conclusion",
        "lines": [
            "- Images are arrays; pixels are numbers.",
            "- Colour segmentation finds the marker robustly.",
            "- Homography corrects perspective distortion.",
            "- Smoothing + tracking give a stable pointer.",
            "",
            "Thank you! Questions?",
        ],
        "diagram": None,
    },
]


# ---------------------------------------------------------------------------
# Simple vector diagrams (Pygame shapes), scaled to fit their card
# ---------------------------------------------------------------------------

def _draw_diagram(name: str, surface: pygame.Surface, rect: pygame.Rect) -> None:
    cx, cy = rect.center
    k = min(rect.w / 520.0, rect.h / 300.0)       # design size 520 x 300
    K = lambda v: int(v * k)                       # noqa: E731
    if name == "pixel_grid":
        cell = K(40)
        x0 = cx - int(3.5 * cell)
        y0 = cy - int(2.5 * cell)
        for i in range(7):
            for j in range(5):
                color = COLORS["accent"] if (i + j) % 3 == 0 else COLORS["panel_alt"]
                pygame.draw.rect(surface, color,
                                 (x0 + i * cell, y0 + j * cell, cell - 2, cell - 2))
        pygame.draw.rect(surface, COLORS["warn"],
                         (x0 + 2 * cell, y0 + cell, cell - 2, cell - 2), 3)
    elif name == "pipeline":
        steps = ["BGR", "HSV", "Mask", "Blobs", "Point"]
        gap = K(26)
        bw = (rect.w - 40 - gap * (len(steps) - 1)) // len(steps)
        bw = max(40, min(K(110), bw))
        total = len(steps) * bw + (len(steps) - 1) * gap
        x = cx - total // 2
        for i, label in enumerate(steps):
            r = pygame.Rect(x, cy - K(35), bw, K(70))
            pygame.draw.rect(surface, COLORS["panel_alt"], r, border_radius=10)
            pygame.draw.rect(surface, COLORS["accent"], r, 2, border_radius=10)
            t = FONT_S.render(label, True, COLORS["text"])
            surface.blit(t, t.get_rect(center=r.center))
            x += bw
            if i < len(steps) - 1:
                pygame.draw.polygon(surface, COLORS["text_dim"],
                                    [(x + 4, cy), (x + gap - 4, cy - 8),
                                     (x + gap - 4, cy + 8)])
                x += gap
    elif name == "blob":
        pygame.draw.circle(surface, COLORS["panel_alt"], (cx - K(60), cy), K(90))
        pygame.draw.circle(surface, COLORS["success"], (cx - K(60), cy), K(55))
        pygame.draw.circle(surface, COLORS["warn"], (cx - K(60), cy), max(4, K(8)))
        end = (cx + K(100), cy - K(90))
        pygame.draw.line(surface, COLORS["warn"], (cx - K(60), cy), end, 3)
        pygame.draw.circle(surface, COLORS["warn"], end, max(5, K(10)), 2)
    elif name == "homography":
        # Trapezoid (camera view) -> rectangle (board).
        a = cx - K(120)
        pygame.draw.polygon(surface, COLORS["panel_alt"],
                            [(a - K(110), cy - K(60)), (a + K(10), cy - K(90)),
                             (a + K(110), cy + K(60)), (a - K(10), cy + K(90))])
        pygame.draw.polygon(surface, COLORS["accent"],
                            [(cx + K(60), cy - K(70)), (cx + K(220), cy - K(70)),
                             (cx + K(220), cy + K(70)), (cx + K(60), cy + K(70))], 3)
        pygame.draw.line(surface, COLORS["text_dim"],
                         (cx + K(15), cy), (cx + K(50), cy), 3)
        pygame.draw.polygon(surface, COLORS["text_dim"],
                            [(cx + K(50), cy - 7), (cx + K(62), cy),
                             (cx + K(50), cy + 7)])


# ---------------------------------------------------------------------------
# Lesson screen
# ---------------------------------------------------------------------------

class LessonScreen(Screen):
    title = "Lesson"
    has_toolbar = True

    def __init__(self, app):
        super().__init__(app)
        self.page_idx = 0
        rects = layout_row(self.toolbar_row_rect(), [190, 200, 190], gap=24)
        self.btn_prev = Button(*rects[0], "< Previous", on_click=self._prev,
                               style="secondary")
        self.btn_restart = Button(*rects[1], "First page",
                                  on_click=self._first, style="secondary",
                                  font=FONT_S)
        self.btn_next = Button(*rects[2], "Next >", on_click=self._next)
        self.buttons = [self.btn_prev, self.btn_restart, self.btn_next]

    @property
    def page(self):
        return LESSON_PAGES[self.page_idx]

    def on_enter(self):
        self.page_idx = 0

    def _first(self):
        self.page_idx = 0

    def _prev(self):
        self.page_idx = max(0, self.page_idx - 1)

    def _next(self):
        if self.page_idx < len(LESSON_PAGES) - 1:
            self.page_idx += 1
        else:
            self.flash("End of the lesson")

    # -- interaction -------------------------------------------------------

    def on_body_click(self, pos):
        """Left click anywhere on the page = next page."""
        if self.body_rect.collidepoint(pos):
            self._next()
            return True
        return False

    def on_right_click(self, pos):
        """Right click = previous page; from page 1 go back to the menu."""
        if self.page_idx > 0:
            self._prev()
        else:
            self.app.go_back()
        return True

    def update(self, dt):
        super().update(dt)
        self.btn_prev.enabled = self.page_idx > 0
        self.btn_restart.enabled = self.page_idx > 0
        self.btn_next.enabled = self.page_idx < len(LESSON_PAGES) - 1
        self.subtitle = f"Page {self.page_idx + 1} of {len(LESSON_PAGES)}"

    # -- rendering ---------------------------------------------------------

    def _layout_text(self, width, height):
        """Wrap the page text, picking the largest font that fits."""
        for font, lh in ((FONT_M, 40), (FONT_S, 30)):
            rows = []                      # (text, indent, kind)
            for line in self.page["lines"]:
                if line.strip() == "":
                    rows.append(("", 0, "gap"))
                elif line.startswith("- "):
                    for i, seg in enumerate(wrap_text(font, line[2:], width - 40)):
                        rows.append((seg, 34, "bullet" if i == 0 else "cont"))
                elif line.startswith("    "):
                    rows.append((line.strip(), 34, "code"))
                else:
                    for seg in wrap_text(font, line, width):
                        rows.append((seg, 0, "text"))
            h = sum(lh // 2 if r[2] == "gap" else lh for r in rows)
            if h <= height:
                break
        return font, lh, rows

    def draw_body(self, s):
        body = self.body_rect.inflate(-2 * (PAD + 8), -2 * PAD)
        body.y += 4
        diagram = self.page.get("diagram")
        gap = 24
        text_w = int(body.w * 0.54) if diagram else body.w
        text_rect = pygame.Rect(body.x, body.y, text_w, body.h)
        font, lh, rows = self._layout_text(text_rect.w - 8, text_rect.h)

        y = text_rect.y
        for text, indent, kind in rows:
            if kind == "gap":
                y += lh // 2
                continue
            x = text_rect.x + indent
            if kind == "bullet":
                pygame.draw.circle(s, COLORS["accent"], (x - 16, y + lh // 2 - 4), 5)
            color = COLORS["accent"] if kind == "code" else COLORS["text"]
            s.blit(font.render(text, True, color), (x, y))
            y += lh

        if diagram:
            card = pygame.Rect(text_rect.right + gap, body.y,
                               body.right - text_rect.right - gap, body.h)
            card.h = min(card.h, 380)
            card.centery = body.centery
            draw_card(s, card)
            _draw_diagram(diagram, s, card.inflate(-24, -24))

    def draw_toolbar_extras(self, s):
        """Progress dots just above the toolbar."""
        n = len(LESSON_PAGES)
        gap = 22
        total = (n - 1) * gap
        cx = self.w // 2
        y = self.toolbar_rect.top - 16
        for i in range(n):
            x = cx - total // 2 + i * gap
            color = COLORS["accent"] if i == self.page_idx else COLORS["border"]
            pygame.draw.circle(s, color, (x, y), 6 if i == self.page_idx else 4)

    def draw(self):
        super().draw()
        self.draw_toolbar_extras(self.app.screen)
