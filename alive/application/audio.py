"""Voz configurable: captura, transcripción, síntesis y envolvente para la boca."""

from __future__ import annotations

import math
import shutil
import struct
import time
from collections.abc import Callable

from alive.domain.contracts import CommandRunner

Runner = CommandRunner | Callable[[list[str], bytes, float], str | bytes]


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


def _run(runner: Runner, argv: list[str], stdin: bytes, timeout_s: float) -> str | bytes:
    if callable(runner):
        return runner(argv, stdin, timeout_s)
    return runner.run(argv, stdin, timeout_s)


def _as_bytes(value: str | bytes) -> bytes:
    return value if isinstance(value, bytes) else value.encode("utf-8", errors="replace")


def _as_text(value: str | bytes) -> str:
    return value if isinstance(value, str) else value.decode("utf-8", errors="replace")


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
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.runner = runner
        self.sleep = sleep

    def _enabled(self, command: list[str]) -> bool:
        return bool(getattr(self.config, "enabled", True) and command)

    def record(self, seconds: float) -> bytes:
        if not self._enabled(self.config.capture_command):
            return b""
        argv = [
            arg.replace("{duration}", str(seconds))
            for arg in self.config.capture_command
        ]
        result = _run(self.runner, argv, b"", seconds + 2)
        return _as_bytes(result)

    def transcribe(self, audio: bytes) -> str:
        if not self._enabled(self.config.stt_command):
            return ""
        result = _run(
            self.runner, self.config.stt_command, audio, self.config.timeout_s
        )
        return _as_text(result).strip()

    def speak(
        self,
        text: str,
        on_level: Callable[[float, float], None],
    ) -> None:
        if not self._enabled(self.config.tts_command) or not self.config.play_command:
            return
        pcm = _as_bytes(
            _run(
                self.runner,
                self.config.tts_command,
                text.encode("utf-8"),
                self.config.timeout_s,
            )
        )
        _run(self.runner, self.config.play_command, pcm, self.config.timeout_s)
        step = self.config.frame_samples / self.config.sample_rate
        for level in rms_envelope(pcm, frame_samples=self.config.frame_samples):
            on_level(level, time.monotonic())
            self.sleep(step)
