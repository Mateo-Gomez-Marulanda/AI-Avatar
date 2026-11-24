"""Memoria de conversación del asistente."""

from __future__ import annotations

from dataclasses import dataclass

_TRUNC = "… [recortado]"


@dataclass(frozen=True)
class Message:
    role: str
    text: str


def _render_message(m: Message) -> str:
    if m.role == "user":
        return f"Usuario: {m.text}"
    if m.role == "assistant":
        return f"Alive: {m.text}"
    return m.text


class Conversation:
    """Almacena el historial de la conversación con un presupuesto de tamaño."""

    def __init__(self, max_chars: int = 6000) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars debe ser mayor que cero")
        self.max_chars = max_chars
        self.messages: list[Message] = []

    def add_user(self, text: str) -> None:
        self.messages.append(Message("user", text))

    def add_assistant(self, text: str) -> None:
        self.messages.append(Message("assistant", text))

    def add_tool_note(self, text: str) -> None:
        self.messages.append(Message("tool", text))

    def add_tool_result(self, command: str, exit_code: int, output: str | None) -> None:
        text = f"Resultado del comando `{command}` (código {exit_code}):"
        if output is None:
            text += "\nsalida no compartida"
        elif output:
            text += f"\n{output}"
        self.messages.append(Message("tool", text))

    def render(self) -> str:
        parts = [_render_message(m) for m in self.messages]
        while len(parts) > 1 and len("\n\n".join(parts)) > self.max_chars:
            parts.pop(0)
        text = "\n\n".join(parts)
        if len(text) > self.max_chars:
            text = text[: self.max_chars - len(_TRUNC)] + _TRUNC
        return text
