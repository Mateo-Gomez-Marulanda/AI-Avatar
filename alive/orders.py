"""Contrato cerrado entre la IA y el intermediario."""

from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_STATES = ("sentado", "parado", "musica")

_STATE_RE = re.compile(r"ESTADO=(sentado|parado|musica)")
_APP_RE = re.compile(r"ABRIR=([a-z0-9_-]+)")
_PREFIXES = ("ESTADO=", "ABRIR=", "ZONA=")


@dataclass(frozen=True)
class Order:
    kind: str
    value: str


@dataclass(frozen=True)
class ParseResult:
    clean_text: str
    orders: tuple[Order, ...]
    ignored: tuple[str, ...]


def parse_orders(text: str) -> ParseResult:
    orders: list[Order] = []
    ignored: list[str] = []
    kept: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        state = _STATE_RE.fullmatch(line)
        app = _APP_RE.fullmatch(line)
        if state:
            orders.append(Order("ESTADO", state.group(1)))
        elif app:
            orders.append(Order("ABRIR", app.group(1)))
        elif line.startswith(_PREFIXES):
            ignored.append(line)
        else:
            kept.append(raw)

    return ParseResult("\n".join(kept).strip(), tuple(orders), tuple(ignored))
