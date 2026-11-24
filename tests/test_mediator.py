from alive.domain.actions import CommandResult
from alive.domain.config import CommandConfig
from alive.domain.contracts import ProviderError
from support import (
    DeferredBackground, FakeAi, FakeApprover, FakeExecutor, FakeLauncher,
    FakeView, FakeVoice, MalformedAi, SilentApprover, WorkerCrashBackground,
    make_config, make_mediator,
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
    m = make_mediator(ai=ai, approver=approver, executor=executor,
                      config=make_config(commands=CommandConfig(share_output_with_model=True)))
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
    cfg = make_config(commands=CommandConfig(max_per_turn=2, share_output_with_model=True))
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


def test_malformed_ai_reply_is_visible_and_frees_turn():
    m = make_mediator(ai=MalformedAi(), background=WorkerCrashBackground())
    m.submit_text("hola")
    assert any("Error inesperado" in b for b in m.view.bubbles)
    assert m.busy is False and m.engine.state == "sentado"


def test_non_provider_transcription_error_is_visible():
    voice = FakeVoice()
    voice.transcribe_error = RuntimeError("sin motor")
    m = make_mediator(ai=FakeAi([]), voice=voice, background=WorkerCrashBackground())
    m.ptt_end(0.5)
    assert any("No pude transcribir: sin motor" in b for b in m.view.bubbles)
    assert m.engine.state == "sentado"


def test_provider_transcription_failure_keeps_empty_result_bubble():
    voice = FakeVoice()
    voice.transcribe_error = ProviderError("sin motor")
    m = make_mediator(ai=FakeAi([]), voice=voice)
    m.ptt_end(0.5)
    assert m.view.bubbles[-1] == "No pude escuchar"
    assert m.engine.state == "sentado"


def test_ptt_is_ignored_while_busy():
    background = DeferredBackground()
    voice = FakeVoice()
    m = make_mediator(ai=FakeAi(["Hola"]), background=background, voice=voice)
    m.submit_text("uno")
    m.ptt_start()
    m.ptt_end(0.5)
    assert voice.records == []
    assert len(background.pending) == 1
    assert m.engine.state == "pensando"


def test_drag_end_delegates_to_engine_with_current_time():
    class EngineSpy:
        def __init__(self):
            self.ended = None
        def end_drag(self, now):
            self.ended = now

    engine = EngineSpy()
    m = make_mediator(ai=FakeAi([]), engine=engine, clock=lambda: 7.0)
    m.on_drag_end("barra")
    assert engine.ended == 7.0


def test_missing_tts_does_not_break_text_reply():
    voice = FakeVoice()
    voice.speak_error = RuntimeError("sin tts")
    m = make_mediator(ai=FakeAi(["Hola sin voz"]), voice=voice)
    m.submit_text("¿qué tal?")
    assert m.view.bubbles[-1] == "Hola sin voz"
    assert voice.spoken == [] and m.busy is False


def test_voice_speaks_final_reply_after_command():
    voice = FakeVoice()
    m = make_mediator(
        ai=FakeAi([command(), "Listo"]),
        voice=voice,
        approver=FakeApprover(True),
        executor=FakeExecutor(),
        config=make_config(commands=CommandConfig(share_output_with_model=True)),
    )
    m.submit_text("ejecuta")
    assert voice.spoken == ["Listo"]


def test_turn_stays_busy_until_speech_is_done():
    background = DeferredBackground()
    voice = FakeVoice()
    voice.defer_speech = True
    m = make_mediator(ai=FakeAi(["Hola"]), voice=voice, background=background)
    m.submit_text("hola")
    background.flush()
    assert m.busy is True and m.engine.state == "hablando"
    voice.finish_speech()
    assert m.busy is False and m.engine.state == "sentado"


def test_speech_error_finishes_turn_and_keeps_reply_visible():
    background = DeferredBackground()
    voice = FakeVoice()
    voice.defer_speech = True
    m = make_mediator(ai=FakeAi(["Hola"]), voice=voice, background=background)
    m.submit_text("hola")
    background.flush()
    voice.finish_speech("tts roto")
    assert m.busy is False and m.view.bubbles[-1] == "Hola"


def test_ptt_end_without_argument_uses_mediator_clock():
    voice = FakeVoice()
    times = [1.0, 3.5]
    def clock():
        return times.pop(0) if len(times) > 1 else times[0]
    m = make_mediator(ai=FakeAi([]), voice=voice, clock=clock)
    m.ptt_start()
    m.ptt_end()
    assert voice.records == [2.5]


def test_quiet_moves_to_corner_and_restores_exact_rect():
    from alive.domain.config import Zone
    from alive.domain.geometry import Rect

    view = FakeView()
    config = make_config(zones={"no_molestar": Zone("bottom-right", margin=12)})
    m = make_mediator(ai=FakeAi([]), config=config, view=view)
    original = view.current_rect()
    m.toggle_no_molestar()
    assert view.snapped[-1] == "no_molestar" and view.click_through is True
    assert m.engine.state == "no_molestar"
    m.toggle_no_molestar()
    assert view.snapped[-1] == original and view.click_through is False
    assert isinstance(original, Rect)


def test_quiet_off_during_turn_restores_in_flight_state():
    m = make_mediator(ai=FakeAi([]), background=DeferredBackground())
    m.submit_text("uno")
    m.toggle_no_molestar()
    m.toggle_no_molestar()
    assert m.engine.state == "pensando" and m.busy is True


def test_speech_ends_while_quiet_then_quiet_off_stays_idle():
    background = DeferredBackground()
    voice = FakeVoice()
    voice.defer_speech = True
    m = make_mediator(ai=FakeAi(["Hola"]), voice=voice, background=background)
    m.submit_text("hola")
    background.flush()
    m.toggle_no_molestar()
    assert m.engine.state == "hablando"
    voice.finish_speech()
    assert m.busy is False and m.engine.state == "no_molestar"
    m.toggle_no_molestar()
    assert m.engine.state in m.engine.idle_states
    assert m.engine.speaking_until == 0.0


def test_mediator_requires_an_injected_timer():
    import pytest
    from alive.application.mediator import Mediator
    from alive.domain.animation import AnimationEngine
    from support import InlineBackground

    with pytest.raises(TypeError, match="timer"):
        Mediator(
            engine=AnimationEngine(),
            view=FakeView(),
            ai=FakeAi([]),
            voice=FakeVoice(),
            launcher=FakeLauncher(),
            config=make_config(),
            clock=lambda: 0.0,
            background=InlineBackground(),
            approver=FakeApprover(),
            executor=FakeExecutor(),
        )
