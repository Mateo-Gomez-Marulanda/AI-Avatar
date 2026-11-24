from alive.domain.actions import CommandResult
from alive.domain.config import CommandConfig
from alive.domain.contracts import ProviderError
from support import (
    DeferredBackground, FakeAi, FakeApprover, FakeExecutor, FakeLauncher,
    FakeView, FakeVoice, SilentApprover, make_config, make_mediator,
)


def action(payload):
    import json
    return "```alive-accion\n" + json.dumps(payload) + "\n```"


def command(comando="printf hola"):
    return action({"tipo": "comando", "comando": comando,
                   "que_hace": "Imprime hola", "por_que": "El usuario lo pidió"})


def app(alias="firefox"):
    return action({"tipo": "app", "alias": alias})


def test_memory_includes_user_and_assistant_once():
    ai = FakeAi(["Hola", "Sigamos"])
    m = make_mediator(ai=ai)
    m.submit_text("uno")
    m.submit_text("dos")
    prompt = ai.prompts[1]
    assert "Usuario: uno" in prompt and "Alive: Hola" in prompt
    assert prompt.count("Usuario: dos") == 1


def test_submit_sets_pensando_and_busy_status():
    statuses = []
    ai = FakeAi(["Hola"])
    m = make_mediator(ai=ai, background=DeferredBackground(),
                      on_status=lambda b, t: statuses.append((b, t)))
    m.submit_text("hola")
    assert m.busy is True
    assert (True, "Pensando…") in statuses


def test_app_action_opens_without_approval():
    ai = FakeAi([app("firefox")])
    launcher, approver = FakeLauncher(), FakeApprover()
    m = make_mediator(ai=ai, launcher=launcher, approver=approver)
    m.submit_text("abre firefox")
    assert launcher.opened == ["firefox"]
    assert approver.requests == []


def test_unknown_app_is_not_opened():
    ai = FakeAi([app("code")])
    launcher = FakeLauncher()
    m = make_mediator(ai=ai, launcher=launcher)
    m.submit_text("abre code")
    assert launcher.opened == []
    assert "App desconocida" in m.view.bubbles[-1]


def test_command_requests_approval_and_runs_once_approved():
    ai = FakeAi([command(), "Listo"])
    approver, executor = FakeApprover(True), FakeExecutor(CommandResult(0, "hola", "", False, 0.1))
    m = make_mediator(ai=ai, approver=approver, executor=executor)
    m.submit_text("ejecuta printf hola")
    assert approver.requests[0].command == "printf hola"
    assert executor.commands == ["printf hola"]
    assert "hola" in ai.prompts[1]
    assert m.view.bubbles[-1] == "Listo"


def test_denied_command_does_not_run_or_call_model_again():
    ai = FakeAi([command()])
    approver, executor = FakeApprover(False), FakeExecutor()
    m = make_mediator(ai=ai, approver=approver, executor=executor)
    m.submit_text("ejecuta algo")
    assert executor.commands == []
    assert len(ai.prompts) == 1
    assert m.view.bubbles[-1] == "Acción no ejecutada"


def test_disabled_commands_never_open_the_dialog():
    ai = FakeAi([command()])
    approver, executor = FakeApprover(True), FakeExecutor()
    m = make_mediator(ai=ai, config=make_config(commands=CommandConfig(enabled=False)),
                      approver=approver, executor=executor)
    m.submit_text("ejecuta algo")
    assert approver.requests == [] and executor.commands == []
    assert "desactivada" in m.view.bubbles[-1]


def test_unshared_output_never_reaches_later_prompts():
    ai = FakeAi([command(), "Hecho", "Otra respuesta"])
    executor = FakeExecutor(CommandResult(0, "SECRETO", "", False, 0.1))
    cfg = make_config(commands=CommandConfig(share_output_with_model=False))
    m = make_mediator(ai=ai, config=cfg, executor=executor)
    m.submit_text("ejecuta")
    assert "SECRETO" not in m.conversation.render()
    assert len(ai.prompts) == 1
    m.submit_text("otra cosa")
    assert "SECRETO" not in ai.prompts[1]


def test_command_limit_stops_the_turn():
    ai = FakeAi([command(), command()])
    cfg = make_config(commands=CommandConfig(max_per_turn=2))
    approver, executor = FakeApprover(True), FakeExecutor()
    m = make_mediator(ai=ai, config=cfg, approver=approver, executor=executor)
    m.submit_text("haz dos cosas")
    assert len(approver.requests) == 2
    assert "dime cómo seguir" in m.view.bubbles[-1]


def test_second_message_while_busy_does_not_call_model():
    bg = DeferredBackground()
    ai = FakeAi(["Hola"])
    m = make_mediator(ai=ai, background=bg)
    m.submit_text("uno")
    m.submit_text("dos")
    assert len(ai.prompts) == 0
    assert "Espera, estoy ocupado" in m.view.bubbles[-1]
    bg.flush()
    assert len(ai.prompts) == 1


def test_provider_error_is_visible():
    ai = FakeAi([], exc=ProviderError("timeout"))
    m = make_mediator(ai=ai)
    m.submit_text("hola")
    assert "timeout" in m.view.bubbles[-1]
    assert m.engine.state == "sentado" and m.busy is False


def test_unexpected_error_is_visible():
    ai = FakeAi([], exc=ValueError("roto"))
    m = make_mediator(ai=ai)
    m.submit_text("hola")
    assert "Error inesperado" in m.view.bubbles[-1]
    assert m.busy is False


def test_parse_error_shows_message_and_does_not_execute():
    ai = FakeAi(["```alive-accion\n{no json}\n```"])
    executor, approver = FakeExecutor(), FakeApprover()
    m = make_mediator(ai=ai, executor=executor, approver=approver)
    m.submit_text("haz algo")
    assert executor.commands == [] and approver.requests == []
    assert "JSON malformado" in m.view.bubbles[-1]


def test_pending_approval_keeps_turn_busy_until_decision():
    ai = FakeAi([command(), "Listo"])
    approver, executor = SilentApprover(), FakeExecutor()
    m = make_mediator(ai=ai, approver=approver, executor=executor)
    m.submit_text("ejecuta")
    assert len(approver.requests) == 1
    assert executor.commands == [] and len(ai.prompts) == 1 and m.busy is True
    approver.decision(False)
    assert executor.commands == [] and m.busy is False
    assert m.view.bubbles[-1] == "Acción no ejecutada"


def test_executor_error_is_visible_and_frees_turn():
    class BrokenExecutor:
        def run(self, command):
            raise RuntimeError("boom")

    m = make_mediator(ai=FakeAi([command()]), executor=BrokenExecutor())
    m.submit_text("ejecuta")
    assert "No pude ejecutar el comando: boom" in m.view.bubbles[-1]
    assert m.busy is False and m.engine.state == "sentado"
