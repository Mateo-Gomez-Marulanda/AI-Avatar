"""Proveedor de IA GENÉRICO basado en un CLI configurable."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable

from alive.domain.config import ProviderConfig
from alive.domain.contracts import AiReply, CommandRunner, ProviderError

Runner = CommandRunner | Callable[[list[str], bytes, float], str]

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class CliProvider:
    def __init__(self, config: ProviderConfig, runner: Runner) -> None:
        self.config = config
        self.runner = runner
        self.session_id: str | None = None
        self._id_re = (
            re.compile(config.session_id_regex, re.MULTILINE)
            if config.session_id_regex
            else None
        )

    def _run(self, argv: list[str], stdin: bytes, timeout_s: float) -> str:
        if callable(self.runner):
            return self.runner(argv, stdin, timeout_s)
        return self.runner.run(argv, stdin, timeout_s)

    def _prompt(self, prompt: str, history: tuple[str, ...]) -> bytes:
        if self.config.prompt_template:
            text = self.config.prompt_template.format(
                history="\n".join(history), text=prompt
            )
        else:
            text = "\n".join((*history, prompt))
        return text.encode("utf-8")

    def ask(self, prompt: str, history: tuple[str, ...]) -> AiReply:
        argv = list(self.config.command)
        if (
            self.config.session_mode == "resume"
            and self.session_id
            and self.config.session_flag
        ):
            argv += [self.config.session_flag, self.session_id]

        out = self._run(argv, self._prompt(prompt, history), self.config.timeout_s)
        clean = _ANSI_RE.sub("", out)

        if self._id_re is not None:
            kept = []
            for line in clean.splitlines():
                match = self._id_re.search(line)
                if match:
                    if self.session_id is None:
                        self.session_id = (
                            match.group(1) if match.groups() else match.group(0)
                        )
                    continue
                kept.append(line)
            clean = "\n".join(kept).strip()

        return AiReply(text=clean.strip())


class SubprocessRunner:
    def run(self, argv: list[str], stdin: bytes, timeout_s: float) -> str:
        try:
            result = subprocess.run(
                argv, input=stdin, capture_output=True, timeout=timeout_s, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"timeout tras {timeout_s}s: {argv[0]}") from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ProviderError(f"fallo al ejecutar {argv[0]}: {exc}") from exc
        return result.stdout.decode("utf-8", errors="replace")
