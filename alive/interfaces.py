"""Contratos entre piezas, sin dependencias de GTK."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar, runtime_checkable

from alive.providers.base import AiReply

T = TypeVar("T")


@runtime_checkable
class CommandRunner(Protocol):
    def run(self, argv: list[str], stdin: bytes, timeout_s: float) -> str: ...


@runtime_checkable
class AiProvider(Protocol):
    def ask(self, prompt: str, history: tuple[str, ...]) -> AiReply: ...


@runtime_checkable
class BackgroundLike(Protocol):
    def run(self, work: Callable[[], T], done: Callable[[T], None]) -> None: ...
