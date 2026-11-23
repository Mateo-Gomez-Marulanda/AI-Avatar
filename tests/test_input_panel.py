import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from alive.ui.input_panel import InputPanel


def test_quit_button_calls_callback():
    called = []
    panel = InputPanel(lambda t: None, lambda s: None,
                       on_quit=lambda: called.append("quit"), voice_enabled=False)
    panel.quit_button.emit("clicked")
    assert called == ["quit"]


def test_ctrl_q_calls_callback():
    called = []
    panel = InputPanel(lambda t: None, lambda s: None,
                       on_quit=lambda: called.append("quit"), voice_enabled=False)
    panel.window.show()
    key, mods = Gtk.accelerator_parse("<Control>q")
    Gtk.accel_groups_activate(panel.window, key, mods)
    assert called == ["quit"]


def test_build_wires_quit_to_main_loop(monkeypatch):
    import alive.main as main
    called = []
    monkeypatch.setattr(main.Gtk, "main_quit", lambda: called.append("quit"))
    _, _, panel, _ = main.build("/tmp/opencode/fake_config.toml")
    panel.quit_button.emit("clicked")
    assert called == ["quit"]
