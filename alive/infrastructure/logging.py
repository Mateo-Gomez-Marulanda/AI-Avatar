"""Registro local del avatar: un único archivo rotatorio y privado."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


def configure_logging() -> Path:
    """Configura el registro una vez y devuelve la ruta del archivo."""
    global _configured
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "alive"
    base.mkdir(parents=True, exist_ok=True)
    path = base / "alive.log"
    if not _configured:
        handler = RotatingFileHandler(
            path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
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
