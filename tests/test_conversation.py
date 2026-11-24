# tests/test_conversation.py
from alive.domain.conversation import Conversation


def test_render_labels_roles_in_order():
    c = Conversation()
    c.add_user("hola")
    c.add_assistant("¿qué tal?")
    c.add_tool_note("App abierta: firefox")
    assert c.render() == (
        "Usuario: hola\n\n"
        "Alive: ¿qué tal?\n\n"
        "App abierta: firefox"
    )


def test_tool_result_includes_command_exit_code_and_output():
    c = Conversation()
    c.add_tool_result("printf hola", 0, "hola")
    text = c.render()
    assert "printf hola" in text and "código 0" in text and "hola" in text


def test_unshared_output_is_not_stored():
    c = Conversation()
    c.add_tool_result("cat archivo", 0, None)
    text = c.render()
    assert "salida no compartida" in text


def test_trims_oldest_messages_but_keeps_the_last():
    c = Conversation(max_chars=40)
    c.add_user("mensaje viejo que sobra")
    c.add_assistant("respuesta vieja")
    c.add_user("último")
    text = c.render()
    assert "último" in text
    assert "mensaje viejo" not in text
    assert len(text) <= 40


def test_truncates_a_single_oversized_message_with_marker():
    c = Conversation(max_chars=30)
    c.add_user("x" * 200)
    text = c.render()
    assert text.endswith("… [recortado]")
    assert len(text) <= 30


def test_rejects_non_positive_budget():
    import pytest
    with pytest.raises(ValueError):
        Conversation(max_chars=0)
