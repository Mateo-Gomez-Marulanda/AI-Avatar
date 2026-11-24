import pytest
from alive.domain.animation import AnimationEngine, STATES

def test_unknown_state_is_rejected():
    with pytest.raises(ValueError):
        AnimationEngine().transition_to("buscando", 0.0)

def test_drag_returns_to_idle_after_snap():
    e = AnimationEngine()
    e.begin_drag(1.0)
    assert e.tick(1.0).state == "arrastrado"
    e.end_drag(2.0)
    assert e.tick(2.0).state == "arrastrado"
    assert e.tick(2.30).state == "sentado"
    assert 0.0 <= e.tick(2.10).snap_progress <= 1.0

def test_speaking_mouth_is_deterministic_and_clamped():
    e = AnimationEngine()
    e.speak("hola", 0.0)
    assert e.tick(0.05).state == "hablando"
    assert 0.0 <= e.tick(0.05).mouth <= 1.0
    e.set_audio_level(5.0, 1.0)
    assert e.tick(1.0).mouth <= 1.0
    assert all(s in STATES for s in ("pensando", "no_molestar", "musica"))


def test_idle_rotates_between_configured_states():
    e = AnimationEngine(("sentado", "parado"), idle_switch_s=10.0)
    assert e.tick(0.0).state == "sentado"
    assert e.tick(9.9).state == "sentado"
    assert e.tick(10.0).state == "parado"
    assert e.tick(20.0).state == "sentado"


def test_music_overrides_idle_and_returns_when_it_stops():
    e = AnimationEngine(("sentado", "parado"))
    e.set_music(True, 0.0)
    assert e.tick(0.0).state == "musica"
    e.speak("hola", 1.0)
    assert e.tick(1.0).state == "hablando"
    e.set_music(False, 2.0)
    assert e.tick(2.5).state in ("sentado", "parado")


def test_new_action_states_are_accepted():
    e = AnimationEngine()
    e.transition_to("esperando", 0.0)
    assert e.tick(0.0).state == "esperando"
    e.transition_to("ejecutando", 1.0)
    assert e.tick(1.0).state == "ejecutando"


def test_invalid_idle_states_are_rejected():
    with pytest.raises(ValueError):
        AnimationEngine(("bailando",))


def test_music_stops_when_no_other_state_intervenes():
    e = AnimationEngine(("sentado", "parado"))
    e.set_music(True, 0.0)
    assert e.tick(0.0).state == "musica"
    e.set_music(False, 1.0)
    assert e.tick(1.0).state in ("sentado", "parado")


def test_speech_duration_override_ends_hablando_early():
    e = AnimationEngine()
    e.speak("hola que tal", 0.0)
    e.set_speech_duration(0.05, 0.0)
    assert e.tick(0.06).state == "sentado"


def test_end_speech_stops_hablando_before_text_estimate():
    e = AnimationEngine()
    e.speak("texto muy largo", 0.0)
    e.end_speech(1.0)
    frame = e.tick(1.0)
    assert frame.state == "sentado" and frame.mouth == 0.0


def test_quiet_holds_idle_and_music_and_restores_previous_state():
    e = AnimationEngine()
    e.transition_to("pensando", 0.0)
    e.set_quiet(True, 1.0)
    assert e.tick(2.0).state == "no_molestar"
    e.set_music(True, 3.0)
    assert e.tick(3.0).state == "no_molestar"
    e.set_quiet(False, 4.0)
    assert e.state == "pensando"
    e.idle(5.0)
    e.set_quiet(True, 6.0)
    assert e.tick(30.0).state == "no_molestar"


def test_begin_snap_exposes_progress_and_returns_to_idle():
    e = AnimationEngine(snap_ms=200)
    e.begin_snap(0.0)
    mid = e.tick(0.1)
    assert mid.state == "arrastrado" and mid.snap_progress == 0.5
    end = e.tick(0.2)
    assert end.state == "sentado" and end.snap_progress == 1.0
