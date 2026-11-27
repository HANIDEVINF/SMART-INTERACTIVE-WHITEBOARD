import json

import numpy as np
import pytest

from core.lesson import (Lesson, LessonError, LessonPage, LessonSession, MAX_PAGES, lesson_nav_hit, lesson_nav_slots)


def sample():
    return Lesson("L", "me", [LessonPage("A", "- x", "img/a.png"), LessonPage("B"), LessonPage("C")])


def test_save_load_round_trip_with_unicode(tmp_path):
    l = sample()
    l.pages[1].text = "> p = a*m + (1-a)*p\n- accentué é"
    path = l.save(tmp_path / "x" / "lesson.json")
    back = Lesson.load(path)
    assert back.title == "L" and [p.title for p in back.pages] == ["A", "B", "C"]
    assert back.pages[1].text.endswith("accentué é") and back.path == path
    assert back.image_path(back.pages[0]) == tmp_path / "x" / "img" / "a.png"
    assert not list((tmp_path / "x").glob("*.tmp"))


def test_bad_files_give_clear_errors(tmp_path):
    with pytest.raises(LessonError, match="does not exist"):
        Lesson.load(tmp_path / "none.json")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(LessonError, match="not valid JSON"):
        Lesson.load(tmp_path / "bad.json")
    for data in ([], {"pages": []}, {"pages": [1]}, {"title": "x"}):
        (tmp_path / "w.json").write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(LessonError):
            Lesson.load(tmp_path / "w.json")
    with pytest.raises(LessonError):
        sample().save(tmp_path)                         # a directory is not a file name


def test_missing_fields_get_defaults():
    l = Lesson.from_dict({"pages": [{"title": "T"}, {}]})
    assert l.pages[0].text == "" and l.pages[1].title == "Page 2" and l.title == "Lesson"


def test_editing_operations():
    l = sample()
    assert l.move_page(0, 1) == 1 and [p.title for p in l.pages] == ["B", "A", "C"]
    assert l.move_page(0, -1) == 0                      # cannot move past the start
    i = l.duplicate_page(1)
    assert i == 2 and l.pages[2].title == "A" and l.pages[2] is not l.pages[1]
    assert l.add_page(0) == 0 and len(l) == 5
    assert l.delete_page(4) == 3
    one = Lesson(pages=[LessonPage()])
    with pytest.raises(LessonError):
        one.delete_page(0)
    big = Lesson(pages=[LessonPage() for _ in range(MAX_PAGES)])
    with pytest.raises(LessonError):
        big.add_page()


def test_session_navigation_and_annotations():
    s = LessonSession(sample())
    assert s.at_first and s.label == "Page 1 / 3" and not s.previous()
    ink = np.zeros((4, 4, 4), np.uint8)
    ink[1, 1] = (0, 0, 0, 255)
    s.store_ink(ink)
    assert s.next() and s.ink_for_current() is None
    assert s.next() and s.at_last and not s.next()
    assert s.go(0) and (s.ink_for_current() == ink).all() and s.annotated_pages() == [0]
    ink[:] = 0
    s.store_ink(ink)                                    # erased -> nothing stored
    assert s.annotated_pages() == []
    assert LessonSession(sample(), 99).index == 2


def test_nav_slots_inside_the_board_and_hit_test():
    slots = lesson_nav_slots(1600, 900)
    for s in slots:
        x, y, w, h = s.rect
        assert 0 <= x and x + w <= 1600 and y + h <= 900
    prev, label, nxt = slots
    cx = lambda s: (s.rect[0] + s.rect[2] / 2, s.rect[1] + s.rect[3] / 2)
    assert lesson_nav_hit(*cx(prev), 1600, 900) == "lesson.prev"
    assert lesson_nav_hit(*cx(nxt), 1600, 900) == "lesson.next"
    assert lesson_nav_hit(*cx(label), 1600, 900) is None
    assert lesson_nav_hit(10, 10, 1600, 900) is None


def test_rebase_images_when_the_lesson_moves(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    (a / "pics").mkdir(parents=True)
    (a / "pics" / "p.png").write_bytes(b"x")
    l = Lesson("T", pages=[LessonPage("P", image="pics/p.png"), LessonPage("Q")])
    l.save(a / "l.json")
    l.rebase_images(b)
    l.save(b / "l.json")
    assert l.image_path(l.pages[0]).exists() and l.pages[1].image == ""
    assert Lesson.load(b / "l.json").image_path(l.pages[0]).read_bytes() == b"x"
