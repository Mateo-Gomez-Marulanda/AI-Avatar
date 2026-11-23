from alive.config import ProviderConfig
from alive.providers.cli import CliProvider, SubprocessRunner

def test_strips_ansi_from_output():
    out = "\x1b[31mHola\x1b[0m mundo"
    p = CliProvider(ProviderConfig(command=["x"], session_mode="oneshot"),
                    lambda argv, stdin, timeout_s: out)
    assert p.ask("q", ()).text == "Hola mundo"

def test_resume_reuses_session_id():
    calls = []
    def runner(argv, stdin, timeout_s):
        calls.append(argv)
        return "primera\nSESSION=abc123\n" if len(calls) == 1 else "segunda\nSESSION=abc123\n"
    cfg = ProviderConfig(command=["cli"], session_mode="resume", session_flag="--resume",
                         session_id_regex=r"^SESSION=(.+)$")
    p = CliProvider(cfg, runner)
    assert p.ask("uno", ()).text == "primera"
    p.ask("dos", ("uno",))
    assert "--resume" in calls[1] and "abc123" in calls[1]
    assert "--resume" not in calls[0]

def test_oneshot_never_passes_session_flag():
    calls = []
    p = CliProvider(ProviderConfig(command=["cli"], session_mode="oneshot", session_flag="--resume"),
                    lambda argv, stdin, timeout_s: (calls.append(argv), "ok")[1])
    p.ask("uno", ()); p.ask("dos", ("uno",))
    assert all("--resume" not in c for c in calls)

def test_runner_reports_timeout():
    import pytest
    from alive.providers.base import ProviderError
    with pytest.raises(ProviderError):
        SubprocessRunner().run(["python3", "-c", "import time; time.sleep(1)"], b"", 0.01)
