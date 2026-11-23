import struct
from alive.application.audio import VoiceService, rms_envelope

def test_rms_envelope_silence_and_tone():
    assert rms_envelope(b"\x00" * 4096, frame_samples=1024) == [0.0, 0.0]
    loud = struct.pack("<h", 16000) * 1024 + b"\x00" * 2048
    vals = rms_envelope(loud, frame_samples=1024)
    assert vals[0] > 0.3 and vals[1] == 0.0

def test_record_replaces_duration_placeholder():
    calls = []
    cfg = type("C", (), {"capture_command": ["ffmpeg", "-t", "{duration}", "-i", "x"],
                         "sample_rate": 16000, "frame_samples": 1024})()
    v = VoiceService(cfg, lambda argv, stdin, timeout_s: (calls.append(argv), b"pcm")[1], lambda s: None)
    assert v.record(2.5) == b"pcm" and calls[0][2] == "2.5"

def test_speak_feeds_levels_in_order():
    levels, sleeps = [], []
    cfg = type("C", (), {"tts_command": ["tts"], "play_command": ["paplay"],
                         "sample_rate": 16000, "frame_samples": 1024, "timeout_s": 5.0})()
    runner = lambda argv, stdin, timeout_s: b"\x00" * 4096 if argv[0] == "tts" else ""
    v = VoiceService(cfg, runner, lambda s: sleeps.append(s))
    v.speak("hola", lambda level, t: levels.append(level))
    assert levels == [0.0, 0.0]
    assert sleeps == [0.064, 0.064]


def test_empty_tts_is_a_noop():
    calls = []
    cfg = type("C", (), {"tts_command": [], "play_command": [], "sample_rate": 16000,
                         "frame_samples": 1024, "timeout_s": 5.0})()
    def runner(argv, stdin, timeout_s):
        calls.append(argv)
        return b""
    v = VoiceService(cfg, runner, lambda s: None)
    levels = []
    v.speak("hola", lambda level, t: levels.append(level))
    assert calls == [] and levels == []


def test_empty_capture_and_stt_return_empty():
    cfg = type("C", (), {"capture_command": [], "stt_command": [], "timeout_s": 5.0})()
    v = VoiceService(cfg, lambda *a: (_ for _ in ()).throw(AssertionError("no debe ejecutar")))
    assert v.record(1.0) == b""
    assert v.transcribe(b"pcm") == ""


def test_disabled_voice_is_silent_even_with_commands():
    cfg = type("C", (), {"enabled": False, "capture_command": ["rec"], "stt_command": ["stt"],
                         "tts_command": ["tts"], "play_command": ["play"], "sample_rate": 16000,
                         "frame_samples": 1024, "timeout_s": 5.0})()
    v = VoiceService(cfg, lambda *a: (_ for _ in ()).throw(AssertionError("no debe ejecutar")))
    v.record(1.0); v.transcribe(b"pcm"); v.speak("hola", lambda *a: None)

import alive.application.audio as audio

def test_missing_voice_commands_detects_absent_binaries(monkeypatch):
    cfg = type("C", (), {"enabled": True,
                         "capture_command": ["rec"], "stt_command": ["stt"],
                         "tts_command": ["tts"], "play_command": ["play"]})()
    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    assert audio.missing_voice_commands(cfg) == ["captura", "stt", "tts", "play"]

def test_disabled_voice_has_no_missing_commands():
    cfg = type("C", (), {"enabled": False, "capture_command": ["rec"],
                         "stt_command": ["stt"], "tts_command": ["tts"],
                         "play_command": ["play"]})()
    assert audio.missing_voice_commands(cfg) == []
