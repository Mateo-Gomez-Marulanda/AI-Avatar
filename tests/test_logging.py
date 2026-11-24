import logging as std_logging

import alive.infrastructure.logging as logmod


def _configure_in_isolation(tmp_path, monkeypatch, **kwargs):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(logmod, "_configured", False)
    root = std_logging.getLogger()
    previous = (list(root.handlers), root.level)
    root.handlers = []
    path = logmod.configure_logging(**kwargs)
    return path, root, previous


def _restore(root, previous):
    for handler in root.handlers:
        handler.close()
    root.handlers = previous[0]
    root.setLevel(previous[1])


def test_configure_logging_creates_private_file(tmp_path, monkeypatch):
    path, root, previous = _configure_in_isolation(tmp_path, monkeypatch)
    try:
        assert path == tmp_path / "alive" / "alive.log"
        assert path.exists()
        assert (path.stat().st_mode & 0o777) == 0o600
    finally:
        _restore(root, previous)


def test_rotated_log_files_keep_private_permissions(tmp_path, monkeypatch):
    path, root, previous = _configure_in_isolation(
        tmp_path, monkeypatch, max_bytes=200
    )
    try:
        logger = std_logging.getLogger("alive.test.rotacion")
        for i in range(30):
            logger.info("comando propuesto %d %s", i, "x" * 80)
        files = sorted(path.parent.glob("alive.log*"))
        assert len(files) >= 2
        assert all((f.stat().st_mode & 0o777) == 0o600 for f in files)
    finally:
        _restore(root, previous)
