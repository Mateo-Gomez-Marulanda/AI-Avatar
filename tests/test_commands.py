import sys
import time

from alive.application.commands import ShellCommandExecutor

MARCA = "… [recortado]"


def test_runs_exact_command_and_captures_stdout():
    result = ShellCommandExecutor().run("printf hola")
    assert result.exit_code == 0 and result.stdout == "hola"
    assert result.timed_out is False and result.ok is True


def test_nonzero_exit_is_reported_with_stderr():
    result = ShellCommandExecutor().run("echo boom >&2; exit 3")
    assert result.exit_code == 3 and "boom" in result.stderr and result.ok is False


def test_timeout_kills_the_process_group():
    result = ShellCommandExecutor(timeout_s=0.2).run("sleep 5")
    assert result.timed_out is True
    assert result.duration_s < 3.0


def test_output_is_capped_and_marked():
    command = f"{sys.executable} -c 'print(\"x\" * 500)'"
    result = ShellCommandExecutor(max_output_bytes=10).run(command)
    assert result.stdout.startswith("x" * 10)
    assert "recortado" in result.stdout
    assert len(result.stdout) < 100


def test_uses_configured_working_directory(tmp_path):
    result = ShellCommandExecutor(workdir=str(tmp_path)).run("pwd")
    assert result.stdout.strip() == str(tmp_path)


def test_output_budget_counts_bytes_not_characters():
    command = f"{sys.executable} -c 'print(\"ñ\" * 10, end=\"\")'"
    result = ShellCommandExecutor(max_output_bytes=9).run(command)
    assert result.stdout.count("ñ") == 4
    assert "\ufffd" in result.stdout
    assert result.stdout.endswith(MARCA)


def test_hostile_stdout_is_bounded_and_does_not_stall():
    inicio = time.monotonic()
    result = ShellCommandExecutor(timeout_s=5.0, max_output_bytes=256).run("yes Alive")
    duracion = time.monotonic() - inicio
    assert duracion < 3.0
    assert result.stdout.endswith(MARCA)
    assert len(result.stdout.encode("utf-8")) == 256 + len(MARCA.encode("utf-8"))


def test_hostile_stderr_is_bounded_too():
    result = ShellCommandExecutor(timeout_s=5.0, max_output_bytes=64).run("yes error >&2")
    assert result.stderr.endswith(MARCA)
    assert len(result.stderr.encode("utf-8")) == 64 + len(MARCA.encode("utf-8"))
