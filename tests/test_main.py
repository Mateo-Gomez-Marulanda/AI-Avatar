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


def _voice_config(tmp_path):
    base = (Path(__file__).parent / "fixtures" / "fake_config.toml").read_text()
    config = tmp_path / "config.toml"
    config.write_text(base.replace("[voice]\nenabled = false", "[voice]\nenabled = true"))
    return config


def test_build_wires_binary_voice_runner_and_timer(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "missing_voice_commands", lambda cfg: [])
    mediator, _, _, _ = main.build(_voice_config(tmp_path))
    assert isinstance(mediator.voice.runner, main.BinarySubprocessRunner)
    assert isinstance(mediator.timer, main.GtkLevelTimer)


def test_build_wires_avatar_ptt_only_with_voice(monkeypatch, tmp_path):
    captured = {}
    original = main.AvatarView.set_callbacks

    def spy(self, *args, **kwargs):
        captured.update(kwargs)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(main.AvatarView, "set_callbacks", spy)
    monkeypatch.setattr(main, "missing_voice_commands", lambda cfg: [])
    main.build(_voice_config(tmp_path))
    assert callable(captured["on_ptt_start"]) and callable(captured["on_ptt_end"])


def test_build_does_not_wire_ptt_without_voice(monkeypatch, tmp_path):
    captured = {}
    original = main.AvatarView.set_callbacks

    def spy(self, *args, **kwargs):
        captured.update(kwargs)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(main.AvatarView, "set_callbacks", spy)
    monkeypatch.setattr(main, "missing_voice_commands", lambda cfg: ["stt"])
    main.build(_voice_config(tmp_path))
    assert captured["on_ptt_start"]() is None
    assert captured["on_ptt_end"]() is None
