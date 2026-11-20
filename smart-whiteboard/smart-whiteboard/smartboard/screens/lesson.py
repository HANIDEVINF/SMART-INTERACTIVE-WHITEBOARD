"""SCREEN: teaching sequence with annotation (uses features/lesson.py)."""
from __future__ import annotations

from ..events import ClickEvent, LEFT
from ..features.drawing import DrawingCanvas
from ..graphics import theme
from ..graphics.widgets import hit
from ..vision import imgproc
from .base import Screen


class LessonScreen(Screen):
    def __init__(self):
        super().__init__()
        self.annotate = False
        self._img_cache = {}

    # -- helpers ----------------------------------------------------------------------------------------
    def ink(self, ctx) -> DrawingCanvas:
        i = ctx.lesson.idx
        if i not in ctx.lesson_ink:
            ctx.lesson_ink[i] = DrawingCanvas(ctx.w, ctx.h)
        return ctx.lesson_ink[i]

    def _goto(self, ctx, step: int):
        self.ink(ctx).lift()
        ok = ctx.lesson.next() if step > 0 else ctx.lesson.prev()
        if not ok:
            ctx.toast("Last page" if step > 0 else "First page", 1.2)
        self.annotate = ctx.lesson.page.type == "draw"

    @property
    def title(self):
        return "Lesson"

    def on_enter(self, ctx):
        self.annotate = ctx.lesson.page.type == "draw"
        self.layout(ctx)

    def on_exit(self, ctx):
        self.ink(ctx).lift()

    # -- layout ------------------------------------------------------------------------------------------
    def layout(self, ctx):
        self.buttons = []
        self.bar = ctx.sc(100)
        y0, y1 = ctx.h - self.bar + ctx.sc(14), ctx.h - ctx.sc(14)
        specs = [("< Prev", lambda c: self._goto(c, -1)), ("Next >", lambda c: self._goto(c, +1)),
                 (lambda: "Annotate: ON" if self.annotate else "Annotate: OFF",
                  lambda c: setattr(self, "annotate", not self.annotate)),
                 ("Colour", lambda c: self.ink(c).set_color((self.ink(c).color_idx + 1) % 5)),
                 ("Undo", lambda c: self.ink(c).undo()),
                 ("Clear ink", lambda c: self.ink(c).clear()),
                 ("< Menu", lambda c: c.nav.back())]
        gap = ctx.sc(12)
        bw = (ctx.w - gap * (len(specs) + 1)) // len(specs)
        for i, (lab, act) in enumerate(specs):
            x = gap + i * (bw + gap)
            self.make_button(ctx, (x, y0, x + bw, y1), lab, act, font=0.75 * ctx.scale)

    def _in_page(self, ctx, pos):
        return pos is not None and ctx.top <= pos[1] < ctx.h - self.bar

    # -- input -------------------------------------------------------------------------------------------
    def update(self, ctx, pos, dt):
        ink = self.ink(ctx)
        if ink.pen_down:
            if self._in_page(ctx, pos):
                ink.move(pos)
            else:
                ink.lift()

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        ink = self.ink(ctx)
        if ev.button == LEFT:
            b = hit(self.buttons, ev.pos)
            if b is not None:
                b.activate(ctx)
            elif self._in_page(ctx, ev.pos):
                if self.annotate:
                    ink.toggle_pen(ev.pos)
                else:
                    self._goto(ctx, +1)            # teacher flow: click on the page = next page
            return True
        # RIGHT: lift pen -> previous page -> menu
        if ink.pen_down:
            ink.lift()
        elif ctx.lesson.idx > 0:
            self._goto(ctx, -1)
        else:
            ctx.nav.back()
        return True

    def status(self, ctx):
        L = ctx.lesson
        return f"{L.title}  -  page {L.idx + 1}/{len(L.pages)}"

    # -- drawing ---------------------------------------------------------------------------------------
    def render(self, ctx, canvas, pos):
        L, s = ctx.lesson, ctx.scale
        p = L.page
        canvas.clear(theme.BG)
        area_h = ctx.h - ctx.top - self.bar
        canvas.text(p.title, ctx.w / 2, ctx.top + ctx.sc(60), 1.6 * s, theme.ACCENT, 3, "cm")

        if p.type == "text":
            y = ctx.top + ctx.sc(170)
            for b in p.bullets:
                canvas.circle((ctx.sc(150), y + ctx.sc(8)), ctx.sc(9), theme.ACCENT)
                canvas.text(b, ctx.sc(190), y, 1.05 * s, theme.TEXT, 2, "lm")
                y += ctx.sc(95)
        elif p.type == "image":
            img = L.image_for(p)
            if img is not None:
                bw, bh = ctx.w - ctx.sc(200), area_h - ctx.sc(250)
                k = min(bw / img.shape[1], bh / img.shape[0])
                tw, th = max(1, int(img.shape[1] * k)), max(1, int(img.shape[0] * k))
                key = (id(img), tw, th)
                if key not in self._img_cache:
                    self._img_cache = {key: imgproc.resize_bilinear(img, tw, th)}
                canvas.blit(self._img_cache[key], (ctx.w - tw) // 2, ctx.top + ctx.sc(120))
            canvas.text(p.caption, ctx.w / 2, ctx.h - self.bar - ctx.sc(60), 0.85 * s, theme.TEXT_DIM, 2, "cm")
        elif p.type == "draw":
            canvas.text(p.prompt, ctx.w / 2, ctx.top + ctx.sc(130), 0.95 * s, theme.TEXT, 2, "cm")
            canvas.outline(ctx.sc(80), ctx.top + ctx.sc(180), ctx.w - ctx.sc(80), ctx.h - self.bar - ctx.sc(30),
                           theme.PANEL_LIGHT, 3)

        ink = self.ink(ctx)
        ink.render_onto(canvas.img, ctx.top)
        canvas.rect(0, ctx.h - self.bar, ctx.w, ctx.h, theme.PANEL)
        self.draw_buttons(canvas, pos)
        if self.annotate and self._in_page(ctx, pos):
            if ink.pen_down:
                canvas.circle(pos, ink.radius, ink.color)
            else:
                canvas.ring(pos, ink.radius + 2, 2, ink.color)
