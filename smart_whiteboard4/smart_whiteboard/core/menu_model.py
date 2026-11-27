"""Menu tree and geometry for the pointer-driven on-board menu.

Pure logic (no Qt): the tree (main menu + submenus), the navigation state (open / current level / back) and the
layout in *board* coordinates, so the same hit-test serves the mouse, the keyboard and the tracked pointer.

Tree:  Main -> Drawing / Image / Presentation / Mode / Settings / Close.
Destructive actions (clear, reset) go through an in-menu confirmation level (Yes / Cancel) so they remain usable with
the pointer alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field

BACK_ID = "@back"
CLOSE_ID = "@close"


@dataclass
class MenuItem:
    id: str
    label: str
    children: list["MenuItem"] | None = None   # submenu
    action: str | None = None                  # action id executed by the page
    flag: str | None = None                    # key in MenuModel.flags -> shows a check mark
    swatch: str | None = None                  # colour preview
    hint: str = ""                             # right-aligned small text (e.g. shortcut)
    danger: bool = False

    @property
    def is_submenu(self) -> bool:
        return self.children is not None


def _confirm(item_id: str, label: str, action: str, question: str) -> MenuItem:
    return MenuItem(item_id, label, children=[
        MenuItem(f"{item_id}.yes", f"Yes - {question}", action=action, danger=True),
        MenuItem(f"{item_id}.no", "Cancel", action="menu.back"),
    ], danger=True)


def build_menu(colors: list[str] | None = None) -> MenuItem:
    colors = colors or ["#1F2937", "#2563EB", "#E11D48", "#16A34A", "#F59E0B", "#7C3AED", "#0D9488", "#78716C"]
    names = ["Black", "Blue", "Red", "Green", "Amber", "Violet", "Teal", "Grey"]
    colour_items = [MenuItem(f"color.{c}", names[i] if i < len(names) else c, action=f"color:{c}", swatch=c,
                             flag=f"color:{c}") for i, c in enumerate(colors)]
    shapes = MenuItem("shapes", "Shapes", children=[
        MenuItem("tool.line", "Line", action="tool:line", flag="tool:line", hint="L"),
        MenuItem("tool.rect", "Rectangle", action="tool:rect", flag="tool:rect", hint="R"),
        MenuItem("tool.circle", "Circle", action="tool:circle", flag="tool:circle", hint="C"),
    ])
    thickness = MenuItem("thickness", "Thickness", children=[
        MenuItem("th.thin", "Thin (3 px)", action="thickness:3", flag="thickness:3"),
        MenuItem("th.medium", "Medium (8 px)", action="thickness:8", flag="thickness:8"),
        MenuItem("th.thick", "Thick (18 px)", action="thickness:18", flag="thickness:18"),
        MenuItem("th.plus", "Thicker", action="thickness:+", hint="]"),
        MenuItem("th.minus", "Thinner", action="thickness:-", hint="["),
    ])
    drawing = MenuItem("drawing", "Drawing", children=[
        MenuItem("tool.pen", "Pen", action="tool:pen", flag="tool:pen", hint="P"),
        MenuItem("tool.eraser", "Eraser", action="tool:eraser", flag="tool:eraser", hint="E"),
        shapes,
        MenuItem("tool.text", "Text", action="tool:text", flag="tool:text", hint="T"),
        MenuItem("colours", "Colours", children=colour_items),
        thickness,
        MenuItem("undo", "Undo", action="undo", hint="Ctrl+Z"),
        MenuItem("redo", "Redo", action="redo", hint="Ctrl+Y"),
        _confirm("clear", "Clear board", "board.clear", "clear the board"),
    ])
    image = MenuItem("image", "Image", children=[
        MenuItem("image.open", "Open image...", action="image.open", hint="Ctrl+O"),
        MenuItem("image.remove", "Remove image", action="image.remove"),
        MenuItem("board.save", "Save as PNG...", action="board.save", hint="Ctrl+S"),
        MenuItem("session.save", "Save session...", action="session.save", hint="Ctrl+Shift+S"),
        MenuItem("session.load", "Load session...", action="session.load", hint="Ctrl+Shift+O"),
        MenuItem("view.in", "Zoom in", action="view:in", hint="+"),
        MenuItem("view.out", "Zoom out", action="view:out", hint="-"),
        MenuItem("view.fit", "Fit to board", action="view:fit", hint="0"),
        MenuItem("view.pan", "Pan (drag the view)", action="view:pan", flag="pan_mode"),
        MenuItem("view.move", "Move view", children=[
            MenuItem("view.left", "Left", action="view:left", hint="Ctrl+Left"),
            MenuItem("view.right", "Right", action="view:right", hint="Ctrl+Right"),
            MenuItem("view.up", "Up", action="view:up", hint="Ctrl+Up"),
            MenuItem("view.down", "Down", action="view:down", hint="Ctrl+Down"),
        ]),
    ])
    presentation = MenuItem("presentation", "Presentation", children=[
        MenuItem("fullscreen", "Fullscreen", action="window.fullscreen", flag="fullscreen", hint="F11"),
        MenuItem("pointer.show", "Show pointer", action="pointer.toggle", flag="pointer_visible"),
        MenuItem("nav.teaching", "Teaching mode", action="nav:teaching"),
        MenuItem("nav.home", "Home screen", action="nav:home", hint="Ctrl+H"),
    ])
    mode = MenuItem("mode", "Mode", children=[
        MenuItem("mode.navigation", "Navigation", action="mode:navigation", flag="mode:navigation", hint="1"),
        MenuItem("mode.drawing", "Drawing", action="mode:drawing", flag="mode:drawing", hint="2"),
        MenuItem("mode.selection", "Selection (dwell)", action="mode:selection", flag="mode:selection", hint="3"),
    ])
    settings = MenuItem("settings", "Settings", children=[
        MenuItem("track.toggle", "Camera pointer", action="track.toggle", flag="tracking", hint="K"),
        MenuItem("nav.calibration", "Calibration", action="nav:calibration"),
        MenuItem("nav.detection", "Detection settings", action="nav:settings"),
        MenuItem("nav.remote", "Remote and keys", action="nav:remote"),
        _confirm("reset", "Reset whiteboard", "board.reset", "reset everything"),
    ])
    return MenuItem("main", "Menu", children=[
        drawing, image, presentation, mode, settings,
        MenuItem(CLOSE_ID, "Close menu", action="menu.close", hint="Esc"),
    ])


@dataclass
class Slot:
    """One laid-out entry: ``rect`` is (x, y, w, h) in board coordinates."""
    id: str
    label: str
    rect: tuple[float, float, float, float]
    item: MenuItem | None
    kind: str = "item"      # item | back | title

    def contains(self, x: float, y: float) -> bool:
        rx, ry, rw, rh = self.rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh


def build_lesson_menu() -> MenuItem:
    """Shown in the main menu only while a lesson is presented (so no entry is ever inert)."""
    return MenuItem("lesson", "Lesson", children=[
        MenuItem("lesson.menu.prev", "Previous page", action="lesson:prev"),
        MenuItem("lesson.menu.next", "Next page", action="lesson:next"),
        MenuItem("lesson.menu.first", "First page", action="lesson:first"),
        MenuItem("lesson.menu.last", "Last page", action="lesson:last"),
        _confirm("lesson.clear", "Clear notes", "lesson:clear", "erase this page's notes"),
        _confirm("lesson.exit", "Leave lesson", "lesson:exit", "back to the editor"),
    ])


class MenuModel:
    ROWS_PER_COLUMN = 6
    MIN_SCALE, MAX_SCALE = 0.8, 1.3

    def __init__(self, root: MenuItem | None = None) -> None:
        self.root = root or build_menu()
        self.scale = 1.0                        # size factor of the whole menu (Settings > General > Interface)
        self.is_open = False
        self.path: list[MenuItem] = []          # submenu stack below root
        self.flags: dict[str, bool] = {}
        self.focus = 0                          # keyboard focus within the current level's entries
        self._by_id: dict[str, MenuItem] = {}
        self._index(self.root)

    def _index(self, item: MenuItem) -> None:
        self._by_id[item.id] = item
        for c in item.children or []:
            self._index(c)

    def set_lesson_active(self, active: bool) -> None:
        """Add / remove the Lesson entry at the top of the main menu."""
        have = any(c.id == "lesson" for c in self.root.children)
        if active and not have:
            item = build_lesson_menu()
            self.root.children.insert(0, item)
            self._index(item)
        elif not active and have:
            self.root.children[:] = [c for c in self.root.children if c.id != "lesson"]
            if self.path and self.path[0].id == "lesson":
                self.close()
        self.focus = 0

    def find(self, item_id: str) -> MenuItem | None:
        return self._by_id.get(item_id)

    # -- state ---------------------------------------------------------------------------------------------------
    @property
    def current(self) -> MenuItem:
        return self.path[-1] if self.path else self.root

    @property
    def title(self) -> str:
        return " / ".join(["Menu"] + [p.label for p in self.path])

    def open(self) -> None:
        self.is_open = True
        self.path.clear()
        self.focus = 0

    def close(self) -> None:
        self.is_open = False
        self.path.clear()
        self.focus = 0

    def toggle(self) -> None:
        self.close() if self.is_open else self.open()

    def back(self) -> str:
        """One level up; closes the menu from the root. Returns "up" | "closed"."""
        if self.path:
            self.path.pop()
            self.focus = 0
            return "up"
        self.close()
        return "closed"

    def entries(self) -> list[MenuItem | None]:
        """Entries of the current level; ``None`` is the Back entry (only in submenus)."""
        items: list[MenuItem | None] = list(self.current.children or [])
        if self.path:
            items.insert(0, None)
        return items

    def activate(self, item_id: str) -> tuple[str, str | None]:
        """Activate an entry. Returns (kind, action): kind is "enter" (submenu entered), "back", "action", "none"."""
        if item_id == BACK_ID:
            self.back()
            return "back", None
        item = self.find(item_id)
        if item is None or not self.is_open:
            return "none", None
        if item.is_submenu:
            self.path.append(item)
            self.focus = 0
            return "enter", None
        return "action", item.action

    # -- keyboard focus --------------------------------------------------------------------------------------------
    def move_focus(self, delta: int) -> str | None:
        n = len(self.entries())
        if n:
            self.focus = (self.focus + delta) % n
        return self.focused_id()

    def focused_id(self) -> str | None:
        ents = self.entries()
        if not ents or not self.is_open:
            return None
        e = ents[min(self.focus, len(ents) - 1)]
        return BACK_ID if e is None else e.id

    # -- geometry ------------------------------------------------------------------------------------------------
    def layout(self, board_w: float, board_h: float) -> list[Slot]:
        """Slots of the current level in board coordinates (empty if closed). Large targets for a shaky pointer."""
        if not self.is_open:
            return []
        ents = self.entries()
        k = min(max(self.scale, self.MIN_SCALE), self.MAX_SCALE)
        item_w, item_h, gap, pad = 340.0 * k, 84.0 * k, 10.0 * k, 18.0 * k
        title_h = 60.0 * k
        x0, y0 = 28.0, 28.0
        # as many rows as fit above the reserved bottom strip (lesson page controls), never more than 6
        fit_rows = int((board_h - y0 - title_h - 2 * pad - 140) // (item_h + gap))
        rows = max(1, min(self.ROWS_PER_COLUMN, max(3, fit_rows), len(ents)))
        cols = -(-len(ents) // rows)
        slots = [Slot("@title", self.title, (x0, y0, cols * item_w + (cols - 1) * gap + 2 * pad, title_h), None, "title")]
        for i, e in enumerate(ents):
            c, r = divmod(i, rows)
            rect = (x0 + pad + c * (item_w + gap), y0 + title_h + pad + r * (item_h + gap), item_w, item_h)
            if e is None:
                slots.append(Slot(BACK_ID, "Back", rect, None, "back"))
            else:
                slots.append(Slot(e.id, e.label, rect, e, "item"))
        return slots

    def panel_rect(self, board_w: float, board_h: float) -> tuple[float, float, float, float] | None:
        slots = self.layout(board_w, board_h)
        if not slots:
            return None
        xs = [s.rect[0] for s in slots]
        ys = [s.rect[1] for s in slots]
        xe = [s.rect[0] + s.rect[2] for s in slots]
        ye = [s.rect[1] + s.rect[3] for s in slots]
        return (min(xs), min(ys), max(xe) + 18 - min(xs), max(ye) + 18 - min(ys))

    def hit(self, x: float, y: float, board_w: float, board_h: float) -> str | None:
        """Id of the clickable entry under (x, y), or None."""
        for s in self.layout(board_w, board_h):
            if s.kind != "title" and s.contains(x, y):
                return s.id
        return None

    def over_panel(self, x: float, y: float, board_w: float, board_h: float) -> bool:
        r = self.panel_rect(board_w, board_h)
        return bool(r) and r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]
