from alive.mediator import Mediator
from alive.domain.config import Config, ProviderConfig, VoiceConfig
from alive.domain.orders import Order

class Inline:
    def run(self, work, done): done(work())

def make(**kw):
    cfg = Config(provider=ProviderConfig(command=["x"], session_mode="oneshot"),
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
        def ask(self, prompt, history): from alive.providers.base import AiReply; return AiReply("Hola\nABRIR=firefox")
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
        def ask(self, p, h): raise AssertionError("no debe llamar al modelo")
    e = AnimationEngine()
    m = make(engine=e, view=object(), ai=AI(), voice=Voice(), launcher=object())
    m.ptt_start(); m.ptt_end(0.5)
    assert e.state == "sentado"

def test_provider_error_returns_to_idle_with_message():
    from alive.domain.animation import AnimationEngine
    from alive.providers.base import ProviderError
    class V:
        def show_bubble(self, text, ms): self.bubble=text
        def hide_bubble(self): pass
        def render(self, f): pass
        def set_click_through(self, e): pass
        def snap_to(self, z): pass
    class AI:
        def ask(self, p, h): raise ProviderError("timeout")
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
