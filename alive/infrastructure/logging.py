"""Registro local del avatar: un único archivo rotatorio y privado."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


class _PrivateRotatingFileHandler(RotatingFileHandler):
    """Mantiene 0600 también en el archivo nuevo y en las copias rotadas."""

    def doRollover(self) -> None:
        super().doRollover()
        os.chmod(self.baseFilename, 0o600)
        for indice in range(1, self.backupCount + 1):
            copia = self.rotation_filename(f"{self.baseFilename}.{indice}")
            if os.path.exists(copia):
                os.chmod(copia, 0o600)


def configure_logging(max_bytes: int = 1_000_000) -> Path:
    """Configura el registro una vez y devuelve la ruta del archivo."""
    global _configured
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "alive"
    base.mkdir(parents=True, exist_ok=True)
    path = base / "alive.log"
    if not _configured:
        handler = _PrivateRotatingFileHandler(
            path, maxBytes=max_bytes, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)
        _configured = True
    path.chmod(0o600)
    return path
