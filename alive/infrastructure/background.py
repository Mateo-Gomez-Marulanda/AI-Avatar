"""Adaptador para ejecutar trabajo fuera del hilo GTK."""

from __future__ import annotations

import threading

from gi.repository import GLib


class GtkBackgroundRunner:
    """Trabaja fuera del hilo GTK y entrega el resultado en el hilo principal."""

    def run(self, work, done) -> None:
        def target() -> None:
            result = work()
            GLib.idle_add(done, result)

        threading.Thread(target=target, daemon=True).start()
