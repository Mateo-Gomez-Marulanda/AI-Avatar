from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AiReply:
    text: str


class ProviderError(RuntimeError):
    pass
