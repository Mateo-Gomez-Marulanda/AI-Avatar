"""Compatibilidad temporal: los contratos viven en alive.domain.contracts."""

from alive.domain.contracts import (
    AiProvider,
    AvatarViewLike,
    BackgroundLike,
    CommandRunner,
    VoiceLike,
)

__all__ = [
    "AiProvider",
    "AvatarViewLike",
    "BackgroundLike",
    "CommandRunner",
    "VoiceLike",
]
