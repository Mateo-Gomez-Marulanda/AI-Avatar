from alive.application.mediator import Mediator
from alive.domain.config import Config, ProviderConfig, VoiceConfig
from alive.domain.orders import Order

class Inline:
    def run(self, work, done): done(work())

def make(**kw):
    cfg = Config(provider=ProviderConfig(command=["x"]),
                 apps={"firefox": "firefox"}, zones={}, voice=VoiceConfig([], [], [], []))
    base = dict(engine=kw.get("engine"), view=kw.get("view"), ai=kw.get("ai"),
                voice=kw.get("voice"), launcher=kw.get("launcher"),
                config=cfg, clock=lambda: 0.0, background=Inline())
    return Mediator(**base)

def test_answer_shows_bubble_and_speaks():
    from alive.domain.animation import AnimationEngine
    class V:
        def __init__(self): self.bubble=None
        def show_bubble(self, text, ms): self.bubble=text
        def hide_bubble(self): pass
        def render(self, frame): pass
        def set_click_through(self, e): pass
        def snap_to(self, z): pass
    class A:
        def ask(self, prompt): from alive.domain.contracts import AiReply; return AiReply("Hola\nABRIR=firefox")
    class Voice:
        def record(self, s): return b""
        def transcribe(self, a): return ""
        def speak(self, text, on_level): self.spoken=text
    class L:
        def __init__(self): self.opened=[]
        def open(self, alias): self.opened.append(alias); return True
    e, v, voice, l = AnimationEngine(), V(), Voice(), L()
    m = make(engine=e, view=v, ai=A(), voice=voice, launcher=l)
    m.submit_text("¿qué tal?")
    assert v.bubble == "Hola" and voice.spoken == "Hola" and l.opened == ["firefox"]
    assert e.state == "hablando"

def test_empty_ptt_does_not_call_ai():
    from alive.domain.animation import AnimationEngine
    class Voice:
        def record(self, s): return b"xyz"
        def transcribe(self, a): return "   "
        def speak(self, text, on_level): raise AssertionError("no debe hablar")
    class AI:
        def ask(self, p): raise AssertionError("no debe llamar al modelo")
    class V:
        def show_bubble(self, text, ms): self.bubble = text
    e = AnimationEngine()
    m = make(engine=e, view=V(), ai=AI(), voice=Voice(), launcher=object())
    m.ptt_start(); m.ptt_end(0.5)
    assert e.state == "sentado"

def test_provider_error_returns_to_idle_with_message():
    from alive.domain.animation import AnimationEngine
    from alive.domain.contracts import ProviderError
    class V:
        def show_bubble(self, text, ms): self.bubble=text
        def hide_bubble(self): pass
        def render(self, f): pass
        def set_click_through(self, e): pass
        def snap_to(self, z): pass
    class AI:
        def ask(self, p): raise ProviderError("timeout")
    class Voice:
        def record(self,s): return b""
        def transcribe(self,a): return ""
        def speak(self,t,on_level): pass
    e, v = AnimationEngine(), V()
    m = make(engine=e, view=v, ai=AI(), voice=Voice(), launcher=object())
    m.submit_text("pregunta")
    assert e.state == "sentado" and "No pude responder" in v.bubble

def test_unknown_app_order_is_ignored():
    from alive.domain.animation import AnimationEngine
    e = AnimationEngine(); m = make(engine=e, view=object(), ai=object(), voice=object(),
                                    launcher=object())
    assert m.apply_order(Order("ABRIR", "inexistente")) is False

class EngineSpy:
    def __init__(self): self.ended = False
    def end_drag(self, now): self.ended = True

class ViewSpy:
    def snap_to(self, zone):
        raise AssertionError("snap_to no debe cancelar la animación")

def test_drag_end_does_not_cancel_snap():
    engine, view = EngineSpy(), ViewSpy()
    m = make(engine=engine, view=view, ai=object(), voice=object(), launcher=object())
    m.on_drag_end("barra")
    assert engine.ended

def test_failed_transcription_shows_bubble():
    from alive.domain.animation import AnimationEngine
    from alive.domain.contracts import ProviderError
    class Voice:
        def record(self, s): return b"pcm"
        def transcribe(self, a): raise ProviderError("sin motor")
        def speak(self, t, on_level): pass
    class V:
        def __init__(self): self.bubble = None
        def show_bubble(self, text, ms): self.bubble = text
    engine = AnimationEngine()
    m = make(engine=engine, view=V(), ai=object(), voice=Voice(), launcher=object())
    m.ptt_end(0.5)
    assert m.view.bubble == "No pude escuchar"

def test_missing_tts_does_not_break_text_reply():
    from alive.domain.animation import AnimationEngine
    from alive.domain.contracts import AiReply, ProviderError
    class V:
        def __init__(self): self.bubble = None
        def show_bubble(self, text, ms): self.bubble = text
        def hide_bubble(self): pass
        def render(self, f): pass
        def set_click_through(self, e): pass
        def snap_to(self, z): pass
    class A:
        def ask(self, prompt): return AiReply("Hola sin voz")
    class Voice:
        def record(self, s): return b""
        def transcribe(self, a): return ""
        def speak(self, text, on_level): raise ProviderError("sin tts")
    engine, v = AnimationEngine(), V()
    m = make(engine=engine, view=v, ai=A(), voice=Voice(), launcher=object())
    m.submit_text("¿qué tal?")
    assert v.bubble == "Hola sin voz" and engine.state == "hablando"
