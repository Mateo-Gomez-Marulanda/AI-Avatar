from alive.domain.config import ProviderConfig
from alive.infrastructure.providers.cli import CliProvider, SubprocessRunner

def test_strips_ansi_from_output():
    out = "\x1b[31mHola\x1b[0m mundo"
    p = CliProvider(ProviderConfig(command=["x"], session_mode="oneshot"),
                    lambda argv, stdin, timeout_s: out)
    assert p.ask("q", ()).text == "Hola mundo"

def test_strips_opencode_status_header():
    out = "\x1b[0m\n> build · big-pickle\nOK\n"
    p = CliProvider(ProviderConfig(command=["opencode", "run"], session_mode="oneshot"),
                    lambda argv, stdin, timeout_s: out)
    assert p.ask("q", ()).text == "OK"


def test_header_filter_only_drops_the_first_line():
    out = "> build · big-pickle\n> cita · importante\nHola\n"
    p = CliProvider(ProviderConfig(command=["opencode", "run"], session_mode="oneshot"),
                    lambda argv, stdin, timeout_s: out)
    assert p.ask("q", ()).text == "> cita · importante\nHola"


def test_header_filter_does_not_affect_other_providers():
    out = "> cita · importante\nHola\n"
    p = CliProvider(ProviderConfig(command=["x"], session_mode="oneshot"),
                    lambda argv, stdin, timeout_s: out)
    assert p.ask("q", ()).text == "> cita · importante\nHola"


def test_session_id_line_is_read_before_the_header_filter():
    cfg = ProviderConfig(command=["opencode", "run"], session_mode="resume",
                         session_flag="--session",
                         session_id_regex=r"^> sesión · (.+)$")
    calls = []

    def runner(argv, stdin, timeout_s):
        calls.append(argv)
        return "> sesión · abc123\nOK\n"

    p = CliProvider(cfg, runner)
    assert p.ask("uno", ()).text == "OK"
    assert p.session_id == "abc123"
    p.ask("dos", ("uno",))
    assert "--session" in calls[1] and "abc123" in calls[1]


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
    from alive.domain.contracts import ProviderError
    with pytest.raises(ProviderError):
        SubprocessRunner().run(["python3", "-c", "import time; time.sleep(1)"], b"", 0.01)
