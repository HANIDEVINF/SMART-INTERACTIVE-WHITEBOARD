"""Phase 6: teaching mode (editor page, presenting on the board, page navigation, annotations)."""
import json

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from core.lesson import Lesson, LessonPage, lesson_nav_slots
from tests.qt_helpers import run_loop, wait_until
from tests.test_gui_interaction import K, click_item, hover, key, qapp, slot_center, win  # noqa: F401  (fixtures)
from ui.teaching_page import DEMO_PATH


def nav_center(which):
    s = next(s for s in lesson_nav_slots(1600, 900) if s.id == f"lesson.{which}")
    return s.rect[0] + s.rect[2] / 2, s.rect[1] + s.rect[3] / 2


def click_nav(win, which):
    c = win.whiteboard.canvas
    QTest.mouseClick(c, Qt.MouseButton.LeftButton, pos=c.board_to_widget(*nav_center(which)).toPoint())
    QApplication.processEvents()


@pytest.fixture
def teach(win):
    win.navigate("teaching", animate=False)
    QApplication.processEvents()
    return win.pages["teaching"]


@pytest.fixture
def presenting(win, teach):
    teach.present_btn.click()
    QApplication.processEvents()
    return win


# --------------------------------------------------------------------------------------------- editor page
def test_demo_lesson_loads_and_previews(teach):
    assert DEMO_PATH.exists()
    assert len(teach.lesson) == 7 and teach.list.count() == 7 and teach.lesson.path.name == "demo_lesson.json"
    assert wait_until(lambda: teach.preview.pixmap() is not None and not teach.preview.pixmap().isNull(), 3000)
    for page in teach.lesson.pages:                         # every picture of the demo exists
        p = teach.lesson.image_path(page)
        assert p is None or p.exists()


def test_editing_marks_dirty_updates_list_and_model(teach):
    assert not teach.dirty
    teach.list.setCurrentRow(2)
    teach.page_title.setText("Renamed")
    teach.page_title.textEdited.emit("Renamed")
    assert teach.dirty and teach.lesson.pages[2].title == "Renamed" and teach.list.item(2).text() == "Renamed"
    teach.text_edit.setPlainText("- new bullet")
    assert teach.lesson.pages[2].text == "- new bullet"
    teach.dirty = False                                     # (avoid the close prompt)


def test_add_duplicate_move_delete_pages(teach):
    n = len(teach.lesson)
    teach.list.setCurrentRow(1)
    teach._add()
    assert len(teach.lesson) == n + 1 and teach.list.currentRow() == 2
    teach._duplicate()
    assert len(teach.lesson) == n + 2
    teach._move(-1)
    assert teach.list.currentRow() == 2
    teach._delete()
    teach._delete()
    assert len(teach.lesson) == n
    teach.dirty = False


def test_last_page_cannot_be_deleted(teach):
    teach.set_lesson(Lesson("x", pages=[LessonPage("only")]))
    toasts = []
    teach.message.connect(lambda t, k: toasts.append(k))
    teach._delete()
    assert len(teach.lesson) == 1 and toasts == ["warn"]


def test_save_as_new_file_rebases_images_and_reloads(teach, tmp_path, monkeypatch):
    target = tmp_path / "mine" / "lesson.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    teach.page_title.setText("Edited")
    teach.page_title.textEdited.emit("Edited")
    assert teach.save()                                      # demo is built-in: Save asks for a new file
    assert not teach.dirty and target.exists()
    back = Lesson.load(target)
    assert back.pages[0].title == "Edited"
    for page in back.pages:
        p = back.image_path(page)
        assert p is None or p.exists()                       # pictures still found from the new location
    assert teach.settings.get("teaching.last_lesson") == str(target)


