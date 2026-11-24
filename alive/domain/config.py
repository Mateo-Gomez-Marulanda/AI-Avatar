"""Configuración del avatar: proveedor de IA, apps, zonas y voz."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

ANCHORS = frozenset({"top", "left", "right", "bottom", "floating"})


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
    timeout_s: float = 60.0
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
class Config:
    provider: ProviderConfig
    apps: dict[str, str]
    zones: dict[str, Zone]
    voice: VoiceConfig
    idle_state: str = "sentado"
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


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"no existe el archivo de configuración: {p}")
    with p.open("rb") as fh:
        data = tomllib.load(fh)

    provider_data = _section(data, "provider")
    command = provider_data.get("command")
    if not isinstance(command, list) or not command:
        raise ConfigError("provider.command debe ser una lista no vacía")
    provider = _build(ProviderConfig, provider_data, "provider")

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

    extras = {
        key: data[key]
        for key in ("idle_state", "bubble_ms_per_char", "drag_snap_ms")
        if key in data
    }
    try:
        return Config(provider=provider, apps=apps, zones=zones, voice=voice, **extras)
    except TypeError as exc:
        raise ConfigError(f"configuración: {exc}") from exc
