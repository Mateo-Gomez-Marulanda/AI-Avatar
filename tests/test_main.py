import threading
from pathlib import Path

import alive.main as main
from alive.infrastructure.background import GtkBackgroundRunner


def test_background_runner_delivers_result(monkeypatch):
    monkeypatch.setattr(main.GLib, "idle_add", lambda fn, *args: fn(*args) and False)
    done_event = threading.Event()
    results = []

    def done(value):
        results.append(value)
        done_event.set()

    GtkBackgroundRunner().run(lambda: 42, done)
    assert done_event.wait(2)
    assert results == [42]


def test_music_probe_callback_schedules_background_work(monkeypatch, tmp_path):
    base = (Path(__file__).parent / "fixtures" / "fake_config.toml").read_text()
    config = tmp_path / "config.toml"
    config.write_text(base.replace("[music]\nenabled = false", "[music]\nenabled = true"))

    callbacks = []
    monkeypatch.setattr(
        main.GLib, "timeout_add", lambda ms, fn: (callbacks.append((ms, fn)) or True)
    )

    class SpyMonitor:
        calls = []

        def __init__(self, source, engine, clock):
            pass

        def poll_async(self, background):
            SpyMonitor.calls.append("async")
            return True

        def poll(self):
            SpyMonitor.calls.append("sync")
            return False

    monkeypatch.setattr(main, "MusicMonitor", SpyMonitor)
    monkeypatch.setattr(main, "PlayerctlMusicSource", lambda players: object())

    main.build(config)

    assert callbacks
    _, callback = callbacks[0]
    assert callback() is True
    assert SpyMonitor.calls == ["async"]
