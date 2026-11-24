import pytest

from alive.domain.config import ConfigError, load_config


def test_obsolete_session_keys_are_rejected(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('''\
[provider]
command = ["x"]
session_mode = "oneshot"
session_flag = "--session"
session_id_regex = "^SESSION=(.+)$"
prompt_template = "{history} | {text}"

[apps]
[zones]
[voice]
''')
    with pytest.raises(ConfigError) as exc:
        load_config(p)
    message = str(exc.value)
    assert "claves desconocidas" in message
    for key in ("session_mode", "session_flag", "session_id_regex", "prompt_template"):
        assert key in message


def test_load_config_reads_provider_apps_and_zones(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('''\
[provider]
command = ["claude", "-p"]

[apps]
firefox = "firefox --new-window"

[zones.barra]
anchor = "top"
margin = 32

[voice]
stt_command = ["whisper"]
tts_command = ["piper"]
play_command = ["paplay", "--raw"]
capture_command = ["ffmpeg", "-t", "{duration}"]
''')
    c = load_config(p)
    assert c.provider.command == ["claude", "-p"]
    assert c.apps["firefox"] == "firefox --new-window"
    assert c.zones["barra"].anchor == "top" and c.zones["barra"].margin == 32
    assert c.idle_state == "sentado"

def test_load_config_rejects_bad_zone_anchor(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('''\
[provider]
command = ["x"]
[apps]
[zones.raro]
anchor = "techo"
[voice]
''')
    try:
        load_config(p)
    except ConfigError as e:
        assert "anchor" in str(e)
    else:
        raise AssertionError("debió fallar")
