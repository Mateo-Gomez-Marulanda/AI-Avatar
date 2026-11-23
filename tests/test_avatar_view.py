from types import SimpleNamespace

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gdk

from alive.domain.config import load_config
from alive.domain.geometry import Rect
from alive.ui import avatar_view as av


def make_view():
    view = av.AvatarView(load_config("/tmp/opencode/fake_config.toml"), Rect(0, 0, 1366, 768))
    events = []
    view.set_callbacks(lambda: events.append("drag"), lambda z: events.append(z),
                       lambda: events.append("panel"))
    return view, events


def ev(dx=0, dy=0, state=0):
    return SimpleNamespace(button=1, x=100, y=100,
                           x_root=683 + dx, y_root=132 + dy, state=state)


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
