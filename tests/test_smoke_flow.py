import sys
from dataclasses import replace

from alive.application.commands import ShellCommandExecutor
from alive.infrastructure.providers.cli import CliProvider, SubprocessRunner
from alive.domain.config import ProviderConfig
from support import (
    FakeApprover, FakeLauncher, FakeView, FakeVoice, InlineBackground, make_config,
    make_mediator,
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
    base = make_config()
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
