# tests/test_actions.py
import json

import pytest

from alive.domain.actions import AppAction, CommandAction, parse_action


def block(payload) -> str:
    return "```alive-accion\n" + json.dumps(payload) + "\n```"


def test_parses_app_action_and_cleans_text():
    parsed = parse_action("Abro eso.\n" + block({"tipo": "app", "alias": ["firefox", "code"]}))
    assert parsed.action == AppAction(("firefox", "code"))
    assert parsed.text == "Abro eso."
    assert parsed.error is None


def test_accepts_a_single_alias_as_string():
    parsed = parse_action(block({"tipo": "app", "alias": "firefox"}))
    assert parsed.action == AppAction(("firefox",))


def test_parses_command_action():
    parsed = parse_action(block({
        "tipo": "comando", "comando": "printf hola",
        "que_hace": "Imprime hola", "por_que": "El usuario lo pidió",
    }))
    assert parsed.action == CommandAction("printf hola", "Imprime hola", "El usuario lo pidió")


def test_more_than_one_block_is_ambiguous_and_executes_nothing():
    parsed = parse_action(block({"tipo": "app", "alias": "firefox"}) + block({"tipo": "app", "alias": "code"}))
    assert parsed.action is None
    assert "ambigua" in parsed.error.lower()
    assert "alive-accion" not in parsed.text


def test_invalid_json_is_an_error():
    parsed = parse_action("```alive-accion\n{no es json}\n```")
    assert parsed.action is None and "JSON" in parsed.error


def test_missing_fields_are_rejected():
    parsed = parse_action(block({"tipo": "comando", "comando": "ls"}))
    assert parsed.action is None and "que_hace" in parsed.error


def test_unknown_type_is_rejected():
    parsed = parse_action(block({"tipo": "borrar", "alias": "firefox"}))
    assert parsed.action is None and "tipo" in parsed.error


def test_empty_text_without_action_is_kept():
    parsed = parse_action("")
    assert parsed.text == "" and parsed.action is None and parsed.error is None


@pytest.mark.parametrize("alias", [
    123,
    ["firefox", 123],
    ["firefox", ""],
    [],
    ["", "firefox"],
])
def test_invalid_alias_rejects_the_whole_action(alias):
    parsed = parse_action(block({"tipo": "app", "alias": alias}))
    assert parsed.action is None
    assert "Acción inválida" in parsed.error and "alias" in parsed.error
