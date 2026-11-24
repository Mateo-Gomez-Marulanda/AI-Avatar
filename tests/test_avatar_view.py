from pathlib import Path
from types import SimpleNamespace

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gdk, GtkLayerShell

from alive.domain.config import Zone, load_config
from alive.domain.geometry import Rect
from alive.ui import avatar_view as av

CONFIG = Path(__file__).parent / "fixtures" / "fake_config.toml"


def make_view():
    view = av.AvatarView(load_config(CONFIG), Rect(0, 0, 1366, 768))
    events = []
    view.set_callbacks(lambda: events.append("drag"), lambda z: events.append(z),
                       lambda: events.append("panel"))
    return view, events


def ev(dx=0, dy=0, state=0):
    return SimpleNamespace(button=1, x=100, y=100,
                           x_root=683 + dx, y_root=132 + dy, state=state)


def ev3(dx=0, dy=0, state=0):
    event = ev(dx, dy, state)
    event.button = 3
    return event


def test_small_jitter_is_a_click(monkeypatch):
    view, events = make_view()
    monkeypatch.setattr(av.Gtk.Widget, "grab_add", lambda w: events.append("grab_add"))
    monkeypatch.setattr(av.Gtk.Widget, "grab_remove", lambda w: events.append("grab_remove"))
    view._button_press(None, ev())
    view._motion(None, ev(3, 3, Gdk.ModifierType.BUTTON1_MASK))
    view._button_release(None, ev(4, 3))
    assert events[0] == "grab_add"
    assert "panel" in events and "grab_remove" in events
    assert "drag" not in events


def test_drag_grabs_pointer_until_release(monkeypatch):
    view, events = make_view()
    monkeypatch.setattr(av.Gtk.Widget, "grab_add", lambda w: events.append("grab_add"))
    monkeypatch.setattr(av.Gtk.Widget, "grab_remove", lambda w: events.append("grab_remove"))
    view._button_press(None, ev())
    view._motion(None, ev(80, 80, Gdk.ModifierType.BUTTON1_MASK))
    view._button_release(None, ev(80, 80))
    assert events[0] == "grab_add"
    assert "grab_remove" in events
    assert "drag" in events and "panel" not in events


def test_second_drag_during_snap_does_not_jump_back(monkeypatch):
    view, _ = make_view()
    monkeypatch.setattr(av.Gtk.Widget, "grab_add", lambda w: None)
    monkeypatch.setattr(av.Gtk.Widget, "grab_remove", lambda w: None)
    placed = []
    monkeypatch.setattr(view, "_place_free", lambda x, y: placed.append((int(x), int(y))))

    view._button_press(None, ev())
    view._motion(None, ev(80, 80, Gdk.ModifierType.BUTTON1_MASK))
    view._button_release(None, ev(80, 80))
    assert view._snap_to is not None

    view._button_press(None, ev(dx=-80, dy=-80))
    view._motion(None, ev(dx=120, dy=100, state=Gdk.ModifierType.BUTTON1_MASK))
    view.render(SimpleNamespace(mouth=0.0, snap_progress=0.0))
    assert view._snap_to is None
    assert placed[-1] == (703, 132)


def test_drag_and_snap_use_anchored_margins(monkeypatch):
    view, _ = make_view()
    monkeypatch.setattr(av.Gtk.Widget, "grab_add", lambda w: None)
    monkeypatch.setattr(av.Gtk.Widget, "grab_remove", lambda w: None)
    E = GtkLayerShell.Edge

    view._button_press(None, ev())
    view._motion(None, ev(100, 200, Gdk.ModifierType.BUTTON1_MASK))
    assert GtkLayerShell.get_anchor(view.window, E.TOP)
    assert GtkLayerShell.get_anchor(view.window, E.LEFT)
    assert GtkLayerShell.get_margin(view.window, E.TOP) == 232
    assert GtkLayerShell.get_margin(view.window, E.LEFT) == 683

    view._button_release(None, ev(100, 200))
    view.render(SimpleNamespace(mouth=0.0, snap_progress=0.5))
    assert GtkLayerShell.get_anchor(view.window, E.TOP)
    assert GtkLayerShell.get_anchor(view.window, E.LEFT)
    assert GtkLayerShell.get_margin(view.window, E.TOP) == 132
    assert GtkLayerShell.get_margin(view.window, E.LEFT) == 633


