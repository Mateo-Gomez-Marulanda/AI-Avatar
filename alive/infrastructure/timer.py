"""Temporizador GTK para entregar niveles de voz en el hilo principal."""

from __future__ import annotations

from collections.abc import Callable

from gi.repository import GLib


class GtkLevelTimer:
    def after(self, delay_s: float, callback: Callable[[], None]) -> object:
        def fire():
            callback()
            return False

        return GLib.timeout_add(max(1, int(delay_s * 1000)), fire)

    def cancel(self, handle: object) -> None:
        GLib.source_remove(handle)
