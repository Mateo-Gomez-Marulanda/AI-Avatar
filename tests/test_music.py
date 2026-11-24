from alive.application.music import MusicMonitor
from alive.infrastructure.mpris import PlayerctlMusicSource


class Engine:
    def __init__(self): self.calls = []
    def set_music(self, active, now): self.calls.append((active, now))


def runner_factory(listed, statuses):
    def runner(argv):
        if argv[:2] == ["playerctl", "-l"]:
            return listed
        name = argv[argv.index("-p") + 1]
        return statuses.get(name, "Paused")
    return runner


def test_playing_configured_player_is_active():
    src = PlayerctlMusicSource(["spotify"], runner_factory("spotify\nbrave.instance1\n", {"spotify": "Playing"}))
    assert src.is_playing() is True


def test_paused_player_is_not_active():
    src = PlayerctlMusicSource(["spotify"], runner_factory("spotify\n", {"spotify": "Paused"}))
    assert src.is_playing() is False


def test_player_name_matches_instance_suffix():
    src = PlayerctlMusicSource(["brave"], runner_factory("brave.instance1\n", {"brave.instance1": "Playing"}))
    assert src.is_playing() is True


def test_empty_players_means_any_player():
    src = PlayerctlMusicSource([], runner_factory("vlc\n", {"vlc": "Playing"}))
    assert src.is_playing() is True


def test_missing_playerctl_is_inactive():
    def runner(argv): raise FileNotFoundError("playerctl")
    assert PlayerctlMusicSource(["spotify"], runner).is_playing() is False


def test_monitor_forwards_state_to_engine():
    class Source:
        def is_playing(self): return True
    engine = Engine()
    monitor = MusicMonitor(Source(), engine, lambda: 7.0)
    assert monitor.poll() is True
    assert engine.calls == [(True, 7.0)]


def test_monitor_does_not_forward_unchanged_state():
    class Source:
        def is_playing(self): return True
    engine = Engine()
    monitor = MusicMonitor(Source(), engine, lambda: 7.0)
    assert monitor.poll() is True
    assert monitor.poll() is True
    assert engine.calls == [(True, 7.0)]


class FakeBackground:
    """Captura el trabajo y el callback sin ejecutarlos: imita al hilo GTK."""

    def __init__(self):
        self.jobs = []

    def run(self, work, done):
        self.jobs.append((work, done))


def test_poll_async_does_not_query_the_source_on_the_calling_thread():
    consulted = []

    class Source:
        def is_playing(self):
            consulted.append(True)
            return True

    engine = Engine()
    monitor = MusicMonitor(Source(), engine, lambda: 7.0)
    background = FakeBackground()

    assert monitor.poll_async(background) is True

    assert consulted == []
    assert engine.calls == []
    assert len(background.jobs) == 1


def test_poll_async_applies_the_result_when_the_callback_runs():
    class Source:
        def is_playing(self): return True

    engine = Engine()
    monitor = MusicMonitor(Source(), engine, lambda: 7.0)
    background = FakeBackground()
    monitor.poll_async(background)

    work, done = background.jobs[0]
    assert work() is True
    done(True)

    assert engine.calls == [(True, 7.0)]


def test_poll_async_skips_a_second_probe_while_one_is_pending():
    class Source:
        def is_playing(self): return False

    monitor = MusicMonitor(Source(), Engine(), lambda: 7.0)
    background = FakeBackground()

    assert monitor.poll_async(background) is True
    assert monitor.poll_async(background) is False
    assert len(background.jobs) == 1

    _, done = background.jobs[0]
    done(False)
    assert monitor.poll_async(background) is True
    assert len(background.jobs) == 2


def test_poll_async_degrades_source_errors_and_releases_the_pending_probe():
    class Source:
        def is_playing(self): raise RuntimeError("playerctl roto")

    engine = Engine()
    monitor = MusicMonitor(Source(), engine, lambda: 7.0)
    background = FakeBackground()
    monitor.poll_async(background)

    work, done = background.jobs[0]
    assert work() is False
    done(False)

    assert engine.calls == [(False, 7.0)]
    assert monitor.poll_async(background) is True