def test_right_zone_keeps_right_edge_anchored():
    view, _ = make_view()
    view.config.zones["derecha"] = Zone("right", margin=12)
    E = GtkLayerShell.Edge

    view._apply_zone("derecha")
    assert GtkLayerShell.get_anchor(view.window, E.RIGHT)
    assert not GtkLayerShell.get_anchor(view.window, E.LEFT)
    assert GtkLayerShell.get_margin(view.window, E.RIGHT) == 12


def test_click_during_snap_keeps_the_animation(monkeypatch):
    view, _ = make_view()
    monkeypatch.setattr(av.Gtk.Widget, "grab_add", lambda w: None)
    monkeypatch.setattr(av.Gtk.Widget, "grab_remove", lambda w: None)

    view._button_press(None, ev())
    view._motion(None, ev(80, 80, Gdk.ModifierType.BUTTON1_MASK))
    view._button_release(None, ev(80, 80))
    assert view._snap_to is not None

    view._button_press(None, ev())
    view._button_release(None, ev())
    assert view._snap_to is not None
    view.render(SimpleNamespace(mouth=0.0, snap_progress=1.0))
    assert view._snap_to is None


def test_avatar_has_colors_for_action_states():
    assert {"pensando", "esperando", "ejecutando"} <= set(av._STATE_COLORS)


def test_right_button_is_ptt_and_does_not_click_or_drag(monkeypatch):
    events = []
    view = av.AvatarView(load_config(CONFIG), Rect(0, 0, 1366, 768))
    view.set_callbacks(
        lambda: events.append("drag"),
        lambda zone: events.append(zone),
        lambda: events.append("panel"),
        on_ptt_start=lambda: events.append("ptt_start"),
        on_ptt_end=lambda: events.append("ptt_end"),
    )
    monkeypatch.setattr(av.Gtk.Widget, "grab_add", lambda w: None)
    monkeypatch.setattr(av.Gtk.Widget, "grab_remove", lambda w: None)
    view._button_press(None, ev3())
    view._motion(None, ev3(80, 80, Gdk.ModifierType.BUTTON3_MASK))
    view._button_release(None, ev3(80, 80))
    assert events == ["ptt_start", "ptt_end"]


def test_click_through_ignores_right_button():
    events = []
    view = av.AvatarView(load_config(CONFIG), Rect(0, 0, 1366, 768))
    view.set_callbacks(lambda: None, lambda zone: None, lambda: None,
                       on_ptt_start=lambda: events.append("ptt_start"))
    view.set_click_through(True)
    view._button_press(None, ev3())
    assert events == []


def test_bottom_right_anchors_both_edges():
    view = av.AvatarView(load_config(CONFIG), Rect(0, 0, 1366, 768))
    view.config.zones["no_molestar"] = Zone("bottom-right", margin=12)
    E = GtkLayerShell.Edge
    view._apply_zone("no_molestar")
    assert GtkLayerShell.get_anchor(view.window, E.BOTTOM)
    assert GtkLayerShell.get_anchor(view.window, E.RIGHT)
    assert not GtkLayerShell.get_anchor(view.window, E.TOP)
    assert not GtkLayerShell.get_anchor(view.window, E.LEFT)
    assert GtkLayerShell.get_margin(view.window, E.BOTTOM) == 12
    assert GtkLayerShell.get_margin(view.window, E.RIGHT) == 12


def test_snap_to_rect_interpolates_and_tracks_current_rect(monkeypatch):
    view = av.AvatarView(load_config(CONFIG), Rect(0, 0, 1366, 768))
    placed = []
    monkeypatch.setattr(view, "_place_free", lambda x, y: placed.append((int(x), int(y))))
    start = view.current_rect()
    target = Rect(1154, 456, start.width, start.height)
    view.snap_to(target)
    view.render(SimpleNamespace(mouth=0.0, snap_progress=0.5))
    assert placed[-1] == ((start.x + target.x) // 2, (start.y + target.y) // 2)
    view.render(SimpleNamespace(mouth=0.0, snap_progress=1.0))
    assert view.current_rect() == target
