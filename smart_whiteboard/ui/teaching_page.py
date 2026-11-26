"""Teaching mode: lesson library/editor. "Present" hands the lesson to the whiteboard, which shows one page at a time."""
from __future__ import annotations

from pathlib import Path

import cv2
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from core.lesson import Lesson, LessonError, LessonPage
from core.settings import DATA_DIR, Settings
from ui.lesson_render import render_page

LESSON_DIR = DATA_DIR / "lessons"
DEMO_PATH = LESSON_DIR / "demo_lesson.json"
FILTER = "Lesson (*.json)"


def _panel() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("panel")
    v = QVBoxLayout(f)
    v.setContentsMargins(14, 12, 14, 14)
    v.setSpacing(8)
    return f, v


class TeachingPage(QWidget):
    presentRequested = Signal(object, int)      # Lesson, first page index
    message = Signal(str, str)
    homeRequested = Signal()

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self.settings = settings
        self.lesson = Lesson()
        self.dirty = False
        self._loading = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(250)
        self._preview_timer.timeout.connect(self._render_preview)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        # ---- header -----------------------------------------------------------------------------------
        head = QHBoxLayout()
        col = QVBoxLayout()
        h1 = QLabel("Teaching Mode")
        h1.setObjectName("h2")
        self.status = QLabel("")
        self.status.setObjectName("muted")
        col.addWidget(h1)
        col.addWidget(self.status)
        head.addLayout(col, 1)
        for text, slot in (("New", self.new_lesson), ("Open...", self.open_dialog), ("Demo lesson", self.load_demo),
                           ("Save", self.save), ("Save as...", self.save_as)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=slot: s())
            head.addWidget(b)
            if text == "Save":
                self.save_btn = b
        self.present_btn = QPushButton("Present from start")
        self.present_btn.setObjectName("primary")
        self.present_btn.clicked.connect(lambda: self.present(0))
        head.addWidget(self.present_btn)
        root.addLayout(head)

        meta, mv = _panel()
        row = QHBoxLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Lesson title")
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Author")
        row.addWidget(QLabel("Lesson"))
        row.addWidget(self.title_edit, 2)
        row.addWidget(self.author_edit, 1)
        mv.addLayout(row)
        root.addWidget(meta)

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        # ---- page list ----------------------------------------------------------------------------------
        left, lv = _panel()
        left.setFixedWidth(270)
        t = QLabel("Pages")
        t.setObjectName("panelTitle")
        lv.addWidget(t)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_row)
        lv.addWidget(self.list, 1)
        r1, r2 = QHBoxLayout(), QHBoxLayout()
        for text, slot, row_ in (("Add", self._add, r1), ("Duplicate", self._duplicate, r1),
                                 ("Up", lambda: self._move(-1), r2), ("Down", lambda: self._move(1), r2),
                                 ("Delete", self._delete, r2)):
            b = QPushButton(text)
            b.setObjectName("preset")
            b.clicked.connect(lambda _=False, s=slot: s())
            row_.addWidget(b)
        lv.addLayout(r1)
        lv.addLayout(r2)
        body.addWidget(left)

        # ---- editor -------------------------------------------------------------------------------------
        mid, ev = _panel()
        t = QLabel("Page")
        t.setObjectName("panelTitle")
        ev.addWidget(t)
        self.page_title = QLineEdit()
        self.page_title.setPlaceholderText("Page title")
        ev.addWidget(self.page_title)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Page text...")
        ev.addWidget(self.text_edit, 3)
        hint = QLabel("<b>- </b>bullet &nbsp;&nbsp; <b>&gt; </b>highlighted line / formula &nbsp;&nbsp; other lines are paragraphs")
        hint.setObjectName("muted")
        ev.addWidget(hint)
        img_row = QHBoxLayout()
        self.image_label = QLabel("No image")
        self.image_label.setObjectName("muted")
        choose = QPushButton("Choose image...")
        choose.clicked.connect(self._choose_image)
        remove = QPushButton("Remove")
        remove.clicked.connect(self._remove_image)
        img_row.addWidget(self.image_label, 1)
        img_row.addWidget(choose)
        img_row.addWidget(remove)
        ev.addLayout(img_row)
        nl = QLabel("Speaker notes (not shown on the board)")
        nl.setObjectName("muted")
        ev.addWidget(nl)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setMaximumHeight(84)
        ev.addWidget(self.notes_edit)
        body.addWidget(mid, 3)

        # ---- preview ------------------------------------------------------------------------------------
        right, rv = _panel()
        t = QLabel("Preview")
        t.setObjectName("panelTitle")
        rv.addWidget(t)
        self.preview = QLabel()
        self.preview.setMinimumSize(360, 202)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background: #FAF9F6; border: 1px solid #E4E1D8; border-radius: 8px;")
        rv.addWidget(self.preview)
        self.present_here = QPushButton("Present from this page")
        self.present_here.clicked.connect(lambda: self.present(max(0, self.list.currentRow())))
        rv.addWidget(self.present_here)
        info = QLabel("While presenting: Next / Previous controls sit at the bottom of the board and work with the "
                      "mouse, the remote's left click and the pointer. Notes you write stay on each page.")
        info.setWordWrap(True)
        info.setObjectName("muted")
        rv.addWidget(info)
        rv.addStretch(1)
        body.addWidget(right, 2)

        for w, slot in ((self.title_edit, self._on_meta), (self.author_edit, self._on_meta)):
            w.textEdited.connect(lambda _t, s=slot: s())
        self.page_title.textEdited.connect(lambda _t: self._on_page_edit())
        self.text_edit.textChanged.connect(self._on_page_edit)
        self.notes_edit.textChanged.connect(self._on_page_edit)

        self._load_initial()

    # ------------------------------------------------------------------------------------- lifecycle
    def _load_initial(self) -> None:
        last = str(self.settings.get("teaching.last_lesson", "") or "")
        for candidate in (last, str(DEMO_PATH)):
            if candidate and Path(candidate).exists():
                try:
                    self.set_lesson(Lesson.load(candidate))
                    return
                except LessonError:
                    continue
        self.set_lesson(Lesson("New lesson", pages=[LessonPage("Page 1", "- first point")]))

    def set_lesson(self, lesson: Lesson, dirty: bool = False) -> None:
        self.lesson, self.dirty = lesson, dirty
        self._loading = True
        self.title_edit.setText(lesson.title)
        self.author_edit.setText(lesson.author)
        self._loading = False
        self._fill_list(0)
        self._update_status()

    def activate(self) -> None:
        self._render_preview()

    # --------------------------------------------------------------------------------------- list/model
    def _fill_list(self, select: int) -> None:
        self._loading = True
        self.list.clear()
        for i, p in enumerate(self.lesson.pages, 1):
            self.list.addItem(p.title)
        self._loading = False
        self.list.setCurrentRow(max(0, min(select, len(self.lesson) - 1)))
        self._on_row(self.list.currentRow())

    def _on_row(self, row: int) -> None:
        if self._loading or row < 0 or row >= len(self.lesson):
            return
        page = self.lesson.pages[row]
        self._loading = True
        self.page_title.setText(page.title)
        self.text_edit.setPlainText(page.text)
        self.notes_edit.setPlainText(page.notes)
        self._loading = False
        self._update_image_label()
        self._preview_timer.start()

    def _current(self) -> LessonPage | None:
        row = self.list.currentRow()
        return self.lesson.pages[row] if 0 <= row < len(self.lesson) else None

    def _mark_dirty(self) -> None:
        self.dirty = True
        self._update_status()

    def _on_meta(self) -> None:
        if self._loading:
            return
        self.lesson.title = self.title_edit.text()
        self.lesson.author = self.author_edit.text()
        self._mark_dirty()
        self._preview_timer.start()

    def _on_page_edit(self) -> None:
        page = self._current()
        if self._loading or page is None:
            return
        page.title = self.page_title.text()
        page.text = self.text_edit.toPlainText()
        page.notes = self.notes_edit.toPlainText()
        item = self.list.currentItem()
        if item is not None:
            item.setText(page.title)
        self._mark_dirty()
        self._preview_timer.start()

    def _add(self) -> None:
        try:
            i = self.lesson.add_page(self.list.currentRow() + 1)
        except LessonError as exc:
            self.message.emit(str(exc), "warn")
            return
        self._mark_dirty()
        self._fill_list(i)

    def _duplicate(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        try:
            i = self.lesson.duplicate_page(row)
        except LessonError as exc:
            self.message.emit(str(exc), "warn")
            return
        self._mark_dirty()
        self._fill_list(i)

    def _delete(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        try:
            i = self.lesson.delete_page(row)
        except LessonError as exc:
            self.message.emit(str(exc), "warn")
            return
        self._mark_dirty()
        self._fill_list(i)

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        j = self.lesson.move_page(row, delta)
        if j != row:
            self._mark_dirty()
            self._fill_list(j)

    # ------------------------------------------------------------------------------------------- image
    def _update_image_label(self) -> None:
        page = self._current()
        if page is None or not page.image:
            self.image_label.setText("No image")
            self.image_label.setStyleSheet("")
            return
        path = self.lesson.image_path(page)
        ok = path is not None and path.exists()
        self.image_label.setText(Path(page.image).name + ("" if ok else "   (file not found)"))
        self.image_label.setStyleSheet("" if ok else "color: #E11D48; font-weight: 700;")

    def _choose_image(self) -> None:
        page = self._current()
        if page is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose a picture", str(LESSON_DIR),
                                              "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.set_page_image(path)

    def set_page_image(self, path: str) -> None:
        page = self._current()
        if page is None:
            return
        p = Path(path)
        if self.lesson.path is not None:
            try:
                p = Path(p.resolve().relative_to(self.lesson.path.parent.resolve()))
            except ValueError:
                pass
        page.image = p.as_posix() if not p.is_absolute() else str(p)
        self._mark_dirty()
        self._update_image_label()
        self._preview_timer.start()

    def _remove_image(self) -> None:
        page = self._current()
        if page is not None and page.image:
            page.image = ""
            self._mark_dirty()
            self._update_image_label()
            self._preview_timer.start()

    # ----------------------------------------------------------------------------------------- preview
    def _render_preview(self) -> None:
        if not self.isVisible() and self.preview.pixmap() is not None and not self.preview.pixmap().isNull():
            return
        row = self.list.currentRow()
        if not 0 <= row < len(self.lesson):
            return
        w = max(360, self.preview.width())
        h = w * 9 // 16
        img = render_page(self.lesson, row, w * 2, h * 2)
        img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        qimg = QImage(img.data, w, h, img.strides[0], QImage.Format.Format_BGR888).copy()
        self.preview.setPixmap(QPixmap.fromImage(qimg))

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self._preview_timer.start()

    # ------------------------------------------------------------------------------------ file actions
    def _update_status(self) -> None:
        name = self.lesson.path.name if self.lesson.path else "not saved yet"
        built_in = self.lesson.path is not None and self.lesson.path.resolve() == DEMO_PATH.resolve()
        tag = "   (demo: Save asks for a new file)" if built_in else ""
        self.status.setText(f"{len(self.lesson)} pages   -   {name}{tag}{'   *  unsaved changes' if self.dirty else ''}")

    def confirm_discard(self) -> bool:
        """True when it is fine to replace / close the current lesson (asks when there are unsaved changes)."""
        if not self.dirty:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Unsaved lesson")
        box.setText(f"Save the changes to \"{self.lesson.title}\"?")
        save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return self.save()
        return clicked is discard

    def new_lesson(self) -> None:
        if self.confirm_discard():
            self.set_lesson(Lesson("New lesson", pages=[LessonPage("Page 1", "- first point")]), dirty=True)

    def load_demo(self) -> None:
        if self.confirm_discard():
            self._open(DEMO_PATH)

    def open_dialog(self) -> None:
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open a lesson", str(LESSON_DIR), FILTER)
        if path:
            self._open(Path(path))

    def _open(self, path: Path) -> bool:
        try:
            lesson = Lesson.load(path)
        except LessonError as exc:
            QMessageBox.warning(self, "Cannot open the lesson", str(exc))
            return False
        self.set_lesson(lesson)
        self.settings.set("teaching.last_lesson", str(path))
        self.message.emit(f"Opened \"{lesson.title}\"", "success")
        return True

    def save(self) -> bool:
        built_in = self.lesson.path is not None and self.lesson.path.resolve() == DEMO_PATH.resolve()
        if self.lesson.path is None or built_in:
            return self.save_as()
        return self._write(None)

    def save_as(self) -> bool:
        default = LESSON_DIR / "my_lesson.json"
        path, _ = QFileDialog.getSaveFileName(self, "Save the lesson", str(default), FILTER)
        if not path:
            return False
        if not path.lower().endswith(".json"):
            path += ".json"
        return self._write(Path(path))

    def _write(self, path: Path | None) -> bool:
        try:
            if path is not None:
                self.lesson.rebase_images(path.parent)
            saved = self.lesson.save(path)
        except LessonError as exc:
            QMessageBox.warning(self, "Cannot save the lesson", str(exc))
            return False
        self.dirty = False
        self.settings.set("teaching.last_lesson", str(saved))
        self._update_status()
        self._update_image_label()
        self.message.emit(f"Lesson saved: {saved.name}", "success")
        return True

    # ----------------------------------------------------------------------------------------- present
    def present(self, index: int = 0) -> None:
        if not len(self.lesson):
            return
        self.presentRequested.emit(self.lesson, index)
