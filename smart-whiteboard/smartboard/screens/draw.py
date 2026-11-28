"""SCREEN: free drawing + shapes (uses features/drawing.py)."""
from __future__ import annotations

from ..events import ClickEvent, LEFT, RIGHT
from ..features.drawing import SHAPE_TOOLS
from ..graphics import primitives as P
from ..graphics import theme
from ..graphics.panels import label, panel
from ..graphics.widgets import hit
from .base import Screen

TOOL_ICONS = {"pen": "pen", "eraser": "eraser", "line": "line", "arrow": "arrow", "rect": "rect", "ellipse": "circle"}
TOOL_LABELS = {"pen": "Pen", "eraser": "Eraser", "line": "Line", "arrow": "Arrow", "rect": "Box", "ellipse": "Circle"}


class DrawScreen(Screen):
    title = "Free drawing"

    def layout(self, ctx):
        self.buttons = []
        d, sc = ctx.drawing, ctx.sc
        x0, y = sc(16), ctx.top + sc(18)
        self.tb_w = sc(352)
        inner = self.tb_w - 2 * x0
        gap, bh = sc(10), sc(58)
        half = (inner - gap) // 2
        self._labels = []

        def section(text):
            nonlocal y
            self._labels.append((text, x0 + sc(6), y + sc(10)))
            y += sc(26)

        section("Tool")
        for i, t in enumerate(("pen", "eraser", "line", "arrow", "rect", "ellipse")):
            cx, cy = x0 + (i % 2) * (half + gap), y + (i // 2) * (bh + gap)
            self.make_button(ctx, (cx, cy, cx + half, cy + bh), TOOL_LABELS[t], lambda c, t=t: d.set_tool(t),
                             icon=TOOL_ICONS[t], selected=lambda t=t: d.tool == t)
        y += 3 * (bh + gap) + sc(2)

        section("Colour")
        sw = (inner - 2 * gap) // 3
        sh = sc(48)
        for i, (name, col) in enumerate(theme.PEN_COLORS):
            cx, cy = x0 + (i % 3) * (sw + gap), y + (i // 3) * (sh + gap)
            self.make_button(ctx, (cx, cy, cx + sw, cy + sh), name, lambda c, i=i: d.set_color(i),
                             selected=lambda i=i: d.color_idx == i and not d.eraser, swatch=col)
        y += 2 * (sh + gap) + sc(2)

        section("Thickness")
        tw = (inner - 2 * gap) // 3
        for i, (name, _) in enumerate(theme.PEN_SIZES):
            cx = x0 + i * (tw + gap)
            self.make_button(ctx, (cx, y, cx + tw, y + sc(50)), name, lambda c, i=i: d.set_size(i),
                             selected=lambda i=i: d.size_idx == i, font=0.58 * ctx.scale)
        y += sc(50) + gap + sc(4)

        section("Board")
        for i, (name, _) in enumerate(theme.BOARDS):
            cx = x0 + i * (tw + gap)
            self.make_button(ctx, (cx, y, cx + tw, y + sc(50)), name, lambda c, i=i: self.set_board(c, i),
                             selected=lambda i=i: ctx.board_idx == i, font=0.58 * ctx.scale, accent=theme.VIOLET)
        y += sc(50) + gap + sc(8)

        acts = [("Undo", "undo", lambda c: d.undo()), ("Redo", "redo", lambda c: d.redo()),
                ("Clear", "trash", lambda c: (d.clear(), c.toast("Drawing cleared"))),
                ("Save", "save", lambda c: c.toast("Saved: " + c.save_snapshot(), 3.0))]
        for i, (name, ic, fn) in enumerate(acts):
            cx, cy = x0 + (i % 2) * (half + gap), y + (i // 2) * (sc(52) + gap)
            self.make_button(ctx, (cx, cy, cx + half, cy + sc(52)), name, fn, icon=ic,
                             accent=theme.AMBER if name == "Clear" else theme.CYAN, font=0.62 * ctx.scale)
        y += 2 * (sc(52) + gap)
        self.make_button(ctx, (x0, y, x0 + inner, y + sc(52)), "Menu", lambda c: c.nav.back(), icon="back",
                         accent=theme.SLATE, font=0.62 * ctx.scale)

    def set_board(self, ctx, i):
        d = ctx.drawing
        ctx.board_idx = i
        names = [n for n, _ in theme.PEN_COLORS]
        if i == 1 and d.color_idx == names.index("White"):
            d.color_idx = names.index("Ink")             # keep the pen visible on a light board
        elif i != 1 and d.color_idx == names.index("Ink"):
            d.color_idx = names.index("White")

    def on_exit(self, ctx):
        ctx.drawing.lift()

    def _on_canvas(self, ctx, pos) -> bool:
        return pos is not None and pos[0] > self.tb_w and pos[1] > ctx.top

    def update(self, ctx, pos, dt):
        d = ctx.drawing
        if d.active and not self._on_canvas(ctx, pos):
            d.lift()                       # pointer left the drawing area: lift the pen
        elif d.active:
            d.move(pos)

    def on_click(self, ctx, ev: ClickEvent) -> bool:
        d = ctx.drawing
        if ev.button == LEFT:
            b = hit(self.buttons, ev.pos)
            if b is not None:
                b.activate(ctx)
            elif self._on_canvas(ctx, ev.pos):
                d.toggle_pen(ev.pos)
                if d.tool in SHAPE_TOOLS:
                    ctx.toast("Move, then click to place the %s" % TOOL_LABELS[d.tool].lower()
                              if d.anchor is not None else "Placed", 1.4)
                else:
                    ctx.toast("Pen DOWN - move to draw" if d.pen_down else "Pen UP", 1.2)
            return True
        # RIGHT: cancel / lift the pen if drawing, otherwise leave
        if d.active:
            d.lift()
            ctx.toast("Cancelled", 1.0)
        else:
            ctx.nav.back()
        return True

    def status(self, ctx):
        d = ctx.drawing
        if d.tool in SHAPE_TOOLS:
            return f"{TOOL_LABELS[d.tool]}: NEXT = first corner, NEXT again = place    PREV = cancel"
        return f"Pen {'DOWN' if d.pen_down else 'UP'}   -   NEXT = pen down / up    PREV = lift / back"

    def render(self, ctx, canvas, pos):
        d = ctx.drawing
        canvas.img[:] = ctx.board_background()
        d.render_onto(canvas.img, ctx.top)
        # shape preview (not stored until the second click)
        col = d.color
        for a, b in d.preview():
            P.aa_segment(canvas.img, a, b, d.radius, col, 0.75)
        if d.anchor is not None:
            canvas.circle(d.anchor, d.radius + 4, theme.WHITE, 0.9)
        panel(canvas, ctx.sc(8), ctx.top + ctx.sc(8), self.tb_w - ctx.sc(8), ctx.h - ctx.sc(12), ctx.sc(24))
        for text, x, yy in self._labels:
            label(canvas, text, x, yy, 14 * ctx.scale)
        self.draw_buttons(canvas, pos)
        if self._on_canvas(ctx, pos):          # pen preview under the pointer
            c = theme.WHITE if d.eraser else d.color
            if d.pen_down and d.tool in ("pen", "eraser"):
                canvas.circle(pos, d.radius, c)
            else:
                canvas.ring(pos, d.radius + 2, 2, c, 0.9)
