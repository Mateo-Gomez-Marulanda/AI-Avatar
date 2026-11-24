"""Intermediario: convierte respuestas en estados, globo, voz y apps.

La IA nunca decide animaciones. Solo puede pedir ESTADO grueso o ABRIR un alias
de la whitelist; todo lo demás se ignora.
"""

from __future__ import annotations

from collections.abc import Callable

from alive.domain.config import Config
from alive.domain.contracts import AiReply, ProviderError
from alive.domain.orders import ALLOWED_STATES, Order, parse_orders


class Mediator:
    def __init__(
        self,
        *,
        engine,
        view,
        ai,
        voice,
        launcher,
        config: Config,
        clock: Callable[[], float],
        background,
    ) -> None:
        self.engine = engine
        self.view = view
        self.ai = ai
        self.voice = voice
        self.launcher = launcher
        self.config = config
        self.clock = clock
        self.background = background
        self.history: tuple[str, ...] = ()
        self._quiet = False

    def submit_text(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.engine.transition_to("escuchando", self.clock())
        self.background.run(lambda: self._ask(text), self._finish)

    def _ask(self, text: str) -> AiReply | None:
        try:
            return self.ai.ask("\n".join((*self.history, text)))
        except ProviderError:
            return None

    def _finish(self, reply: AiReply | None) -> None:
        if reply is None:
            self.view.show_bubble(
                "No pude responder", self.config.bubble_ms_per_char
            )
            self.engine.transition_to(self.config.idle_state, self.clock())
            return

        parsed = parse_orders(reply.text)
        for order in parsed.orders:
            self.apply_order(order)

        text = parsed.clean_text or "ok"
        self.engine.speak(text, self.clock())
        self.view.show_bubble(text, self.config.bubble_ms_per_char)
        self.history = (*self.history, text)
        try:
            self.voice.speak(
                text,
                on_level=lambda level, now: self.engine.set_audio_level(level, now),
            )
        except ProviderError:
            pass  # La voz es opcional; el globo con la respuesta ya es visible.

    def ptt_start(self) -> None:
        self.engine.transition_to("escuchando", self.clock())

    def _transcribe(self, seconds: float) -> str:
        try:
            return self.voice.transcribe(self.voice.record(seconds))
        except ProviderError:
            return ""

    def ptt_end(self, held_seconds: float) -> None:
        work = lambda: self._transcribe(held_seconds)
        self.background.run(work, self._on_transcript)

    def _on_transcript(self, text: str) -> None:
        if text.strip():
            self.submit_text(text)
        else:
            self.view.show_bubble(
                "No pude escuchar", self.config.bubble_ms_per_char
            )
            self.engine.transition_to(self.config.idle_state, self.clock())

    def apply_order(self, order: Order) -> bool:
        if order.kind == "ESTADO":
            if order.value not in ALLOWED_STATES:
                return False
            self.engine.transition_to(order.value, self.clock())
            return True
        if order.kind == "ABRIR":
            if order.value not in self.config.apps:
                return False
            return bool(self.launcher.open(order.value))
        return False

    def toggle_no_molestar(self) -> None:
        self._quiet = not self._quiet
        self.view.set_click_through(self._quiet)
        state = "no_molestar" if self._quiet else self.config.idle_state
        self.engine.transition_to(state, self.clock())

    def on_drag_start(self) -> None:
        self.engine.begin_drag(self.clock())

    def on_drag_end(self, zone_name: str) -> None:
        self.engine.end_drag(self.clock())
