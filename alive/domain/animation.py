"""Motor de estados y boca. Ninguna decisión de animación viene de la IA."""

from __future__ import annotations

from dataclasses import dataclass

STATES = (
    "sentado",
    "parado",
    "escuchando",
    "pensando",
    "esperando",
    "ejecutando",
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
        idle_states: tuple[str, ...] = ("sentado", "parado"),
        snap_ms: int = 250,
        ms_per_char: int = 45,
        idle_switch_s: float = 20.0,
    ) -> None:
        if not idle_states:
            raise ValueError("idle_states no puede estar vacío")
        unknown = [state for state in idle_states if state not in STATES]
        if unknown:
            raise ValueError(f"estados idle desconocidos: {unknown!r}")
        self.idle_states = tuple(idle_states)
        self.snap_ms = snap_ms
        self.ms_per_char = ms_per_char
        self.idle_switch_s = idle_switch_s
        self._idle_index = 0
        self._idle_since: float | None = None
        self._music_active = False
        self._state = self.idle_state
        self.speaking_until = 0.0
        self._audio_level = 0.0
        self._audio_at = float("-inf")
        self._dragging = False
        self._snap_start: float | None = None
        self._return_at: float | None = None
        self._snap_return_state: str | None = None
        self._quiet = False
        self._quiet_state: str | None = None
        self._quiet_speaking_until = 0.0

    @property
    def state(self) -> str:
        return self._state

    @property
    def idle_state(self) -> str:
        return self.idle_states[self._idle_index]

    def idle(self, now: float) -> None:
        if self._quiet:
            self._state = "no_molestar"
        else:
            self._state = "musica" if self._music_active else self.idle_state
        self.speaking_until = 0.0
        self._idle_since = now

    def set_music(self, active: bool, now: float) -> None:
        self._music_active = active
        if self._state == "musica" and not active:
            self._state = self.idle_state
        elif self._state in self.idle_states and active:
            self._state = "musica"
        self._idle_since = now

    def transition_to(self, state: str, now: float) -> None:
        if state not in STATES:
            raise ValueError(f"estado desconocido: {state!r}")
        self._state = state
        if state in self.idle_states:
            self._idle_index = self.idle_states.index(state)
            self._idle_since = now
        if state != "hablando":
            self.speaking_until = 0.0

    def speak(self, text: str, now: float, duration_s: float | None = None) -> None:
        self._state = "hablando"
        seconds = (
            len(text) * self.ms_per_char / 1000
            if duration_s is None
            else duration_s
        )
        self.speaking_until = now + seconds

    def set_speech_duration(self, duration_s: float, now: float) -> None:
        self.speaking_until = now + duration_s

    def end_speech(self, now: float) -> None:
        self._audio_level = 0.0
        self._audio_at = float("-inf")
        self.idle(now)

    def set_audio_level(self, level: float, now: float) -> None:
        self._audio_level = min(1.0, max(0.0, level))
        self._audio_at = now

    def begin_drag(self, now: float) -> None:
        self._dragging = True
        self._state = "arrastrado"
        self._snap_start = None
        self._return_at = None
        self.speaking_until = 0.0

    def begin_snap(self, now: float) -> None:
        self._dragging = False
        self._snap_return_state = self._state
        self._snap_start = now
        self._return_at = now + self.snap_ms / 1000

    def end_drag(self, now: float) -> None:
        self.begin_snap(now)

    def set_quiet(self, active: bool, now: float) -> None:
        if active == self._quiet:
            return
        if active:
            self._quiet_state = self._state
            self._quiet_speaking_until = self.speaking_until
            self._quiet = True
            self.transition_to("no_molestar", now)
            return

        self._quiet = False
        previous = self._quiet_state
        saved_until = self._quiet_speaking_until
        self._quiet_state = None
        self._quiet_speaking_until = 0.0
        in_turn = previous not in (
            None,
            "no_molestar",
            "arrastrado",
            "musica",
        ) and previous not in self.idle_states
        if in_turn:
            self._state = previous
            self.speaking_until = saved_until
            self._idle_since = now
        else:
            self.idle(now)

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
                previous = self._snap_return_state
                self._snap_start = None
                self._return_at = None
                self._snap_return_state = None
                in_turn = (
                    previous is not None
                    and previous != "arrastrado"
                    and previous not in self.idle_states
                    and previous not in ("musica", "no_molestar")
                )
                if in_turn:
                    self._state = previous
                    self._idle_since = now
                else:
                    self.idle(now)
            else:
                assert self._snap_start is not None
                duration = self._return_at - self._snap_start
                progress = 0.0 if duration == 0 else (now - self._snap_start) / duration
                return Frame("arrastrado", self._mouth(now), min(1.0, max(0.0, progress)))

        if self._state == "hablando" and now >= self.speaking_until:
            self.idle(now)

        if self._state in self.idle_states and not self._music_active and not self._quiet:
            if self._idle_since is None:
                self._idle_since = now
            elif now - self._idle_since >= self.idle_switch_s:
                self._idle_index = (self._idle_index + 1) % len(self.idle_states)
                self._idle_since = now
                self._state = self.idle_state

        return Frame(self._state, self._mouth(now), 1.0)
