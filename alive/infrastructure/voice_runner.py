"""Runner binario para PCM de voz: stdout se devuelve sin decodificar."""

from __future__ import annotations

import os
import subprocess

from alive.domain.contracts import ProviderError


class BinarySubprocessRunner:
    def __init__(self, cwd: str | None = None) -> None:
        self.cwd = os.path.expanduser(cwd) if cwd else None

    def run(self, argv: list[str], stdin: bytes, timeout_s: float) -> bytes:
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
        return result.stdout
