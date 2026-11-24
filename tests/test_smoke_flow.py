import struct
import sys
from dataclasses import replace

from alive.application.audio import VoiceService
from alive.application.commands import ShellCommandExecutor
from alive.infrastructure.providers.cli import CliProvider, SubprocessRunner
from alive.domain.config import ProviderConfig, VoiceConfig, CommandConfig
from support import (
    FakeAi, FakeApprover, FakeBackground, FakeLauncher, FakeTimer, FakeView,
    FakeVoice, InlineBackground, make_config, make_mediator,
)


def test_fake_cli_command_flow_end_to_end(tmp_path):
    script = tmp_path / "fake_cli.py"
    counter = tmp_path / "calls.txt"
    script.write_text(f'''\
import json, pathlib
counter = pathlib.Path({str(counter)!r})
n = int(counter.read_text()) if counter.exists() else 0
counter.write_text(str(n + 1))
if n == 0:
    text = "Voy a ejecutarlo\\n```alive-accion\\n" + json.dumps({{
        "tipo": "comando", "comando": "printf hola",
        "que_hace": "Imprime hola", "por_que": "El usuario lo pidió",
    }}) + "\\n```"
else:
    text = "Listo: hola"
print(json.dumps({{"type": "text", "sessionID": "ses_x",
                   "part": {{"type": "text", "messageID": "m1", "text": text}}}}))
''')
    ai = CliProvider(
        ProviderConfig(command=[sys.executable, str(script)], output_format="json"),
        SubprocessRunner(),
    )
    view, voice, launcher = FakeView(), FakeVoice(), FakeLauncher()
    approver = FakeApprover(True)
    executor = ShellCommandExecutor(timeout_s=5.0, workdir=str(tmp_path))
    base = make_config(commands=CommandConfig(share_output_with_model=True))
    mediator = make_mediator(
        ai=ai, view=view, voice=voice, launcher=launcher, approver=approver,
        executor=executor, background=InlineBackground(),
        config=replace(base, commands=replace(base.commands, working_dir=str(tmp_path))),
    )
    mediator.submit_text("ejecuta printf hola")

    assert approver.requests[0].command == "printf hola"
    assert "printf hola" in mediator.conversation.render()
    assert "hola" in mediator.conversation.render()
    tool_msg = mediator.conversation.messages[-2]
    assert tool_msg.role == "tool"
    assert tool_msg.text == "Resultado del comando `printf hola` (código 0):\nhola"
    assert view.bubbles[-1] == "Listo: hola"
    assert mediator.busy is False


def test_real_voice_chain_fake_cli_end_to_end():
    pcm = struct.pack("<h", 16000) * 1024
    played = []

    def runner(argv, stdin, timeout_s):
        if argv[0] == "rec":
            return b"audio capturado"
        if argv[0] == "stt":
            return b"hola"
        if argv[0] == "tts":
            assert stdin == "Hola".encode("utf-8")
            return pcm
        played.append(stdin)
        return b""

    voice_cfg = VoiceConfig(
        enabled=True,
        capture_command=["rec"],
        stt_command=["stt"],
        tts_command=["tts"],
        play_command=["play"],
        sample_rate=16000,
        frame_samples=1024,
        timeout_s=5.0,
    )
    config = replace(make_config(), voice=voice_cfg)
    background, timer, view = FakeBackground(), FakeTimer(), FakeView()
    voice = VoiceService(voice_cfg, runner, clock=lambda: 1.0)
    mediator = make_mediator(
        ai=FakeAi(["Hola"]), voice=voice, view=view, config=config,
        background=background, timer=timer,
    )

    mediator.ptt_start()
    mediator.ptt_end()
    background.flush()  # captura + STT → texto
    background.flush()  # modelo → respuesta
    assert view.bubbles[-1] == "Hola"
    assert mediator.busy is True and mediator.engine.state == "hablando"

    background.flush()  # TTS → PCM y duración real
    assert len(timer.pending) == 1
    timer.fire()  # nivel de la boca en el hilo GTK
    assert mediator.engine.tick(1.0).mouth > 0.0
    assert played == [] and mediator.busy is True

    background.flush()  # reproducción → fin del turno
    assert played == [pcm]
    assert timer.pending == []
    assert mediator.busy is False
    frame = mediator.engine.tick(1.0)
    assert frame.state in ("sentado", "parado") and frame.mouth == 0.0
