"""Lanzamiento de aplicaciones permitidas por la whitelist."""

from __future__ import annotations

import shlex
from collections.abc import Callable


class AppLauncher:
    def __init__(
        self,
        whitelist: dict[str, str],
        spawn: Callable[[list[str]], None],
    ) -> None:
        self.whitelist = whitelist
        self.spawn = spawn

    def open(self, alias: str) -> bool:
        command = self.whitelist.get(alias)
        if not command:
            return False
        argv = shlex.split(command)
        if not argv:
            return False
        self.spawn(argv)
        return True
