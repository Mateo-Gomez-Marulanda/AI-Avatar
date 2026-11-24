"""Ejecución de comandos con timeout y salida acotada."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time

from alive.domain.actions import CommandResult

_MARCA_RECORTA = "… [recortado]"
_CHUNK = 65536
_DRAIN_S = 0.5
_WAIT_S = 1.0


def _acotar(raw: bytes | bytearray, limite: int) -> str:
    """Decodifica como máximo ``limite`` bytes y marca el recorte."""
    if len(raw) <= limite:
        return bytes(raw).decode(errors="replace")
    return bytes(raw[:limite]).decode(errors="replace") + _MARCA_RECORTA


def _matar_grupo(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


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
        deadline = inicio + self._timeout_s
        stdout, stderr, timed_out = self._capturar(process, deadline)
        self._esperar(process)
        return CommandResult(
            process.returncode if process.returncode is not None else -signal.SIGKILL,
            _acotar(stdout, self._max_output_bytes),
            _acotar(stderr, self._max_output_bytes),
            timed_out,
            time.monotonic() - inicio,
        )

    def _capturar(
        self, process: subprocess.Popen, deadline: float
    ) -> tuple[bytearray, bytearray, bool]:
        """Drena ambos flujos con presupuesto de bytes y sin esperas infinitas."""
        pipes = {
            pipe.fileno(): pipe
            for pipe in (process.stdout, process.stderr)
            if pipe is not None
        }
        stdout_fd = process.stdout.fileno() if process.stdout is not None else -1
        stderr_fd = process.stderr.fileno() if process.stderr is not None else -1
        buffers = {fd: bytearray() for fd in pipes}
        limite = max(0, self._max_output_bytes)
        selector = selectors.DefaultSelector()
        for fd in pipes:
            os.set_blocking(fd, False)
            selector.register(fd, selectors.EVENT_READ)
        timed_out = False
        matado = False
        try:
            while selector.get_map():
                restante = deadline - time.monotonic()
                if restante <= 0:
                    if not matado:
                        timed_out = True
                        _matar_grupo(process)
                        matado = True
                        deadline = time.monotonic() + _DRAIN_S
                        continue
                    break
                for key, _ in selector.select(min(0.1, restante)):
                    fd = key.fd
                    try:
                        chunk = os.read(fd, min(_CHUNK, limite + 1 - len(buffers[fd])))
                    except BlockingIOError:
                        continue
                    except OSError:
                        chunk = b""
                    if not chunk:
                        selector.unregister(fd)
                        pipes[fd].close()
                        continue
                    buffers[fd].extend(chunk)
                    if len(buffers[fd]) > limite:
                        _matar_grupo(process)
                        matado = True
                        deadline = time.monotonic() + _DRAIN_S
                        selector.unregister(fd)
                        pipes[fd].close()
        finally:
            for key in list(selector.get_map().values()):
                selector.unregister(key.fd)
            for pipe in pipes.values():
                if not pipe.closed:
                    pipe.close()
            selector.close()
        return buffers.get(stdout_fd, bytearray()), buffers.get(stderr_fd, bytearray()), timed_out

    @staticmethod
    def _esperar(process: subprocess.Popen) -> None:
        try:
            process.wait(timeout=_WAIT_S)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=_WAIT_S)
            except subprocess.TimeoutExpired:
                pass
