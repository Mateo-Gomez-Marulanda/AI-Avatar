"""Mediador conversacional: turnos, acciones autorizadas y errores visibles.

La IA propone texto y acciones; el motor local decide todos los estados visuales.
Las apps de la whitelist se abren directo y los comandos requieren aprobación.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass

from alive.application.prompt import build_prompt, build_system_prompt
from alive.domain.actions import (
    AppAction,
    CommandAction,
    CommandRequest,
    CommandResult,
    parse_action,
)
from alive.domain.config import Config
from alive.domain.contracts import (
    AiProvider,
    Approver,
    AvatarViewLike,
    BackgroundLike,
    CommandExecutor,
    ProviderError,
    VoiceLike,
)
from alive.domain.conversation import Conversation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ModelReply:
    text: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class _CommandOutcome:
    command: str
    result: CommandResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class _Transcript:
    text: str = ""
    error: str | None = None


class Mediator:
    def __init__(
        self,
        *,
        engine,
        view: AvatarViewLike,
        ai: AiProvider,
        voice: VoiceLike,
        launcher,
        config: Config,
        clock: Callable[[], float],
        background: BackgroundLike,
        approver: Approver,
        executor: CommandExecutor,
        on_status: Callable[[bool, str], None] | None = None,
    ) -> None:
        self.engine = engine
        self.view = view
        self.ai = ai
        self.voice = voice
        self.launcher = launcher
        self.config = config
        self.clock = clock
        self.background = background
        self.approver = approver
        self.executor = executor
        self.on_status = on_status
        self.conversation = Conversation(config.conversation.max_chars)
        self.system_prompt = build_system_prompt(config.apps, config.commands.enabled)
        self.busy = False
        self._command_count = 0
        self._quiet = False

    def submit_text(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self.busy:
            self.view.show_bubble("Espera, estoy ocupado.", self.config.bubble_ms_per_char)
            return
        self.busy = True
        self._command_count = 0
        self.conversation.add_user(text)
        self.engine.transition_to("pensando", self.clock())
        self._status(True, "Pensando…")
        self.background.run(self._call_model, self._on_model)

    def _call_model(self) -> _ModelReply:
        try:
            reply = self.ai.ask(build_prompt(self.system_prompt, self.conversation))
            return _ModelReply(text=reply.text)
        except ProviderError as exc:
            return _ModelReply(error=str(exc))
        except Exception as exc:
            return _ModelReply(error=f"Error inesperado: {exc}")

    def _on_model(self, reply: _ModelReply) -> None:
        if reply.error:
            self._end_with_error(reply.error)
            return
        parsed = parse_action(reply.text or "")
        if parsed.error:
            if parsed.text:
                self.conversation.add_assistant(parsed.text)
            self._end_with_error(parsed.error)
            return
        if parsed.action is None:
            text = parsed.text or "ok"
            self.conversation.add_assistant(text)
            self._display(text)
            return
        if parsed.text:
            self.conversation.add_assistant(parsed.text)
        if isinstance(parsed.action, AppAction):
            self._do_app(parsed.action, parsed.text)
        else:
            self._do_command(parsed.action, parsed.text)

    def _do_app(self, action: AppAction, text: str) -> None:
        missing = [alias for alias in action.aliases if alias not in self.config.apps]
        if missing:
            self._end_with_error("App desconocida: " + ", ".join(missing))
            return
        opened: list[str] = []
        failed: list[str] = []
        for alias in action.aliases:
            try:
                if self.launcher.open(alias):
                    opened.append(alias)
                else:
                    failed.append(alias)
            except Exception as exc:
                logger.error("No pude abrir %s: %s", alias, exc)
                failed.append(alias)
        self.conversation.add_tool_note("App abierta: " + ", ".join(opened))
        logger.info("Apps abiertas: %s", ", ".join(opened))
        if failed:
            self._end_with_error("No pude abrir: " + ", ".join(failed))
            return
        self._display(text or "Abriendo…")

    def _do_command(self, action: CommandAction, text: str) -> None:
        if not self.config.commands.enabled:
            self._end_with_error("Ejecución de comandos desactivada")
            return
        if self._command_count >= self.config.commands.max_per_turn:
            self._display("He ejecutado varias acciones; dime cómo seguir")
            return
        logger.info("Comando propuesto: %s", action.command)
        self.engine.transition_to("esperando", self.clock())
        self._status(True, "Esperando permiso…")
        self.view.show_bubble(
            text or "Necesito tu permiso para ejecutar un comando",
            self.config.bubble_ms_per_char,
        )
        request = CommandRequest(
            action.command,
            action.what,
            action.why,
            os.path.expanduser(self.config.commands.working_dir),
        )
        self.approver.request(
            request, lambda approved: self._on_decision(approved, action.command)
        )

    def _on_decision(self, approved: bool, command: str) -> None:
        if not approved:
            self.conversation.add_tool_note("El usuario denegó la acción.")
            logger.info("Comando denegado: %s", command)
            self._display("Acción no ejecutada")
            return
        logger.info("Comando aprobado: %s", command)
        self._command_count += 1
        self.engine.transition_to("ejecutando", self.clock())
        self._status(True, "Ejecutando…")
        self.background.run(
            lambda: self._run_command(command), self._on_command_result
        )

    def _run_command(self, command: str) -> _CommandOutcome:
        try:
            return _CommandOutcome(command, result=self.executor.run(command))
        except Exception as exc:
            return _CommandOutcome(
                command, error=f"No pude ejecutar el comando: {exc}"
            )

    def _on_command_result(self, outcome: _CommandOutcome) -> None:
        if outcome.error:
            self._end_with_error(outcome.error)
            return
        result = outcome.result
        assert result is not None
        if self.config.commands.share_output_with_model:
            parts = [result.stdout, result.stderr]
            if result.timed_out:
                parts.append("[tiempo agotado]")
            output = "\n".join(part for part in parts if part) or "(sin salida)"
        else:
            output = None
        self.conversation.add_tool_result(outcome.command, result.exit_code, output)
        logger.info(
            "Comando terminado: código=%s timeout=%s duración=%.3fs",
            result.exit_code,
            result.timed_out,
            result.duration_s,
        )
        logger.debug(
            "Salida del comando %s: stdout=%r stderr=%r",
            outcome.command,
            result.stdout,
            result.stderr,
        )
        resumen = (
            "El comando agotó el tiempo"
            if result.timed_out
            else f"Comando ejecutado (código {result.exit_code})"
        )
        if self._command_count >= self.config.commands.max_per_turn:
            self._display("He ejecutado varias acciones; dime cómo seguir")
        elif self.config.commands.share_output_with_model:
            self.view.show_bubble(resumen, self.config.bubble_ms_per_char)
            self.engine.transition_to("pensando", self.clock())
            self._status(True, "Pensando…")
            self.background.run(self._call_model, self._on_model)
        else:
            self._display(resumen)

    def _display(self, text: str) -> None:
        self.view.show_bubble(text, self.config.bubble_ms_per_char)
        self.engine.speak(text, self.clock())
        try:
            self.voice.speak(
                text,
                on_level=lambda level, now: self.engine.set_audio_level(level, now),
            )
        except Exception as exc:
            logger.warning("Voz no disponible: %s", exc)
        self._finish_turn()

    def _finish_turn(self) -> None:
        self.busy = False
        self._status(False, "")

    def _end_with_error(self, message: str) -> None:
        logger.error("%s", message)
        self.view.show_bubble(message, self.config.bubble_ms_per_char)
        self.engine.idle(self.clock())
        self._finish_turn()

    def _status(self, busy: bool, text: str) -> None:
        if self.on_status is not None:
            self.on_status(busy, text)

    def ptt_start(self) -> None:
        if self.busy:
            return
        self.engine.transition_to("escuchando", self.clock())

    def _transcribe(self, seconds: float) -> _Transcript:
        try:
            return _Transcript(text=self.voice.transcribe(self.voice.record(seconds)))
        except ProviderError:
            return _Transcript()
        except Exception as exc:
            return _Transcript(error=f"No pude transcribir: {exc}")

    def ptt_end(self, held_seconds: float) -> None:
        if self.busy:
            return
        work = lambda: self._transcribe(held_seconds)
        self.background.run(work, self._on_transcript)

    def _on_transcript(self, transcript: _Transcript) -> None:
        if transcript.error:
            self._end_with_error(transcript.error)
            return
        if transcript.text.strip():
            self.submit_text(transcript.text)
        else:
            self.view.show_bubble("No pude escuchar", self.config.bubble_ms_per_char)
            self.engine.idle(self.clock())

    def toggle_no_molestar(self) -> None:
        self._quiet = not self._quiet
        self.view.set_click_through(self._quiet)
        if self._quiet:
            self.engine.transition_to("no_molestar", self.clock())
        else:
            self.engine.idle(self.clock())

    def on_drag_start(self) -> None:
        self.engine.begin_drag(self.clock())

    def on_drag_end(self, zone_name: str) -> None:
        self.engine.end_drag(self.clock())
