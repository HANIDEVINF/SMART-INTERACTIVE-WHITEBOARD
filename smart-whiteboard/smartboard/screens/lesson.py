"""SCREEN: teaching sequence with annotation + quiz (uses features/lesson.py)."""
from __future__ import annotations

import time

from ..events import ClickEvent, LEFT
from ..features.drawing import DrawingCanvas
from ..graphics import theme
from ..graphics.anim import ease_out
from ..graphics.panels import panel
from ..graphics.widgets import hit
from ..vision import imgproc
from .base import Screen


class LessonScreen(Screen):
    def __init__(self):
        super().__init__()
        self.annotate = False
        self._img_cache = {}
        self._t_page = time.perf_counter()

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
        else:
            self._t_page = time.perf_counter()
        self.annotate = ctx.lesson.page.type == "draw"
        self.layout(ctx)

    @property
    def title(self):
        return "Lesson"

    def on_enter(self, ctx):
        self.annotate = ctx.lesson.page.type == "draw"
        self._t_page = time.perf_counter()
        self.layout(ctx)

    def on_exit(self, ctx):
        self.ink(ctx).lift()

    # -- layout ------------------------------------------------------------------------------------------
    def layout(self, ctx):
        self.buttons = []
        self.bar = ctx.sc(112)
        y0, y1 = ctx.h - self.bar + ctx.sc(18), ctx.h - ctx.sc(18)
        ic = lambda c: self.ink(c)
        specs = [("Prev", "left", lambda c: self._goto(c, -1), None),
                 ("Next", "right", lambda c: self._goto(c, +1), None),
                 (lambda: "Annotate: ON" if self.annotate else "Annotate: OFF", "pen",
                  lambda c: setattr(self, "annotate", not self.annotate), lambda: self.annotate),
                 ("Colour", "circle", lambda c: ic(c).set_color((ic(c).color_idx + 1) % 5), None),
                 ("Undo", "undo", lambda c: ic(c).undo(), None),
                 ("Clear ink", "trash", lambda c: ic(c).clear(), None),
                 ("Menu", "back", lambda c: c.nav.back(), None)]
        gap = ctx.sc(14)
        bw = (ctx.w - gap * (len(specs) + 1) - ctx.sc(40)) // len(specs)
        for i, (lab, icon, act, sel) in enumerate(specs):
            x = ctx.sc(20) + gap + i * (bw + gap)
            self.make_button(ctx, (x, y0, x + bw, y1), lab, act, icon=icon, selected=sel, font=0.6 * ctx.scale,
                             accent=theme.SLATE if lab == "Menu" else theme.CYAN)
        p = ctx.lesson.page
        if p.type == "quiz":                                  # one big card per answer
            n = len(p.options)
            ow, oh, og = min(ctx.sc(1100), ctx.w - ctx.sc(300)), ctx.sc(110), ctx.sc(26)
            ox = (ctx.w - ow) // 2
            oy = ctx.top + ctx.sc(330)
            chosen = ctx.lesson.chosen.get(ctx.lesson.idx)
            for i, text in enumerate(p.options):
                acc = theme.CYAN
                if chosen is not None:
                    acc = theme.GOOD if i == p.answer else (theme.WARN if i == chosen else theme.SLATE)
                self.make_button(ctx, (ox, oy + i * (oh + og), ox + ow, oy + i * (oh + og) + oh),
                                 f"{'ABC'[i]}   {text}", lambda c, i=i: self._answer(c, i),
                                 accent=acc, font=0.95 * ctx.scale,
                                 selected=(lambda i=i: chosen is not None and i in (p.answer, chosen)))

    def _answer(self, ctx, i):
        L = ctx.lesson
        if L.idx in L.chosen:
            ctx.toast("Already answered", 1.0)
            return
        ok = L.choose(i)
        ctx.toast("Correct!" if ok else "Not quite - the right answer is highlighted", 2.5)
        self.layout(ctx)

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
                elif ctx.lesson.page.type != "quiz":
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
        right, total = L.score
        q = f"   -   quiz {right}/{total}" if total else ""
        return f"{L.title}   -   page {L.idx + 1}/{len(L.pages)}{q}"

    # -- drawing ---------------------------------------------------------------------------------------
    def render(self, ctx, canvas, pos):
        L, s = ctx.lesson, ctx.scale
        p = L.page
        canvas.clear()
        # progress bar under the top bar
        k = (L.idx + 1) / len(L.pages)
        canvas.rect(0, ctx.top, ctx.w, ctx.top + ctx.sc(6), theme.PANEL)
        canvas.rect(0, ctx.top, int(ctx.w * k), ctx.top + ctx.sc(6), theme.CYAN)
        slide = ease_out((time.perf_counter() - self._t_page) / 0.35)     # content glides in
        dy = (1 - slide) * 30 * s
        area_h = ctx.h - ctx.top - self.bar
        tcol = theme.TEXT
        canvas.text(p.title, ctx.w / 2, ctx.top + 70 * s + dy, 58 * s, tcol, True, "cm", alpha=slide)
        canvas.rrect(ctx.w / 2 - 70 * s, ctx.top + 112 * s + dy, ctx.w / 2 + 70 * s, ctx.top + 118 * s + dy, 3 * s,
                     theme.CYAN, 1.0, theme.VIOLET)

        if p.type == "text":
            y = ctx.top + 190 * s
            for i, b in enumerate(p.bullets):
                a = ease_out((time.perf_counter() - self._t_page - 0.12 * i) / 0.35)
                yy = y + (1 - a) * 24 * s
                x0, x1 = ctx.sc(150), ctx.w - ctx.sc(150)
                canvas.rrect(x0, yy, x1, yy + 92 * s, 20 * s, theme.CARD_TOP, a, theme.CARD_BOT)
                canvas.circle((x0 + 52 * s, yy + 46 * s), 24 * s, theme.CYAN, a * 0.25)
                canvas.ring((x0 + 52 * s, yy + 46 * s), 24 * s, 2, theme.CYAN, a)
                canvas.text(str(i + 1), x0 + 52 * s, yy + 46 * s, 24 * s, theme.CYAN, True, "cm", alpha=a)
                canvas.text_fit(b, x0 + 106 * s, yy + 46 * s, 34 * s, x1 - x0 - 150 * s, theme.TEXT, False, "lm")
                y += 112 * s
        elif p.type == "image":
            img = L.image_for(p)
            if img is not None:
                bw, bh = ctx.w - ctx.sc(260), area_h - ctx.sc(250)
                k2 = min(bw / img.shape[1], bh / img.shape[0])
                tw, th = max(1, int(img.shape[1] * k2)), max(1, int(img.shape[0] * k2))
                key = (id(img), tw, th)
                if key not in self._img_cache:
                    self._img_cache = {key: imgproc.resize_bilinear(img, tw, th)}
                x, y = (ctx.w - tw) // 2, ctx.top + ctx.sc(150)
                panel(canvas, x - 12 * s, y - 12 * s, x + tw + 12 * s, y + th + 12 * s, 18 * s)
                canvas.blit(self._img_cache[key], x, y)
            canvas.text(p.caption, ctx.w / 2, ctx.h - self.bar - ctx.sc(50), 28 * s, theme.TEXT_DIM, False, "cm")
        elif p.type == "draw":
            canvas.text(p.prompt, ctx.w / 2, ctx.top + 160 * s, 32 * s, theme.TEXT_DIM, False, "cm")
            panel(canvas, ctx.sc(80), ctx.top + ctx.sc(200), ctx.w - ctx.sc(80), ctx.h - self.bar - ctx.sc(30),
                  22 * s, theme.VIOLET)
        elif p.type == "quiz":
            canvas.text_fit(p.question, ctx.w / 2, ctx.top + 220 * s, 40 * s, ctx.w - 300 * s, theme.TEXT, False, "cm")
            right, total = L.score
            canvas.text(f"Score  {right} / {total}", ctx.w - 60 * s, ctx.top + 70 * s, 26 * s, theme.AMBER, True, "rm")

        self.ink(ctx).render_onto(canvas.img, ctx.top)
        panel(canvas, ctx.sc(14), ctx.h - self.bar + ctx.sc(4), ctx.w - ctx.sc(14), ctx.h - ctx.sc(8), ctx.sc(26),
              shadow=False)
        self.draw_buttons(canvas, pos)
        ink = self.ink(ctx)
        if self.annotate and self._in_page(ctx, pos):
            if ink.pen_down:
                canvas.circle(pos, ink.radius, ink.color)
            else:
                canvas.ring(pos, ink.radius + 2, 2, ink.color)
