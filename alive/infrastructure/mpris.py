"""Consulta de reproducción MPRIS mediante `playerctl`."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

logger = logging.getLogger(__name__)

Runner = Callable[[list[str]], str]

_TIMEOUT_S = 2.0


def _playerctl(argv: list[str]) -> str:
    result = subprocess.run(
        argv, capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"playerctl terminó con código {result.returncode}: {' '.join(argv)}"
        )
    return result.stdout


class PlayerctlMusicSource:
    """Indica si algún reproductor configurado está reproduciendo."""

    def __init__(self, players: list[str], runner: Runner | None = None) -> None:
        self.players = list(players)
        self._runner = runner if runner is not None else _playerctl
        self._warned = False

    def _warn_once(self, message: str) -> None:
        if self._warned:
            return
        self._warned = True
        logger.warning(message)

    def is_playing(self) -> bool:
        try:
            listed = self._runner(["playerctl", "-l"])
        except FileNotFoundError:
            self._warn_once("playerctl no está instalado; música desactivada")
            return False
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            self._warn_once(f"no se pudo consultar playerctl: {exc}")
            return False

        names = [line.strip() for line in listed.splitlines() if line.strip()]
        if self.players:
            names = [
                name
                for name in names
                if any(
                    name == player or name.startswith(f"{player}.")
                    for player in self.players
                )
            ]

        for name in names:
            try:
                status = self._runner(["playerctl", "-p", name, "status"])
            except (OSError, RuntimeError, subprocess.SubprocessError):
                continue  # Un reproductor que falla no impide consultar los demás.
            if any(line.strip() == "Playing" for line in status.splitlines()):
                return True
        return False
