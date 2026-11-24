"""Ejecución de comandos con timeout y salida acotada."""

from __future__ import annotations

import os
import signal
import subprocess
import time

from alive.domain.actions import CommandResult

_MARCA_RECORTA = "… [recortado]"


def _acotar(raw: bytes, limite: int) -> str:
    texto = raw.decode(errors="replace")
    if len(texto) <= limite:
        return texto
    return texto[:limite] + _MARCA_RECORTA


class ShellCommandExecutor:
    """Ejecuta un texto de comando en ``/bin/sh -c`` sin terminal."""

    def __init__(
        self,
        timeout_s: float = 30.0,
        *,
        max_output_bytes: int = 8192,
        workdir: str = "~",
    ) -> None:
        self._timeout_s = timeout_s
        self._max_output_bytes = max_output_bytes
        self._workdir = workdir

    def run(self, command: str) -> CommandResult:
        inicio = time.monotonic()
        process = subprocess.Popen(
            ["/bin/sh", "-c", command],
            cwd=os.path.expanduser(self._workdir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        timed_out = False
        stdout = stderr = b""
        try:
            stdout, stderr = process.communicate(timeout=self._timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        return CommandResult(
            process.returncode,
            _acotar(stdout, self._max_output_bytes),
            _acotar(stderr, self._max_output_bytes),
            timed_out,
            time.monotonic() - inicio,
        )
