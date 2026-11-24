"""Proveedor de IA GENÉRICO basado en un CLI configurable."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from alive.domain.config import ProviderConfig
from alive.domain.contracts import AiReply, CommandRunner, ProviderError
from alive.infrastructure.providers.opencode import parse_opencode_output

Runner = CommandRunner | Callable[[list[str], bytes, float], str]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# `opencode run` imprime una cabecera de estado: "> <agente> · <modelo>".
# El patrón es estricto para no confundirlo con una cita markdown ordinaria.
_STATUS_HEADER_RE = re.compile(r"^> \S+ · \S+$")


def _drop_opencode_header(text: str) -> str:
    """Quita solo la cabecera de estado de `opencode run`, nunca una cita."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if _STATUS_HEADER_RE.match(line):
            del lines[index]
        break
    return "\n".join(lines)


class CliProvider:
    def __init__(self, config: ProviderConfig, runner: Runner) -> None:
        self.config = config
        self.runner = runner

    def _run(self, argv: list[str], stdin: bytes, timeout_s: float) -> str:
        if callable(self.runner):
            return self.runner(argv, stdin, timeout_s)
        return self.runner.run(argv, stdin, timeout_s)

    def ask(self, prompt: str) -> AiReply:
        argv = list(self.config.command)
        out = self._run(argv, prompt.encode("utf-8"), self.config.timeout_s)
        if self.config.output_format == "json":
            parsed = parse_opencode_output(out)
            return AiReply(parsed.text.strip(), parsed.session_id)

        clean = _ANSI_RE.sub("", out)
        if argv and Path(argv[0]).name == "opencode":
            clean = _drop_opencode_header(clean)
        return AiReply(text=clean.strip())


class SubprocessRunner:
    def __init__(self, cwd: str | None = None) -> None:
        self.cwd = os.path.expanduser(cwd) if cwd else None

    def run(self, argv: list[str], stdin: bytes, timeout_s: float) -> str:
        try:
            result = subprocess.run(
                argv,
                input=stdin,
                capture_output=True,
                timeout=timeout_s,
                check=False,
                cwd=self.cwd,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(
                f"Tiempo de espera agotado tras {timeout_s}s: {argv[0]}"
            ) from exc
        except OSError as exc:
            raise ProviderError(f"fallo al ejecutar {argv[0]}: {exc}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or b"").decode("utf-8", errors="replace")
            raise ProviderError(
                f"{argv[0]} falló con código {result.returncode}: {stderr[:500]}"
            )
        return result.stdout.decode("utf-8", errors="replace")
