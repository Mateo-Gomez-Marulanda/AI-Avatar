"""Prompt del asistente conversacional: sistema y combinación con el historial."""

from __future__ import annotations

from collections.abc import Mapping

from alive.domain.conversation import Conversation


def build_system_prompt(apps: Mapping[str, str], commands_enabled: bool) -> str:
    lines = [
        "Eres Alive, un asistente de escritorio.",
        "Responde en el idioma del usuario, con respuestas claras y breves cuando sea posible.",
        "Nunca digas que ejecutaste algo. Si necesitas una acción, propónla y espera la decisión del usuario.",
        "No incluyas animaciones, estados visuales, sprites ni tiempos.",
        "",
        "Apps disponibles (solo estas, por su alias):",
    ]
    lines += [f"- {alias}: {command}" for alias, command in apps.items()]
    lines += [
        "",
        "Contrato de acción:",
        'Si propones una acción, entrega un solo bloque ```alive-accion``` con:',
        '{"tipo": "app", "alias": "<alias>"}',
    ]
    if commands_enabled:
        lines += [
            'También puedes proponer: {"tipo": "comando", "comando": "<texto>",'
            ' "que_hace": "<qué hace>", "por_que": "<por qué>"}',
        ]
    else:
        lines += [
            "No hay ejecución de comandos disponible; no propongas comandos.",
        ]
    lines += [
        "Usa como máximo un bloque por respuesta y solo cuando propongas una acción.",
    ]
    return "\n".join(lines)


def build_prompt(system_prompt: str, conversation: Conversation) -> str:
    transcript = conversation.render()
    if not transcript:
        return system_prompt
    return f"{system_prompt}\n\n{transcript}"
