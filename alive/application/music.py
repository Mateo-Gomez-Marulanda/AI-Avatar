"""Sondeo de música: el estado visible lo decide el motor local."""

from __future__ import annotations

from collections.abc import Callable


class MusicMonitor:
    def __init__(self, source, engine, clock: Callable[[], float]) -> None:
        self.source = source
        self.engine = engine
        self.clock = clock

    def poll(self) -> bool:
        active = self.source.is_playing()
        self.engine.set_music(active, self.clock())
        return active
