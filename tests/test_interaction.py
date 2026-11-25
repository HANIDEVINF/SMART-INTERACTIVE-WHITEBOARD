"""Dwell, interaction engine and menu model/layout."""
from core.interaction import Command, DwellSelector, InteractionEngine, Mode
from core.menu_model import BACK_ID, MenuModel, build_menu


def kinds(cmds):
    return [c.kind for c in cmds]


def test_dwell_fires_after_time_and_not_again_while_resting():
    d = DwellSelector(1000, 200)
    assert d.update("a", 0) is None
    assert d.update("a", 500) is None and abs(d.progress - 0.5) < 1e-9
    assert d.update("a", 1000) == "a"
    assert d.update("a", 1500) is None and d.update("a", 4000) is None      # locked until the pointer leaves
    assert d.update(None, 4100) is None
    assert d.update("a", 4200) is None                                       # still within lock/leave
    assert d.update("b", 4300) is None
    assert d.update("a", 4400) is None and d.update("a", 5400) == "a"       # a fresh dwell on a is possible again


def test_dwell_jitter_within_grace_keeps_timer_but_leaving_resets():
    d = DwellSelector(1000, 200)
    d.update("a", 0)
    d.update(None, 400)           # 100 ms jitter off the item
    d.update("a", 500)
    assert d.update("a", 1000) == "a"
    d2 = DwellSelector(1000, 200)
    d2.update("a", 0)
    d2.update("b", 300)
    d2.update("b", 600)           # away for 300 ms > grace: restarted on b
    assert d2.update("b", 1400) is None and d2.update("b", 1700) == "b"


def test_navigation_mode_left_click_activates_hovered_item_only():
    e = InteractionEngine()
    e.pointer(100, 100, True, 0, hover=None)
    assert kinds(e.left_click()) == ["click"]
    e.pointer(100, 100, True, 10, hover="tool.pen")
    c = e.left_click()
    assert c[0].kind == "activate" and c[0].target == "tool.pen"


def test_drawing_mode_left_click_toggles_pen_and_moves_draw():
    e = InteractionEngine()
    e.set_mode(Mode.DRAWING)
    e.pointer(10, 10, True, 0)
    assert kinds(e.left_click()) == ["pen_down"] and e.pen_down
    c = e.pointer(20, 25, True, 10)
    assert kinds(c) == ["pen_move"] and (c[0].x, c[0].y) == (20, 25)
    assert kinds(e.left_click()) == ["pen_up"] and not e.pen_down
    assert e.pointer(30, 30, True, 20) == []


def test_pointer_lost_lifts_pen_and_clicks_do_nothing():
    e = InteractionEngine()
    e.set_mode(Mode.DRAWING)
    e.pointer(10, 10, True, 0)
    e.left_click()
    c = e.pointer(0, 0, False, 50)
    assert kinds(c) == ["pen_up", "pointer_lost"] and not e.pen_down
    assert e.left_click() == []
    assert kinds(e.pointer(0, 0, False, 60)) == []              # no repeated "lost"


def test_right_click_lifts_pen_else_goes_back():
    e = InteractionEngine()
    e.set_mode(Mode.DRAWING)
    e.pointer(1, 1, True, 0)
    e.left_click()
    assert kinds(e.right_click()) == ["pen_up"]
    assert kinds(e.right_click()) == ["back"]


def test_selection_mode_dwell_activates():
    e = InteractionEngine(dwell_ms=500)
    e.set_mode(Mode.SELECTION)
    out = []
    for t in range(0, 700, 50):
        out += e.pointer(5, 5, True, t, hover="mode.drawing")
    assert [c.target for c in out if c.kind == "activate"] == ["mode.drawing"]
    e.set_mode(Mode.NAVIGATION)
    assert e.dwell_progress == 0.0


def test_mode_change_lifts_pen():
    e = InteractionEngine()
    e.set_mode(Mode.DRAWING)
    e.pointer(1, 1, True, 0)
    e.left_click()
    assert kinds(e.set_mode(Mode.NAVIGATION)) == ["pen_up"]


def test_menu_tree_has_required_submenus():
    m = MenuModel()
    top = {c.id for c in m.root.children}
    assert {"drawing", "image", "presentation", "settings"} <= top
    m.open()
    assert m.activate("drawing") == ("enter", None) and m.title == "Menu / Drawing"
    assert m.activate("tool.pen") == ("action", "tool:pen")
    assert m.activate(BACK_ID)[0] == "back" and m.current is m.root
    assert m.back() == "closed" and not m.is_open


def test_confirmation_level_and_actions_all_have_handlers():
    m = MenuModel()
    m.open()
    m.activate("drawing")
    assert m.activate("clear") == ("enter", None)
    assert m.activate("clear.no") == ("action", "menu.back")
    assert m.activate("clear.yes") == ("action", "board.clear")


def test_layout_inside_board_no_overlap_and_hit_test():
    m = MenuModel()
    m.open()
    stack = [None] + [m.root.children[0]]
    for level in range(2):
        if level == 1:
            m.activate("drawing")
        slots = [s for s in m.layout(1600, 900) if s.kind != "title"]
        for s in slots:
            x, y, w, h = s.rect
            assert 0 <= x and x + w <= 1600 and 0 <= y and y + h <= 900
        for i, a in enumerate(slots):
            for b in slots[i + 1:]:
                ax, ay, aw, ah = a.rect
                bx, by, bw, bh = b.rect
                assert ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay
        s0 = slots[0]
        cx, cy = s0.rect[0] + s0.rect[2] / 2, s0.rect[1] + s0.rect[3] / 2
        assert m.hit(cx, cy, 1600, 900) == s0.id
        assert m.hit(1590, 890, 1600, 900) is None
    assert not m.layout(1600, 900) == []


def test_closed_menu_has_no_hits_and_keyboard_focus_wraps():
    m = MenuModel()
    assert m.hit(60, 140, 1600, 900) is None and m.layout(1600, 900) == []
    m.open()
    first = m.focused_id()
    n = len(m.entries())
    for _ in range(n):
        m.move_focus(1)
    assert m.focused_id() == first
    assert m.move_focus(-1) == "@close"
