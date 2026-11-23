import pytest
from alive.animation import AnimationEngine, STATES

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
