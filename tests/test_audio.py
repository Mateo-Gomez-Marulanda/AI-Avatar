import struct
from alive.application.audio import VoiceService, rms_envelope
from support import FakeBackground, FakeTimer

def test_rms_envelope_silence_and_tone():
    assert rms_envelope(b"\x00" * 4096, frame_samples=1024) == [0.0, 0.0]
    loud = struct.pack("<h", 16000) * 1024 + b"\x00" * 2048
    vals = rms_envelope(loud, frame_samples=1024)
    assert vals[0] > 0.3 and vals[1] == 0.0

def test_record_replaces_duration_placeholder():
    calls = []
    cfg = type("C", (), {"capture_command": ["ffmpeg", "-t", "{duration}", "-i", "x"],
                         "sample_rate": 16000, "frame_samples": 1024})()
    v = VoiceService(cfg, lambda argv, stdin, timeout_s: (calls.append(argv), b"pcm")[1])
    assert v.record(2.5) == b"pcm" and calls[0][2] == "2.5"


def test_empty_tts_completes_without_background_jobs():
    calls, ready, done = [], [], []
    cfg = type("C", (), {"enabled": True, "tts_command": [], "play_command": [],
                         "sample_rate": 16000, "frame_samples": 1024,
                         "timeout_s": 5.0})()
    def runner(argv, stdin, timeout_s):
        calls.append(argv)
        return b""
    bg, timer = FakeBackground(), FakeTimer()
    v = VoiceService(cfg, runner)
    v.speak_async("hola", on_level=lambda *a: None, on_ready=ready.append,
                  on_done=done.append, background=bg, timer=timer)
    assert calls == [] and ready == [0.0] and done == [None]
    assert bg.jobs == [] and timer.pending == []


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
    done = []
    v.record(1.0)
    v.transcribe(b"pcm")
    v.speak_async("hola", on_level=lambda *a: None, on_ready=lambda d: None,
                  on_done=done.append, background=FakeBackground(), timer=FakeTimer())
    assert done == [None]

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


def test_voice_service_has_no_blocking_speak():
    assert not hasattr(VoiceService, "speak")


def test_binary_runner_preserves_raw_pcm_bytes():
    import sys
    from alive.infrastructure.voice_runner import BinarySubprocessRunner
    code = "import sys; sys.stdout.buffer.write(bytes([0, 255, 128, 10]))"
    out = BinarySubprocessRunner().run([sys.executable, "-c", code], b"", 5.0)
    assert out == bytes([0, 255, 128, 10])


def test_synthesize_keeps_raw_pcm_from_runner():
    pcm = bytes([0, 255, 128, 10])
    cfg = type("C", (), {"enabled": True, "tts_command": ["tts"],
                         "timeout_s": 5.0})()
    v = VoiceService(cfg, lambda argv, stdin, t: pcm)
    assert v.synthesize("hola") == pcm


def test_speak_async_defers_synthesis_and_play_to_background():
    pcm = bytes([0, 255, 128, 10]) * 1024
    cfg = type("C", (), {"enabled": True, "tts_command": ["tts"],
                         "play_command": ["paplay"], "sample_rate": 16000,
                         "frame_samples": 1024, "timeout_s": 5.0})()
    calls = []
    def runner(argv, stdin, t):
        calls.append(argv[0])
        return pcm if argv[0] == "tts" else b""
    bg, timer, levels, done = FakeBackground(), FakeTimer(), [], []
    v = VoiceService(cfg, runner, clock=lambda: 1.0)
    v.speak_async("hola", on_level=lambda l, n: levels.append((l, n)),
                  on_ready=lambda d: calls.append(("ready", d)),
                  on_done=lambda e: done.append(e),
                  background=bg, timer=timer)

    assert calls == []
    bg.flush()
    assert calls[0] == "tts" and calls[1] == ("ready", 0.128)
    assert len(bg.jobs) == 1 and len(timer.pending) == 2
    assert levels == [] and done == []


def test_speak_async_delivers_levels_and_finishes_after_playback():
    pcm = bytes([0, 255, 128, 10]) * 1024
    cfg = type("C", (), {"enabled": True, "tts_command": ["tts"],
                         "play_command": ["paplay"], "sample_rate": 16000,
                         "frame_samples": 1024, "timeout_s": 5.0})()
    bg, timer, levels, done = FakeBackground(), FakeTimer(), [], []
    v = VoiceService(cfg, lambda argv, stdin, t: pcm, clock=lambda: 2.0)
    v.speak_async("hola", on_level=lambda l, n: levels.append((l, n)),
                  on_ready=lambda d: None, on_done=done.append,
                  background=bg, timer=timer)
    bg.flush()
    timer.fire()
    assert levels and done == []
    bg.flush()
    assert done == [None]
    assert timer.cancelled
    assert levels[-1][0] == 0.0


def test_stale_synthesis_callback_is_discarded():
    pcm = struct.pack("<h", 16000) * 1024
    cfg = type("C", (), {"enabled": True, "tts_command": ["tts"],
                         "play_command": ["paplay"], "sample_rate": 16000,
                         "frame_samples": 1024, "timeout_s": 5.0})()
    bg, timer = FakeBackground(), FakeTimer()
    old = {"ready": [], "levels": [], "done": []}
    new = {"ready": [], "levels": [], "done": []}
    v = VoiceService(cfg, lambda argv, stdin, t: pcm, clock=lambda: 1.0)
    for text, sink in (("uno", old), ("dos", new)):
        v.speak_async(
            text,
            on_level=lambda level, now, sink=sink: sink["levels"].append(level),
            on_ready=lambda duration, sink=sink: sink["ready"].append(duration),
            on_done=lambda error, sink=sink: sink["done"].append(error),
            background=bg, timer=timer,
        )
    bg.flush()  # sintetiza "dos"
    timer.fire_all()
    bg.flush()  # llega tarde la síntesis de "uno"
    assert old == {"ready": [], "levels": [], "done": []}
    bg.flush()  # reproducir "dos"
    assert new["done"] == [None] and new["ready"] == [0.064] and new["levels"]


def test_speak_async_reports_synthesis_error_once():
    cfg = type("C", (), {"enabled": True, "tts_command": ["tts"],
                         "play_command": ["paplay"], "sample_rate": 16000,
                         "frame_samples": 1024, "timeout_s": 5.0})()
    def boom(argv, stdin, t):
        raise RuntimeError("tts roto")
    bg, timer, done = FakeBackground(), FakeTimer(), []
    v = VoiceService(cfg, boom, clock=lambda: 0.0)
    v.speak_async("hola", on_level=lambda *a: None, on_ready=lambda d: None,
                  on_done=done.append, background=bg, timer=timer)
    bg.flush()
    assert len(done) == 1 and "tts roto" in done[0]
    assert bg.jobs == [] and timer.pending == []
