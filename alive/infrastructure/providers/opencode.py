"""Parser de la salida NDJSON de `opencode run`."""

from __future__ import annotations

import json
from dataclasses import dataclass

from alive.domain.contracts import ProviderError


@dataclass(frozen=True)
class OpencodeReply:
    text: str
    session_id: str | None = None


_FREE_LIMIT_ERROR = (
    "OpenCode alcanzó el límite gratuito; conecta un proveedor o cambia de modelo."
)
_MISSING_AGENT_ERROR = (
    "Falta el agente alive en OpenCode; "
    "copia .opencode/agents/alive.md a ~/.config/opencode/agents/."
)


def parse_opencode_output(output: str) -> OpencodeReply:
    """Extrae el último mensaje de texto y el último id de sesión del NDJSON."""
    session_id: str | None = None
    current_message_id: str | None = None
    parts: list[str] = []

    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(event, dict):
            continue

        if event.get("sessionID"):
            session_id = event["sessionID"]

        kind = event.get("type")
        if kind == "error":
            error = event.get("error")
            if not isinstance(error, dict):
                error = {}
            error_type = error.get("type", "")
            message = str(error.get("message", ""))
            if error_type == "provider.free-limit":
                raise ProviderError(_FREE_LIMIT_ERROR)
            if "Agent not found" in message:
                raise ProviderError(_MISSING_AGENT_ERROR)
            raise ProviderError(f"OpenCode: {message}")

        if kind != "text":
            continue
        part = event.get("part")
        if not isinstance(part, dict) or part.get("type") != "text":
            continue

        message_id = part.get("messageID") or event.get("messageID") or ""
        if message_id != current_message_id:
            current_message_id = message_id
            parts = []
        text = part.get("text")
        if isinstance(text, str):
            parts.append(text)

    text = "".join(parts).strip()
    if not text:
        raise ProviderError(f"OpenCode no devolvió texto: {output[:200]!r}")
    return OpencodeReply(text=text, session_id=session_id)
