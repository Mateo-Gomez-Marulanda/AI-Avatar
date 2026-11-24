from pathlib import Path

from alive.domain.config import ConfigError, load_config

EXAMPLE = Path(__file__).parent.parent / "config.toml.example"


def test_example_provider_is_opencode():
    cfg = load_config(EXAMPLE)
    assert cfg.provider.command == ["opencode", "run"]
    assert cfg.provider.session_mode == "oneshot"


def test_load_config_reads_provider_apps_and_zones(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('''\
[provider]
command = ["claude", "-p"]
session_mode = "resume"
prompt_template = "{history} | {text}"

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
