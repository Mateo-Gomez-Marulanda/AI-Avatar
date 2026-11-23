"""Motor de estados y boca. Ninguna decisión de animación viene de la IA."""

from __future__ import annotations

from dataclasses import dataclass

STATES = (
    "sentado",
    "parado",
    "escuchando",
    "pensando",
    "hablando",
    "musica",
    "arrastrado",
    "no_molestar",
)

_AUDIO_TTL_S = 0.12


@dataclass(frozen=True)
class Frame:
    state: str
    mouth: float
    snap_progress: float


class AnimationEngine:
    def __init__(
        self,
        idle_state: str = "sentado",
        snap_ms: int = 250,
        ms_per_char: int = 45,
    ) -> None:
        self.idle_state = idle_state
        self.snap_ms = snap_ms
        self.ms_per_char = ms_per_char
        self._state = idle_state
        self.speaking_until = 0.0
        self._audio_level = 0.0
        self._audio_at = float("-inf")
        self._dragging = False
        self._snap_start: float | None = None
        self._return_at: float | None = None

    @property
    def state(self) -> str:
        return self._state

    def transition_to(self, state: str, now: float) -> None:
        if state not in STATES:
            raise ValueError(f"estado desconocido: {state!r}")
        self._state = state
        if state != "hablando":
            self.speaking_until = 0.0

    def speak(self, text: str, now: float) -> None:
        self._state = "hablando"
        self.speaking_until = now + len(text) * self.ms_per_char / 1000

    def set_audio_level(self, level: float, now: float) -> None:
        self._audio_level = min(1.0, max(0.0, level))
        self._audio_at = now

    def begin_drag(self, now: float) -> None:
        self._dragging = True
        self._state = "arrastrado"
        self._snap_start = None
        self._return_at = None
        self.speaking_until = 0.0

    def end_drag(self, now: float) -> None:
        self._dragging = False
        self._snap_start = now
        self._return_at = now + self.snap_ms / 1000

    def _mouth(self, now: float) -> float:
        if now - self._audio_at <= _AUDIO_TTL_S:
            return self._audio_level
        if self._state == "hablando":
            return 0.7 if int(now * 10) % 2 == 0 else 0.1
        return 0.0

    def tick(self, now: float) -> Frame:
        if self._dragging:
            return Frame(self._state, self._mouth(now), 0.0)

        if self._return_at is not None:
            if now >= self._return_at:
                self._state = self.idle_state
                self._snap_start = None
                self._return_at = None
            else:
                assert self._snap_start is not None
                duration = self._return_at - self._snap_start
                progress = 0.0 if duration == 0 else (now - self._snap_start) / duration
                return Frame("arrastrado", self._mouth(now), min(1.0, max(0.0, progress)))

        if self._state == "hablando" and now >= self.speaking_until:
            self._state = self.idle_state

        return Frame(self._state, self._mouth(now), 1.0)
