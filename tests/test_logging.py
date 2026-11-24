def test_configure_logging_creates_private_file(tmp_path, monkeypatch):
    import alive.infrastructure.logging as logmod
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setattr(logmod, "_configured", False)
    path = logmod.configure_logging()
    assert path == tmp_path / "alive" / "alive.log"
    assert path.exists()
    assert (path.stat().st_mode & 0o777) == 0o600
