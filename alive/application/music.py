"""Sondeo de música: el estado visible lo decide el motor local."""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class MusicMonitor:
    def __init__(self, source, engine, clock: Callable[[], float]) -> None:
        self.source = source
        self.engine = engine
        self.clock = clock
        self._last_active: bool | None = None
        self._pending = False

    def _apply(self, active: bool) -> None:
        self._pending = False
        if active != self._last_active:
            # set_music reinicia el temporizador de idle: solo avisar en cambios.
            self._last_active = active
            self.engine.set_music(active, self.clock())

    def poll(self) -> bool:
        active = self.source.is_playing()
        self._apply(active)
        return active

    def poll_async(self, background) -> bool:
        """Consulta el reproductor fuera del hilo GTK y aplica el cambio al volver."""
        if self._pending:
            return False
        self._pending = True

        def work() -> bool:
            try:
                return self.source.is_playing()
            except Exception as exc:
                logger.warning("No pude consultar la música: %s", exc)
                return False

        background.run(work, self._apply)
        return True
