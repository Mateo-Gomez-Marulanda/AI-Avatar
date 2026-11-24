from pathlib import Path

import pytest

from alive.domain.config import ConfigError, load_config

EXAMPLE = Path(__file__).parent.parent / "config.toml.example"


def test_example_uses_opencode_with_agent_and_archived():
    cfg = load_config(EXAMPLE)
    assert cfg.provider.command[:5] == ["opencode", "run", "--format", "json", "--agent"]
    assert cfg.provider.command[-1] == "--archived"
    assert cfg.provider.output_format == "json"
    assert cfg.provider.workdir == "~"


def test_example_has_new_sections():
    cfg = load_config(EXAMPLE)
    assert cfg.commands.enabled is True
    assert cfg.conversation.max_chars == 6000
    assert cfg.music.players == ["spotify"]
    assert cfg.idle_states == ("sentado", "parado")


def test_config_has_no_single_idle_state():
    cfg = load_config(EXAMPLE)
    assert not hasattr(cfg, "idle_state")
    assert cfg.idle_states == ("sentado", "parado")


def test_rejects_idle_states_table(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('''\
[provider]
command = ["claude", "-p"]
output_format = "text"

[apps]
firefox = "firefox --new-window"

[commands]
enabled = false
max_per_turn = 2
share_output_with_model = false

[conversation]
max_chars = 1234

[music]
enabled = false
players = []

[idle_states]
''')
    # [idle_states] no es válido: idle_states es una clave raíz, no una tabla.
    with pytest.raises(ConfigError):
        load_config(p)


def test_parses_root_idle_and_music_values(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('''\
idle_states = ["parado"]
idle_switch_s = 5.0
[provider]
command = ["x"]
[apps]
[commands]
max_per_turn = 2
share_output_with_model = false
[music]
players = []
''')
    c = load_config(p)
    assert c.idle_states == ("parado",) and c.idle_switch_s == 5.0
    assert c.commands.max_per_turn == 2 and c.commands.share_output_with_model is False
    assert c.music.players == []


def test_rejects_old_session_keys(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[provider]\ncommand = ["x"]\nsession_mode = "oneshot"\n')
    with pytest.raises(ConfigError):
        load_config(p)


def test_rejects_bad_output_format(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[provider]\ncommand = ["x"]\noutput_format = "yaml"\n')
    with pytest.raises(ConfigError):
        load_config(p)


def test_rejects_unknown_idle_state(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('idle_states = ["bailando"]\n[provider]\ncommand = ["x"]\n')
    with pytest.raises(ConfigError):
        load_config(p)
