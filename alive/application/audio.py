"""Voz configurable: captura, transcripción, síntesis y envolvente para la boca."""

from __future__ import annotations

import math
import shutil
import struct
import time
from collections.abc import Callable

from alive.domain.contracts import (
    BackgroundLike,
    BinaryCommandRunner,
    LevelTimer,
    SpeechAudio,
)

Runner = BinaryCommandRunner | Callable[[list[str], bytes, float], bytes]


def missing_voice_commands(config) -> list[str]:
    """Etiquetas de los comandos de voz que no existen en este sistema."""
    if not getattr(config, "enabled", True):
        return []
    checks = (
        ("captura", config.capture_command),
        ("stt", config.stt_command),
        ("tts", config.tts_command),
        ("play", config.play_command),
    )
    return [
        label
        for label, argv in checks
        if argv and shutil.which(argv[0]) is None
    ]


def _run(runner: Runner, argv: list[str], stdin: bytes, timeout_s: float) -> bytes:
    if callable(runner):
        return runner(argv, stdin, timeout_s)
    return runner.run(argv, stdin, timeout_s)


def _as_text(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def rms_envelope(
    pcm: bytes, sample_width: int = 2, frame_samples: int = 1024
) -> list[float]:
    frame_bytes = frame_samples * sample_width
    levels: list[float] = []
    for start in range(0, len(pcm), frame_bytes):
        chunk = pcm[start : start + frame_bytes]
        count = len(chunk) // sample_width
        if count == 0:
            continue
        samples = struct.unpack(f"<{count}h", chunk[: count * sample_width])
        rms = math.sqrt(sum(s * s for s in samples) / count)
        levels.append(min(1.0, rms / 32768.0))
    return levels


class VoiceService:
    def __init__(
        self,
        config,
        runner: Runner,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.runner = runner
        self.clock = clock
        self.sleep = sleep
        self._generation = 0
        self._pending_levels: list[object] = []

    def _enabled(self, command: list[str]) -> bool:
        return bool(getattr(self.config, "enabled", True) and command)

    def _voice_ready(self) -> bool:
        return self._enabled(self.config.tts_command) and bool(
            self.config.play_command
        )

    def record(self, seconds: float) -> bytes:
        if not self._enabled(self.config.capture_command):
            return b""
        argv = [
            arg.replace("{duration}", str(seconds))
            for arg in self.config.capture_command
        ]
        return _run(self.runner, argv, b"", seconds + 2)

    def transcribe(self, audio: bytes) -> str:
        if not self._enabled(self.config.stt_command):
            return ""
        return _as_text(
            _run(self.runner, self.config.stt_command, audio, self.config.timeout_s)
        ).strip()

    def synthesize(self, text: str) -> bytes:
        if not self._enabled(self.config.tts_command):
            return b""
        return _run(
            self.runner,
            self.config.tts_command,
            text.encode("utf-8"),
            self.config.timeout_s,
        )

    def play(self, pcm: bytes) -> str | None:
        if not self.config.play_command:
            return None
        try:
            _run(self.runner, self.config.play_command, pcm, self.config.timeout_s)
        except Exception as exc:
            return f"No pude reproducir la voz: {exc}"
        return None

    def _synthesize(self, text: str) -> SpeechAudio:
        if not self._voice_ready():
            return SpeechAudio()
        try:
            pcm = self.synthesize(text)
        except Exception as exc:
            return SpeechAudio(error=f"No pude sintetizar la voz: {exc}")
        duration_s = len(pcm) / (2 * self.config.sample_rate)
        return SpeechAudio(pcm=pcm, duration_s=duration_s)

    def _cancel_levels(self, timer: LevelTimer | None = None) -> None:
        for handle in self._pending_levels:
            if timer is not None:
                timer.cancel(handle)
        self._pending_levels = []

    def speak_async(
        self,
        text: str,
        *,
        on_level: Callable[[float, float], None],
        on_ready: Callable[[float], None],
        on_done: Callable[[str | None], None],
        background: BackgroundLike,
        timer: LevelTimer,
    ) -> None:
        """Sintetiza y reproduce en fondo; entrega niveles en el hilo GTK."""
        self._generation += 1
        generation = self._generation
        self._cancel_levels(timer)

        if not self._voice_ready():
            on_ready(0.0)
            on_done(None)
            return

        def on_audio(audio: SpeechAudio) -> None:
            if generation != self._generation:
                return
            self._cancel_levels(timer)
            if audio.error:
                on_ready(0.0)
                on_done(audio.error)
                return
            on_ready(audio.duration_s)
            step = self.config.frame_samples / self.config.sample_rate
            for index, level in enumerate(
                rms_envelope(audio.pcm, frame_samples=self.config.frame_samples)
            ):
                def emit(level: float = level) -> None:
                    if generation == self._generation:
                        on_level(level, self.clock())

                self._pending_levels.append(timer.after(index * step, emit))

            def on_played(error: str | None) -> None:
                if generation != self._generation:
                    return
                self._cancel_levels(timer)
                on_level(0.0, self.clock())
                on_done(error)

            background.run(lambda: self.play(audio.pcm), on_played)

        background.run(lambda: self._synthesize(text), on_audio)

    def speak(
        self,
        text: str,
        on_level: Callable[[float, float], None],
    ) -> None:
        """Compatibilidad temporal hasta que el mediador use ``speak_async``."""
        if not self._voice_ready():
            return
        pcm = self.synthesize(text)
        _run(self.runner, self.config.play_command, pcm, self.config.timeout_s)
        step = self.config.frame_samples / self.config.sample_rate
        for level in rms_envelope(pcm, frame_samples=self.config.frame_samples):
            on_level(level, self.clock())
            self.sleep(step)
