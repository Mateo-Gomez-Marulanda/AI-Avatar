from alive.application.prompt import build_prompt, build_system_prompt
from alive.domain.conversation import Conversation

APPS = {"firefox": "firefox --new-window", "code": "code"}


def test_prompt_names_alive_apps_and_language_rule():
    p = build_system_prompt(APPS, commands_enabled=True)
    assert "Eres Alive" in p
    assert "idioma del usuario" in p
    assert "firefox: firefox --new-window" in p and "code: code" in p


def test_prompt_explains_the_single_action_block():
    p = build_system_prompt(APPS, commands_enabled=True)
    assert "alive-accion" in p
    assert '"tipo": "app"' in p and '"tipo": "comando"' in p
    assert "Nunca digas que ejecutaste" in p


def test_prompt_forbids_visual_decisions():
    p = build_system_prompt(APPS, commands_enabled=True)
    assert "No incluyas animaciones" in p
    assert "ESTADO=" not in p and "ABRIR=" not in p


def test_disabled_commands_are_not_offered():
    p = build_system_prompt(APPS, commands_enabled=False)
    assert "No hay ejecución de comandos disponible" in p
    assert '"tipo": "comando"' not in p
    assert '"tipo": "app"' in p


def test_build_prompt_appends_transcript_once():
    c = Conversation()
    c.add_user("hola")
    p = build_prompt("SISTEMA", c)
    assert p.startswith("SISTEMA")
    assert p.count("Usuario: hola") == 1


def test_build_prompt_with_empty_history_is_just_the_system_prompt():
    assert build_prompt("SISTEMA", Conversation()) == "SISTEMA"
