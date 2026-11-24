"""Contrato de acciones que una respuesta de la IA puede llevar."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_BLOCK = re.compile(r"```alive-accion[ \t]*\r?\n(.*?)```", re.DOTALL)

_COMANDO_MAX = 2000
_EXPLICACION_MAX = 1000


@dataclass(frozen=True)
class AppAction:
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class CommandAction:
    command: str
    what: str
    why: str


@dataclass(frozen=True)
class CommandRequest:
    command: str
    what: str
    why: str
    workdir: str


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


@dataclass(frozen=True)
class ParsedReply:
    text: str
    action: AppAction | CommandAction | None = None
    error: str | None = None


def _parse_app(data: dict, text: str) -> ParsedReply:
    raw = data.get("alias")
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, list):
        candidates = raw
    else:
        candidates = []
    aliases = tuple(c for c in candidates if isinstance(c, str) and c)
    if not aliases:
        return ParsedReply(text, error="Acción inválida: falta el alias")
    return ParsedReply(text, action=AppAction(aliases))


def _parse_comando(data: dict, text: str) -> ParsedReply:
    for name in ("comando", "que_hace", "por_que"):
        value = data.get(name)
        if not isinstance(value, str) or not value:
            return ParsedReply(text, error=f"Acción inválida: falta el campo {name}")
    if len(data["comando"]) > _COMANDO_MAX:
        return ParsedReply(text, error="Acción inválida: comando demasiado largo")
    for name in ("que_hace", "por_que"):
        if len(data[name]) > _EXPLICACION_MAX:
            return ParsedReply(text, error=f"Acción inválida: {name} demasiado largo")
    return ParsedReply(
        text,
        action=CommandAction(data["comando"], data["que_hace"], data["por_que"]),
    )


def parse_action(reply: str) -> ParsedReply:
    """Extrae una acción del bloque ``alive-accion`` embebido en la respuesta."""
    blocks = _BLOCK.findall(reply)
    text = _BLOCK.sub("", reply).strip()
    if len(blocks) > 1:
        return ParsedReply(text, error="Respuesta ambigua: más de una acción")
    if not blocks:
        return ParsedReply(text)
    try:
        data = json.loads(blocks[0])
    except json.JSONDecodeError:
        return ParsedReply(text, error="Acción inválida: JSON malformado")
    if not isinstance(data, dict):
        return ParsedReply(text, error="Acción inválida: se esperaba un objeto")
    tipo = data.get("tipo")
    if tipo == "app":
        return _parse_app(data, text)
    if tipo == "comando":
        return _parse_comando(data, text)
    return ParsedReply(text, error="Acción inválida: tipo desconocido")
