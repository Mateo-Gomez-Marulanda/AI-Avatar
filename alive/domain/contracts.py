"""Contratos del dominio, sin dependencias de GTK ni de subprocess."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

from alive.domain.animation import Frame

T = TypeVar("T")


@dataclass(frozen=True)
class AiReply:
    text: str
    session_id: str | None = None


class ProviderError(RuntimeError):
    pass


@runtime_checkable
class CommandRunner(Protocol):
    def run(self, argv: list[str], stdin: bytes, timeout_s: float) -> str: ...


@runtime_checkable
class AiProvider(Protocol):
    def ask(self, prompt: str) -> AiReply: ...


@runtime_checkable
class BackgroundLike(Protocol):
    def run(self, work: Callable[[], T], done: Callable[[T], None]) -> None: ...


@runtime_checkable
class AvatarViewLike(Protocol):
    def show_bubble(self, text: str, ms_per_char: int) -> None: ...

    def hide_bubble(self) -> None: ...

    def render(self, frame: Frame) -> None: ...

    def set_click_through(self, enabled: bool) -> None: ...

    def snap_to(self, zone_name: str) -> None: ...


@runtime_checkable
class VoiceLike(Protocol):
    def record(self, seconds: float) -> bytes: ...

    def transcribe(self, audio: bytes) -> str: ...

    def speak(self, text: str, on_level: Callable[[float, float], None]) -> None: ...
