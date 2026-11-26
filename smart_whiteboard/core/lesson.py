"""Teaching mode data model: a lesson is an ordered list of pages (title, text, optional image, notes).

Pure Python (no Qt) so it can be tested without a display.

Text mini-format used by the page renderer::

    - a bullet
    > a highlighted line, e.g. a formula
    any other line is a paragraph;  an empty line adds vertical space
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.menu_model import Slot

LESSON_VERSION = 1
MAX_PAGES = 200


class LessonError(Exception):
    """A lesson file is missing, unreadable or malformed (the message is shown to the user)."""


@dataclass
class LessonPage:
    title: str = "Untitled page"
    text: str = ""
    image: str = ""        # path relative to the lesson file (or absolute); "" = no image
    notes: str = ""        # speaker notes, never drawn on the board

    def clone(self) -> "LessonPage":
        return LessonPage(self.title, self.text, self.image, self.notes)


@dataclass
class Lesson:
    title: str = "New lesson"
    author: str = ""
    pages: list[LessonPage] = field(default_factory=lambda: [LessonPage("Page 1")])
    path: Path | None = None          # where it was loaded from / saved to (None = never saved)

    # -- structure ------------------------------------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.pages)

    def add_page(self, index: int | None = None, page: LessonPage | None = None) -> int:
        if len(self.pages) >= MAX_PAGES:
            raise LessonError(f"A lesson can have at most {MAX_PAGES} pages")
        page = page or LessonPage(f"Page {len(self.pages) + 1}")
        i = len(self.pages) if index is None else max(0, min(index, len(self.pages)))
        self.pages.insert(i, page)
        return i

    def delete_page(self, index: int) -> int:
        """Delete a page (a lesson always keeps at least one). Returns the index to select afterwards."""
        if len(self.pages) <= 1:
            raise LessonError("A lesson needs at least one page")
        del self.pages[index]
        return min(index, len(self.pages) - 1)

    def duplicate_page(self, index: int) -> int:
        return self.add_page(index + 1, self.pages[index].clone())

    def move_page(self, index: int, delta: int) -> int:
        j = index + delta
        if 0 <= j < len(self.pages):
            self.pages[index], self.pages[j] = self.pages[j], self.pages[index]
            return j
        return index

    def image_path(self, page: LessonPage) -> Path | None:
        if not page.image:
            return None
        p = Path(page.image)
        if not p.is_absolute() and self.path is not None:
            p = self.path.parent / p
        return p

    def rebase_images(self, new_dir: Path) -> None:
        """Keep every picture reachable when the lesson file moves to ``new_dir`` (relative if possible, else absolute)."""
        for page in self.pages:
            src = self.image_path(page)
            if src is None:
                continue
            try:
                page.image = Path(os.path.relpath(src, new_dir)).as_posix()
            except ValueError:                       # different drive on Windows
                page.image = str(src)

    # -- persistence -------------------------------------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"version": LESSON_VERSION, "title": self.title, "author": self.author,
                "pages": [asdict(p) for p in self.pages]}

    @classmethod
    def from_dict(cls, data: object) -> "Lesson":
        if not isinstance(data, dict):
            raise LessonError("The file is not a lesson (expected a JSON object)")
        raw = data.get("pages")
        if not isinstance(raw, list) or not raw:
            raise LessonError("The lesson has no pages")
        if len(raw) > MAX_PAGES:
            raise LessonError(f"The lesson has too many pages (maximum {MAX_PAGES})")
        pages = []
        for i, p in enumerate(raw, 1):
            if not isinstance(p, dict):
                raise LessonError(f"Page {i} is malformed")
            pages.append(LessonPage(*(str(p.get(k, d)) for k, d in
                                      (("title", f"Page {i}"), ("text", ""), ("image", ""), ("notes", "")))))
        return cls(str(data.get("title", "Lesson")), str(data.get("author", "")), pages)

    @classmethod
    def load(cls, path: str | Path) -> "Lesson":
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise LessonError(f"'{path.name}' does not exist") from None
        except (OSError, UnicodeDecodeError) as exc:
            raise LessonError(f"'{path.name}' could not be read: {exc}") from None
        except json.JSONDecodeError as exc:
            raise LessonError(f"'{path.name}' is not valid JSON ({exc.msg}, line {exc.lineno})") from None
        lesson = cls.from_dict(data)
        lesson.path = path
        return lesson

    def save(self, path: str | Path | None = None) -> Path:
        """Atomic write (a crash never leaves a half-written lesson)."""
        target = Path(path or self.path or "")
        if not str(target) or target.is_dir():
            raise LessonError("Choose a file name for the lesson")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
            os.replace(tmp, target)
        except OSError as exc:
            raise LessonError(f"Could not save '{target.name}': {exc}") from None
        self.path = target
        return target


class LessonSession:
    """A lesson being presented: current page and the annotations drawn on each page.

    Annotations are kept per page (as BGRA arrays) so that going Next then Previous brings back what was written.
    """

    def __init__(self, lesson: Lesson, index: int = 0) -> None:
        self.lesson = lesson
        self.index = max(0, min(index, len(lesson) - 1))
        self._ink: dict[int, object] = {}

    @property
    def count(self) -> int:
        return len(self.lesson)

    @property
    def page(self) -> LessonPage:
        return self.lesson.pages[self.index]

    @property
    def at_first(self) -> bool:
        return self.index == 0

    @property
    def at_last(self) -> bool:
        return self.index == self.count - 1

    def go(self, index: int) -> bool:
        index = max(0, min(index, self.count - 1))
        changed = index != self.index
        self.index = index
        return changed

    def next(self) -> bool:
        return self.go(self.index + 1)

    def previous(self) -> bool:
        return self.go(self.index - 1)

    def store_ink(self, ink) -> None:
        if ink is not None and bool(ink[..., 3].any()):
            self._ink[self.index] = ink.copy()
        else:
            self._ink.pop(self.index, None)

    def ink_for_current(self):
        return self._ink.get(self.index)

    def annotated_pages(self) -> list[int]:
        return sorted(self._ink)

    @property
    def label(self) -> str:
        return f"Page {self.index + 1} / {self.count}"


def lesson_nav_slots(board_w: float, board_h: float) -> list[Slot]:
    """Clickable page controls drawn at the bottom centre of the board while a lesson is presented."""
    h, w, gap = 84.0, 250.0, 24.0
    page_w = 250.0
    total = 2 * w + page_w + 2 * gap
    x0 = (board_w - total) / 2
    y = board_h - h - 26
    return [Slot("lesson.prev", "Previous", (x0, y, w, h), None, "item"),
            Slot("lesson.label", "", (x0 + w + gap, y, page_w, h), None, "title"),
            Slot("lesson.next", "Next", (x0 + w + gap + page_w + gap, y, w, h), None, "item")]


def lesson_nav_hit(x: float, y: float, board_w: float, board_h: float) -> str | None:
    for s in lesson_nav_slots(board_w, board_h):
        if s.kind != "title" and s.contains(x, y):
            return s.id
    return None
