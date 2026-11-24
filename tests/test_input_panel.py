from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from alive.ui.input_panel import InputPanel

CONFIG = Path(__file__).parent / "fixtures" / "fake_config.toml"


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
    _, _, panel, _ = main.build(CONFIG)
    panel.quit_button.emit("clicked")
    assert called == ["quit"]


def test_build_hides_mic_and_warns_when_voice_tools_missing(monkeypatch):
    import alive.main as main

    monkeypatch.setattr(main, "missing_voice_commands", lambda cfg: ["stt"])
    _, view, panel, _ = main.build(CONFIG)
    assert panel.mic.get_visible() is False
    assert view.bubble.get_text() == "Voz no disponible: faltan herramientas"


def test_set_busy_disables_entry_send_and_mic_and_shows_status():
    panel = InputPanel(lambda t: None, lambda s: None, voice_enabled=True)
    panel.set_busy(True, "Pensando…")
    assert panel.entry.get_sensitive() is False
    assert panel.send.get_sensitive() is False
    assert panel.mic.get_sensitive() is False
    assert panel.status.get_text() == "Pensando…"
    panel.set_busy(False)
    assert panel.entry.get_sensitive() is True
    assert panel.send.get_sensitive() is True
    assert panel.status.get_text() == ""


def test_submit_keeps_panel_visible():
    panel = InputPanel(lambda t: None, lambda s: None, voice_enabled=False)
    panel.window.show()
    panel.entry.set_text("hola")
    panel._submit()
    assert panel.window.get_visible() is True


def test_delete_event_hides_instead_of_destroying():
    panel = InputPanel(lambda t: None, lambda s: None, voice_enabled=False)
    panel.window.show()
    assert panel._on_delete(None, None) is True
    assert panel.window.get_visible() is False
