"""Configuración del avatar: proveedor, apps, zonas, voz y comportamiento."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from alive.domain.animation import STATES

ANCHORS = frozenset({"top", "left", "right", "bottom", "floating"})
ROOT_KEYS = frozenset({
    "provider",
    "apps",
    "zones",
    "voice",
    "commands",
    "conversation",
    "music",
    "idle_states",
    "idle_switch_s",
    "bubble_ms_per_char",
    "drag_snap_ms",
})


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Zone:
    anchor: str
    margin: int = 0
    x: int = 0
    y: int = 0
    click_through: bool = False


@dataclass(frozen=True)
class ProviderConfig:
    command: list[str]
    timeout_s: float = 90.0
    output_format: str = "text"
    workdir: str = ""


@dataclass(frozen=True)
class VoiceConfig:
    stt_command: list[str] = field(default_factory=list)
    tts_command: list[str] = field(default_factory=list)
    play_command: list[str] = field(default_factory=list)
    capture_command: list[str] = field(default_factory=list)
    sample_rate: int = 16000
    frame_samples: int = 1024
    timeout_s: float = 30.0
    enabled: bool = True


@dataclass(frozen=True)
class CommandConfig:
    enabled: bool = True
    timeout_s: float = 30.0
    max_output_bytes: int = 8192
    max_per_turn: int = 3
    approval_timeout_s: float = 120.0
    working_dir: str = "~"
    share_output_with_model: bool = True


@dataclass(frozen=True)
class ConversationConfig:
    max_chars: int = 6000


@dataclass(frozen=True)
class MusicConfig:
    enabled: bool = True
    players: list[str] = field(default_factory=lambda: ["spotify"])
    poll_s: float = 5.0


@dataclass(frozen=True)
class Config:
    provider: ProviderConfig
    apps: dict[str, str]
    zones: dict[str, Zone]
    voice: VoiceConfig
    commands: CommandConfig = field(default_factory=CommandConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    music: MusicConfig = field(default_factory=MusicConfig)
    idle_states: tuple[str, ...] = ("sentado", "parado")
    idle_switch_s: float = 20.0
    bubble_ms_per_char: int = 45
    drag_snap_ms: int = 250


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{name} debe ser una tabla")
    return value


def _build(cls: type, values: dict[str, Any], section: str):
    allowed = {f.name for f in fields(cls)}
    unknown = set(values) - allowed
    if unknown:
        raise ConfigError(f"{section}: claves desconocidas {sorted(unknown)}")
    try:
        return cls(**values)
    except TypeError as exc:
        raise ConfigError(f"{section}: {exc}") from exc


def _check_number(
    value: Any,
    label: str,
    *,
    minimum: float | None = None,
    inclusive: bool = True,
    integer: bool = False,
) -> None:
    expected = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, expected):
        raise ConfigError(f"{label} debe ser {'un entero' if integer else 'un número'}")
    if minimum is None:
        return
    if (value >= minimum) if inclusive else (value > minimum):
        return
    comparison = "mayor o igual que" if inclusive else "mayor que"
    raise ConfigError(f"{label} debe ser {comparison} {minimum}")


def _check_bool(value: Any, label: str) -> None:
    if not isinstance(value, bool):
        raise ConfigError(f"{label} debe ser booleano")


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"no existe el archivo de configuración: {p}")
    with p.open("rb") as fh:
        data = tomllib.load(fh)

    unknown = set(data) - ROOT_KEYS
    if unknown:
        raise ConfigError(f"claves desconocidas: {sorted(unknown)}")

    provider_data = _section(data, "provider")
    command = provider_data.get("command")
    if not isinstance(command, list) or not command:
        raise ConfigError("provider.command debe ser una lista no vacía")
    provider = _build(ProviderConfig, provider_data, "provider")
    if provider.output_format not in ("text", "json"):
        raise ConfigError(f"provider.output_format inválido: {provider.output_format!r}")
    _check_number(provider.timeout_s, "provider.timeout_s", minimum=0, inclusive=False)

    apps_data = _section(data, "apps")
    apps = {str(k): str(v) for k, v in apps_data.items()}

    zones_data = _section(data, "zones")
    zones: dict[str, Zone] = {}
    for name, values in zones_data.items():
        if not isinstance(values, dict):
            raise ConfigError(f"zones.{name} debe ser una tabla")
        anchor = values.get("anchor")
        if anchor not in ANCHORS:
            raise ConfigError(f"zones.{name}.anchor inválido: {anchor!r}")
        zones[str(name)] = _build(Zone, values, f"zones.{name}")

    voice = _build(VoiceConfig, _section(data, "voice"), "voice")

    commands = _build(CommandConfig, _section(data, "commands"), "commands")
    _check_bool(commands.enabled, "commands.enabled")
    _check_number(commands.timeout_s, "commands.timeout_s", minimum=0, inclusive=False)
    _check_number(commands.max_output_bytes, "commands.max_output_bytes", minimum=1, integer=True)
    _check_number(commands.max_per_turn, "commands.max_per_turn", minimum=1, integer=True)
    _check_number(
        commands.approval_timeout_s, "commands.approval_timeout_s", minimum=0, inclusive=False
    )
    _check_bool(commands.share_output_with_model, "commands.share_output_with_model")

    conversation = _build(
        ConversationConfig, _section(data, "conversation"), "conversation"
    )
    _check_number(conversation.max_chars, "conversation.max_chars", minimum=1, integer=True)

    music = _build(MusicConfig, _section(data, "music"), "music")
    _check_bool(music.enabled, "music.enabled")
    if not isinstance(music.players, list) or any(
        not isinstance(player, str) for player in music.players
    ):
        raise ConfigError("music.players debe ser una lista de textos")
    _check_number(music.poll_s, "music.poll_s", minimum=0, inclusive=False)

    idle_states = data.get("idle_states", ("sentado", "parado"))
    if not isinstance(idle_states, (list, tuple)) or not idle_states:
        raise ConfigError("idle_states debe ser una lista no vacía")
    invalid = [state for state in idle_states if state not in STATES]
    if invalid:
        raise ConfigError(f"estados idle desconocidos: {invalid!r}")
    idle_states = tuple(idle_states)

    idle_switch_s = data.get("idle_switch_s", 20.0)
    bubble_ms_per_char = data.get("bubble_ms_per_char", 45)
    drag_snap_ms = data.get("drag_snap_ms", 250)
    _check_number(idle_switch_s, "idle_switch_s")
    _check_number(bubble_ms_per_char, "bubble_ms_per_char", integer=True)
    _check_number(drag_snap_ms, "drag_snap_ms", integer=True)

    return Config(
        provider=provider,
        apps=apps,
        zones=zones,
        voice=voice,
        commands=commands,
        conversation=conversation,
        music=music,
        idle_states=idle_states,
        idle_switch_s=idle_switch_s,
        bubble_ms_per_char=bubble_ms_per_char,
        drag_snap_ms=drag_snap_ms,
    )
