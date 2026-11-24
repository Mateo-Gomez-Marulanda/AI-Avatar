import json
import sys

import pytest

from alive.domain.config import ProviderConfig
from alive.domain.contracts import AiReply, ProviderError
from alive.infrastructure.providers.cli import CliProvider, SubprocessRunner


def test_strips_ansi_from_text_output():
    p = CliProvider(ProviderConfig(command=["x"]), lambda argv, stdin, timeout_s: "\x1b[31mHola\x1b[0m mundo")
    assert p.ask("q") == AiReply("Hola mundo")


def test_strips_opencode_status_header_in_text_mode():
    out = "\x1b[0m\n> build · big-pickle\nOK\n"
    p = CliProvider(ProviderConfig(command=["opencode", "run"]), lambda argv, stdin, timeout_s: out)
    assert p.ask("q").text == "OK"


def test_json_mode_parses_opencode_events():
    line = json.dumps({"type": "text", "sessionID": "ses_1",
                       "part": {"type": "text", "messageID": "m1", "text": "Hola"}})
    p = CliProvider(ProviderConfig(command=["opencode", "run"], output_format="json"),
                    lambda argv, stdin, timeout_s: line)
    assert p.ask("q") == AiReply("Hola", "ses_1")


def test_runner_reports_timeout():
    with pytest.raises(ProviderError):
        SubprocessRunner().run(["python3", "-c", "import time; time.sleep(1)"], b"", 0.01)


def test_runner_reports_nonzero_exit_with_stderr():
    with pytest.raises(ProviderError) as exc:
        SubprocessRunner().run(
            [sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(2)"], b"", 5
        )
    assert "boom" in str(exc.value)


def test_runner_uses_cwd(tmp_path):
    out = SubprocessRunner(cwd=str(tmp_path)).run(["/bin/sh", "-c", "pwd"], b"", 5)
    assert out.strip() == str(tmp_path)
