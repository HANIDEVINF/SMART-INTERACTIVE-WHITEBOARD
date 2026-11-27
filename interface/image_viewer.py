"""Image viewer screen: gallery, display, zoom, pan, reset.

A projected board has no keyboard, so the viewer never depends on the OS
file dialog: pictures placed in ``assets/images/`` appear in an on-board
gallery that is operated with the pointer.  A *Browse* button still opens
the native dialog when tkinter is available (operator convenience).

Zoom / pan model
----------------
The view is described by ``zoom`` (1 = whole image fitted in the board)
and ``center`` (the image point, in 0..1 fractions, shown in the middle).
Only the visible part of the image is cropped and scaled, so even an 8x
zoom of a large photo costs one small ``smoothscale`` -- and the result is
cached until the view changes.

Pointer controls: Zoom +/- buttons, arrow buttons, or simply **click on the
image to centre the view there**.  Right click = step back (zoom out, then
back to the gallery).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

from interface.components import (Button, COLORS, FONT_M, FONT_S, PAD, Screen,
                                  fit_surface, layout_row)
from utils.file_utils import ASSETS_DIR

logger = logging.getLogger(__name__)

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff")


def list_gallery_images(folder: Path | None = None, limit: int = 12) -> list[Path]:
    """Image files found in the assets folder (sorted, at most ``limit``)."""
    folder = Path(folder) if folder else ASSETS_DIR / "images"
    if not folder.is_dir():
        return []
    files = [p for p in sorted(folder.iterdir())
             if p.suffix.lower() in IMAGE_EXTS]
    return files[:limit]


class ImageViewerScreen(Screen):
    title = "Images"
    has_toolbar = True
    MIN_ZOOM = 1.0
    MAX_ZOOM = 8.0

    def __init__(self, app):
        super().__init__(app)
        self.image: pygame.Surface | None = None
        self.image_name = ""
        self.zoom = 1.0
        self.center = (0.5, 0.5)
        self._view_cache = None          # (key, surface, dest_rect)
        self._thumbs: list[tuple[Path, pygame.Surface, pygame.Rect]] = []
        self._gallery_built = False

        rects = layout_row(self.toolbar_row_rect(),
                           [130, None, 80, 80, 100, None, 70, 70, 70, 70,
                            None, 130], gap=10)
        it = iter(rects)
        self.btn_gallery = Button(*next(it), "Gallery", on_click=self._to_gallery,
                                  style="secondary", font=FONT_S)
        self.btn_zoom_out = Button(*next(it), "Zoom -",
                                   on_click=lambda: self._zoom_by(0.8),
                                   font=FONT_S)
        self.btn_zoom_in = Button(*next(it), "Zoom +",
                                  on_click=lambda: self._zoom_by(1.25),
                                  font=FONT_S)
        self.btn_reset = Button(*next(it), "Fit", on_click=self._reset_zoom,
                                style="secondary", font=FONT_S)
        self.btn_left = Button(*next(it), icon=self._arrow(-1, 0),
                               on_click=lambda: self._pan(-1, 0),
                               style="secondary")
        self.btn_up = Button(*next(it), icon=self._arrow(0, -1),
                             on_click=lambda: self._pan(0, -1),
                             style="secondary")
        self.btn_down = Button(*next(it), icon=self._arrow(0, 1),
                               on_click=lambda: self._pan(0, 1),
                               style="secondary")
        self.btn_right = Button(*next(it), icon=self._arrow(1, 0),
                                on_click=lambda: self._pan(1, 0),
                                style="secondary")
        self.btn_browse = Button(*next(it), "Browse...", on_click=self._browse,
                                 style="secondary", font=FONT_S)
        self.view_buttons = [self.btn_zoom_out, self.btn_zoom_in,
                             self.btn_reset, self.btn_left, self.btn_up,
                             self.btn_down, self.btn_right]
        self.buttons = [self.btn_gallery, self.btn_browse] + self.view_buttons

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _arrow(dx, dy):
        def draw(surface, rect, color):
            cx, cy = rect.center
            k = 11
            if dx:
                pts = [(cx - dx * k, cy - k), (cx + dx * k, cy),
                       (cx - dx * k, cy + k)]
            else:
                pts = [(cx - k, cy - dy * k), (cx, cy + dy * k),
                       (cx + k, cy - dy * k)]
            pygame.draw.polygon(surface, color, pts)
        return draw

    @property
    def viewing(self) -> bool:
        return self.image is not None

    def on_enter(self):
        self._gallery_built = False      # re-scan the folder each time

    # -- image handling ----------------------------------------------------

    def load_path(self, path) -> bool:
        """Load an image file; returns True on success."""
        try:
            surf = pygame.image.load(str(path))
            self.image = surf.convert_alpha() if pygame.display.get_surface() \
                else surf
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not load image %s: %s", path, exc)
            self.flash("Invalid image file")
            return False
        self.image_name = Path(path).name
        self.zoom, self.center = 1.0, (0.5, 0.5)
        self._view_cache = None
        self.flash(f"Loaded {self.image_name}")
        return True

    def _browse(self):
        """Native file dialog (needs tkinter; optional)."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Select an image",
                filetypes=[("Image files", " ".join(f"*{e}" for e in IMAGE_EXTS)),
                           ("All files", "*.*")])
            root.destroy()
        except Exception as exc:  # noqa: BLE001 - tkinter may be unavailable
            logger.error("File dialog failed: %s", exc)
            self.flash("File dialog unavailable - put images in assets/images")
            return
        if path:
            self.load_path(path)

    def _to_gallery(self):
        self.image = None
        self._view_cache = None

    # -- zoom / pan --------------------------------------------------------

    def _zoom_by(self, factor: float) -> None:
        if not self.viewing:
            return
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom * factor))
        if self.zoom <= 1.001:
            self.center = (0.5, 0.5)
        self._clamp_center()
        self._view_cache = None

    def _reset_zoom(self) -> None:
        self.zoom, self.center = 1.0, (0.5, 0.5)
        self._view_cache = None

    def _pan(self, dx: int, dy: int) -> None:
        if not self.viewing:
            return
        step = 0.25 / self.zoom                 # a quarter of the view
        self.center = (self.center[0] + dx * step, self.center[1] + dy * step)
        self._clamp_center()
        self._view_cache = None

    def _clamp_center(self) -> None:
        half = 0.5 / self.zoom
        cx = min(max(self.center[0], half), 1 - half)
        cy = min(max(self.center[1], half), 1 - half)
        self.center = (cx, cy)

    def _visible_fraction_rect(self):
        half = 0.5 / self.zoom
        return (self.center[0] - half, self.center[1] - half, 2 * half, 2 * half)

    # -- interaction -------------------------------------------------------

    def on_body_click(self, pos):
        body = self.body_rect
        if not body.collidepoint(pos):
            return False
        if self.viewing:
            # Click on the image = centre the view there.
            cache = self._view_cache
            if cache is None or not cache[2].collidepoint(pos):
                return True
            _, _, dest = cache
            fx, fy, fw, fh = self._visible_fraction_rect()
            self.center = (fx + (pos[0] - dest.x) / dest.w * fw,
                           fy + (pos[1] - dest.y) / dest.h * fh)
            self._clamp_center()
            self._view_cache = None
            return True
        for path, _, rect in self._thumbs:     # gallery
            if rect.collidepoint(pos):
                self.load_path(path)
                return True
        return True

    def on_right_click(self, pos):
        """Step back: zoom out, then close the image, then leave."""
        if self.viewing and self.zoom > 1.001:
            self._zoom_by(0.8)
        elif self.viewing:
            self._to_gallery()
        else:
            self.app.go_back()
        return True

    # -- per-frame ---------------------------------------------------------

    def update(self, dt):
        super().update(dt)
        for b in self.view_buttons:
            b.enabled = self.viewing
        self.btn_zoom_in.enabled = self.viewing and self.zoom < self.MAX_ZOOM - 1e-6
        self.btn_zoom_out.enabled = self.viewing and self.zoom > 1.001
        pan_ok = self.viewing and self.zoom > 1.001
        for b in (self.btn_left, self.btn_up, self.btn_down, self.btn_right):
            b.enabled = pan_ok
        self.subtitle = (f"{self.image_name}   |   zoom {self.zoom:.2f}x"
                         if self.viewing else "Pick an image")

    # -- rendering ---------------------------------------------------------

    def _build_gallery(self):
        self._thumbs = []
        files = list_gallery_images()
        body = self.body_rect.inflate(-2 * (PAD + 8), -2 * PAD)
        if not files:
            self._gallery_built = True
            return
        cols = 3 if len(files) > 2 else len(files)
        rows = -(-len(files) // cols)
        gap = 20
        cell_w = (body.w - gap * (cols - 1)) // cols
        cell_h = min(260, (body.h - gap * (rows - 1)) // rows)
        for i, path in enumerate(files):
            r, c = divmod(i, cols)
            rect = pygame.Rect(body.x + c * (cell_w + gap),
                               body.y + r * (cell_h + gap), cell_w, cell_h)
            try:
                img = pygame.image.load(str(path))
                k = min((rect.w - 16) / img.get_width(),
                        (rect.h - 60) / img.get_height())
                thumb = pygame.transform.smoothscale(
                    img, (max(1, int(img.get_width() * k)),
                          max(1, int(img.get_height() * k))))
            except Exception:  # noqa: BLE001
                continue
            self._thumbs.append((path, thumb, rect))
        self._gallery_built = True

    def draw_body(self, s):
        if not self.viewing:
            self._draw_gallery(s)
            return
        body = self.body_rect
        fx, fy, fw, fh = self._visible_fraction_rect()
        key = (id(self.image), round(self.zoom, 4),
               round(self.center[0], 4), round(self.center[1], 4))
        if self._view_cache is None or self._view_cache[0] != key:
            iw, ih = self.image.get_size()
            src = pygame.Rect(int(fx * iw), int(fy * ih),
                              max(1, int(fw * iw)), max(1, int(fh * ih)))
            src.clamp_ip(pygame.Rect(0, 0, iw, ih))
            # Fit the visible region into the body, preserving aspect.
            k = min((body.w - 2 * PAD) / src.w, (body.h - 2 * PAD) / src.h)
            size = (max(1, int(src.w * k)), max(1, int(src.h * k)))
            surf = pygame.transform.smoothscale(self.image.subsurface(src), size)
            dest = surf.get_rect(center=body.center)
            self._view_cache = (key, surf, dest)
        _, surf, dest = self._view_cache
        s.blit(surf, dest)
        pygame.draw.rect(s, COLORS["border"], dest.inflate(4, 4), 2)

    def _draw_gallery(self, s):
        if not self._gallery_built:
            self._build_gallery()
        if not self._thumbs:
            msg = FONT_M.render("No images found. Put pictures in "
                                "assets/images/ or press Browse...", True,
                                COLORS["text_dim"])
            msg = fit_surface(msg, self.w - 80)
            s.blit(msg, msg.get_rect(center=self.body_rect.center))
            return
        pointer = self.app.pointer_pos if self.app.pointer_visible else None
        for path, thumb, rect in self._thumbs:
            hover = pointer is not None and rect.collidepoint(pointer)
            pygame.draw.rect(s, COLORS["panel_alt"] if hover else COLORS["panel"],
                             rect, border_radius=14)
            pygame.draw.rect(s, COLORS["accent"] if hover else COLORS["border"],
                             rect, 3 if hover else 2, border_radius=14)
            s.blit(thumb, thumb.get_rect(midtop=(rect.centerx, rect.y + 10)))
            name = fit_surface(FONT_S.render(path.stem.replace("_", " "), True,
                                             COLORS["text"]), rect.w - 20)
            s.blit(name, name.get_rect(midbottom=(rect.centerx, rect.bottom - 10)))
