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
