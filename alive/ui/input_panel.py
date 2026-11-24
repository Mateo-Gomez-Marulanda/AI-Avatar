"""Panel de texto y micrófono de pulsación mantenida."""

from __future__ import annotations

import time
from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, Gtk  # noqa: E402


class InputPanel:
    def __init__(
        self,
        on_text_submit: Callable[[str], None],
        on_ptt_hold: Callable[[float], None],
        *,
        on_ptt_start: Callable[[], None] | None = None,
        on_toggle_quiet: Callable[[], None] | None = None,
        voice_enabled: bool = True,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self.on_text_submit = on_text_submit
        self.on_ptt_hold = on_ptt_hold
        self.on_ptt_start = on_ptt_start
        self.on_toggle_quiet = on_toggle_quiet
        self.on_quit = on_quit
        self._held_since: float | None = None

        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_title("Alive")
        self.window.set_default_size(480, 88)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_keep_above(False)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_border_width(8)

        self.status = Gtk.Label(label="")
        self.status.set_no_show_all(True)
        box.pack_start(self.status, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Escribe a Alive…")
        self.entry.connect("activate", self._on_activate)
        box.pack_start(self.entry, True, True, 0)

        self.send = Gtk.Button(label="Enviar")
        self.send.connect("clicked", self._on_send)
        box.pack_start(self.send, False, False, 0)

        self.mic = Gtk.Button(label="Micrófono")
        self.mic.set_events(
            Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
        )
        self.mic.connect("button-press-event", self._on_mic_press)
        self.mic.connect("button-release-event", self._on_mic_release)
        box.pack_start(self.mic, False, False, 0)

        quiet = Gtk.ToggleButton(label="No molestar")
        quiet.connect("toggled", self._on_quiet)
        box.pack_start(quiet, False, False, 0)

        self.quit_button = Gtk.Button(label="Salir")
        self.quit_button.connect("clicked", self._on_quit)
        box.pack_start(self.quit_button, False, False, 0)

        self.window.add(box)
        self.window.connect("delete-event", self._on_delete)
        accel_group = Gtk.AccelGroup()
        key, mods = Gtk.accelerator_parse("<Control>q")
        accel_group.connect(key, mods, 0, self._on_quit_accel)
        self.window.add_accel_group(accel_group)
        self.window.show_all()
        if not voice_enabled:
            self.mic.hide()
        self.window.hide()

    def show(self) -> None:
        self.window.show()
        self.entry.grab_focus()

    def hide(self) -> None:
        self.window.hide()

    def present(self) -> None:
        self.window.present()
        self.entry.grab_focus()

    def set_busy(self, busy: bool, status: str = "") -> None:
        self.entry.set_sensitive(not busy)
        self.send.set_sensitive(not busy)
        self.mic.set_sensitive(not busy)
        self.status.set_text(status)
        if status:
            self.status.show()
        else:
            self.status.hide()

    def _submit(self) -> None:
        text = self.entry.get_text().strip()
        if not text:
            return
        self.entry.set_text("")
        self.on_text_submit(text)

    def _on_activate(self, entry) -> None:
        self._submit()

    def _on_send(self, button) -> None:
        self._submit()

    def _on_mic_press(self, widget, event) -> bool:
        if event.button != 1:
            return False
        self._held_since = time.monotonic()
        if self.on_ptt_start is not None:
            self.on_ptt_start()
        return False

    def _on_mic_release(self, widget, event) -> bool:
        if event.button != 1 or self._held_since is None:
            return False
        held = time.monotonic() - self._held_since
        self._held_since = None
        self.on_ptt_hold(held)
        return False

    def _on_delete(self, widget, event) -> bool:
        self.hide()
        return True

    def _on_quiet(self, button) -> None:
        if self.on_toggle_quiet is not None:
            self.on_toggle_quiet()

    def _on_quit(self, button=None) -> None:
        if self.on_quit is not None:
            self.on_quit()

    def _on_quit_accel(self, group, acceleratable, key, mods) -> None:
        self._on_quit()