def test_save_cancel_keeps_unsaved_state(teach, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    teach.text_edit.setPlainText("changed")
    assert teach.dirty and not teach.save() and teach.dirty
    teach.dirty = False


def test_corrupt_lesson_file_is_reported_and_current_lesson_kept(teach, tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: shown.append(a[2]))
    before = teach.lesson
    assert teach._open(bad) is False
    assert teach.lesson is before and shown and "not valid JSON" in shown[0]


def test_missing_image_shows_a_warning_and_a_placeholder_not_a_crash(teach):
    teach.list.setCurrentRow(1)
    teach.set_page_image("/nowhere/pic.png")
    assert "not found" in teach.image_label.text()
    teach._render_preview()
    teach.dirty = False


def test_unsaved_lesson_blocks_closing_until_confirmed(teach, monkeypatch, win):
    teach.text_edit.setPlainText("changed")
    calls = []
    monkeypatch.setattr(type(teach), "confirm_discard", lambda self: calls.append(1) or False)
    win.close()
    assert calls and win.isVisible()                          # cancelled: window stays
    teach.dirty = False                                       # so the fixture can close the window silently


# ------------------------------------------------------------------------------------------- presenting
def test_present_shows_page_one_with_controls_and_lesson_menu(presenting):
    w = presenting
    wb = w.whiteboard
    assert w.current_page == "whiteboard" and wb.lesson_active
    assert wb.canvas.lesson_label == "Page 1 / 7" and not wb.canvas.lesson_can_prev and wb.canvas.lesson_can_next
    assert wb.engine.has_background and wb.engine.source.shape[:2] == (1800, 3200)
    key(w, K.Key_M)
    assert wb.menu.entries()[0].id == "lesson"


def test_next_and_previous_buttons_with_the_mouse(presenting):
    wb = presenting.whiteboard
    click_nav(presenting, "next")
    assert wb.session.index == 1 and wb.canvas.lesson_label == "Page 2 / 7" and wb.canvas.lesson_can_prev
    click_nav(presenting, "prev")
    assert wb.session.index == 0
    click_nav(presenting, "prev")                              # already first: nothing happens
    assert wb.session.index == 0
    for _ in range(10):
        click_nav(presenting, "next")
    assert wb.session.index == 6 and not wb.canvas.lesson_can_next


def test_remote_next_click_on_the_next_control_turns_the_page(presenting):
    w = presenting
    wb = w.whiteboard
    hover(w, *nav_center("next"))
    assert wb.canvas.menu_hover == "lesson.next"
    key(w, K.Key_Right)                                        # remote Next = left click at the pointer
    assert wb.session.index == 1
    run_loop(300)
    hover(w, *nav_center("prev"))
    key(w, K.Key_Right)
    assert wb.session.index == 0


def test_selection_mode_dwell_turns_the_page(presenting):
    w = presenting
    wb = w.whiteboard
    wb.set_dwell_ms(300)
    key(w, K.Key_3)
    hover(w, *nav_center("next"))
    assert wait_until(lambda: wb.session.index == 1, 3000)


def test_annotations_are_kept_per_page(presenting):
    wb = presenting.whiteboard
    wb.engine.draw_line((100, 100), (600, 300), (37, 99, 235), 8)
    click_nav(presenting, "next")
    assert not wb.engine.has_ink and not wb.engine.can_undo
    wb.engine.draw_line((900, 600), (1200, 650), (0, 0, 0), 8)
    click_nav(presenting, "prev")
    assert wb.engine.has_ink and wb.engine.ink[100:104, 98:104, 3].any() and not wb.engine.ink[600:650, 900:1200, 3].any()
    click_nav(presenting, "next")
    assert wb.engine.ink[600:660, 900:1200, 3].any()


def test_lesson_submenu_last_page_clear_notes_and_leave(presenting):
    w = presenting
    wb = w.whiteboard
    key(w, K.Key_M)
    click_item(w, "lesson")
    click_item(w, "lesson.menu.last")
    assert wb.session.index == 6
    wb.engine.draw_line((100, 100), (600, 300), (0, 0, 0), 8)
    click_item(w, "lesson.clear")
    click_item(w, "lesson.clear.no")
    assert wb.engine.has_ink
    click_item(w, "lesson.clear")
    click_item(w, "lesson.clear.yes")
    assert not wb.engine.has_ink and not wb.menu.is_open
    key(w, K.Key_M)
    click_item(w, "lesson")
    click_item(w, "lesson.exit")
    click_item(w, "lesson.exit.yes")
    assert not wb.lesson_active and w.current_page == "teaching" and not wb.engine.has_background
    key_after = [c.id for c in wb.menu.root.children]
    assert "lesson" not in key_after and wb.canvas.lesson_label is None


def test_zoom_and_draw_on_a_lesson_page_then_turn_the_page(presenting):
    wb = presenting.whiteboard
    wb.canvas.zoom_in()
    wb.canvas.zoom_in()
    wb.canvas.grab()                                           # the layered path renders the 2x source
    click_nav(presenting, "next")
    assert wb.canvas.view.is_identity                          # every page starts fully visible


def test_images_cannot_be_replaced_while_presenting(presenting):
    wb = presenting.whiteboard
    toasts = []
    wb.message.connect(lambda t, k: toasts.append(k))
    wb.execute_action("image.remove")
    assert wb.engine.has_background and toasts[-1] == "warn"


def test_reset_leaves_the_lesson(presenting):
    wb = presenting.whiteboard
    wb.reset()
    assert not wb.lesson_active and wb.canvas.lesson_label is None


def test_start_page_index_and_single_page_lesson(win, teach):
    teach.set_lesson(Lesson("one", pages=[LessonPage("Only", "- a")]))
    teach.present(0)
    wb = win.whiteboard
    assert wb.canvas.lesson_label == "Page 1 / 1" and not wb.canvas.lesson_can_next
    click_nav(win, "next")
    assert wb.session.index == 0
    wb.exit_lesson()
    teach.set_lesson(Lesson.load(DEMO_PATH))
    teach.present(3)
    assert wb.session.index == 3


# ------------------------------------------------------------------------------------ interface settings
def test_interface_settings_apply_to_the_board(win):
    st = win.pages["settings"]
    wb = win.whiteboard
    st.hud_box.setChecked(False)
    st.ripple_box.setChecked(False)
    assert not wb.canvas.show_hud and not wb.canvas.show_ripples
    hover(win, 900, 450)
    key(win, K.Key_Right)
    assert wb.canvas.ripples == []                            # rings disabled
    st.menu_scale.set_value(130)
    st._on_interface()
    assert wb.menu.scale == pytest.approx(1.3) and win.settings.get("interface.menu_scale") == 1.3
    win.reset_application()
    assert wb.canvas.show_hud and wb.menu.scale == 1.0 and st.hud_box.isChecked()
