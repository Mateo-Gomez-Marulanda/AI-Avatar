from alive.domain.actions import CommandResult
from alive.domain.config import Config, ProviderConfig, VoiceConfig
from alive.domain.contracts import AiReply
from alive.domain.geometry import Rect


class InlineBackground:
    def run(self, work, done): done(work())


class FakeBackground:
    """Captura trabajos y callbacks sin ejecutarlos."""

    def __init__(self): self.jobs = []

    def run(self, work, done): self.jobs.append((work, done))

    def flush(self):
        work, done = self.jobs.pop(0)
        done(work())


class FakeTimer:
    """Temporizador de un solo disparo que se acciona manualmente."""

    def __init__(self): self.pending = []; self.cancelled = []

    def after(self, delay_s, callback):
        handle = (delay_s, callback)
        self.pending.append(handle)
        return handle

    def cancel(self, handle):
        if handle in self.pending:
            self.pending.remove(handle)
        self.cancelled.append(handle)

    def fire(self):
        _, callback = self.pending.pop(0)
        callback()

    def fire_all(self):
        while self.pending:
            self.fire()


class DeferredBackground:
    def __init__(self): self.pending = []
    def run(self, work, done): self.pending.append((work, done))
    def flush(self):
        work, done = self.pending.pop(0)
        done(work())


class WorkerCrashBackground:
    """Imita a GtkBackgroundRunner: si work lanza, done nunca se programa."""
    def __init__(self): self.pending = []
    def run(self, work, done):
        self.pending.append((work, done))
        try:
            result = work()
        except Exception:
            return
        done(result)


class FakeView:
    def __init__(self):
        self.bubbles = []
        self._rect = Rect(0, 0, 200, 300)
        self.click_through = False
        self.snapped = []
    def show_bubble(self, text, ms): self.bubbles.append(text)
    def hide_bubble(self): pass
    def render(self, frame): pass
    def set_click_through(self, enabled): self.click_through = enabled
    def current_rect(self): return self._rect
    def current_zone(self): return "flotante"
    def snap_to(self, target):
        self.snapped.append(target)
        if isinstance(target, Rect):
            self._rect = target


class FakeVoice:
    def __init__(self):
        self.spoken = []
        self.records = []
        self.transcribe_error = None
        self.speak_error = None
        self.defer_speech = False
        self._speech_done = None
    def record(self, seconds):
        self.records.append(seconds)
        return b""
    def transcribe(self, audio):
        if self.transcribe_error is not None:
            raise self.transcribe_error
        return ""
    def speak(self, text, on_level):
        if self.speak_error is not None:
            raise self.speak_error
        self.spoken.append(text)
    def speak_async(self, text, *, on_level, on_ready, on_done,
                    background, timer):
        if self.speak_error is not None:
            on_ready(0.0)
            on_done(str(self.speak_error))
            return
        self.spoken.append(text)
        self._speech_done = on_done
        on_ready(0.1)
        if not self.defer_speech:
            self.finish_speech()
    def finish_speech(self, error=None):
        done, self._speech_done = self._speech_done, None
        if done is not None:
            done(error)


class FakeLauncher:
    def __init__(self): self.opened = []
    def open(self, alias): self.opened.append(alias); return True


class FakeApprover:
    def __init__(self, approved=True): self.requests = []; self.approved = approved
    def request(self, request, on_decision):
        self.requests.append(request)
        on_decision(self.approved)


class SilentApprover:
    def __init__(self): self.requests = []; self.decision = None
    def request(self, request, on_decision):
        self.requests.append(request); self.decision = on_decision


class FakeExecutor:
    def __init__(self, result=None):
        self.commands = []
        self.result = result or CommandResult(0, "ok", "", False, 0.01)
    def run(self, command):
        self.commands.append(command)
        return self.result


class FakeAi:
    def __init__(self, replies, exc=None):
        self.replies = list(replies)
        self.exc = exc
        self.prompts = []
    def ask(self, prompt):
        self.prompts.append(prompt)
        if self.exc is not None:
            raise self.exc
        return AiReply(self.replies.pop(0))


class MalformedAi:
    """Proveedor que devuelve una respuesta sin el campo ``text``."""
    def ask(self, prompt):
        return object()


def make_config(**kw):
    base = {
        "provider": ProviderConfig(command=["x"]),
        "apps": {"firefox": "firefox"},
        "zones": {},
        "voice": VoiceConfig(),
    }
    base.update(kw)
    return Config(**base)


def make_mediator(*, ai, config=None, engine=None, view=None, voice=None,
                  launcher=None, approver=None, executor=None, background=None,
                  timer=None, clock=lambda: 0.0, on_status=None):
    from alive.application.mediator import Mediator
    from alive.domain.animation import AnimationEngine
    return Mediator(
        engine=engine or AnimationEngine(),
        view=view or FakeView(),
        ai=ai,
        voice=voice or FakeVoice(),
        launcher=launcher or FakeLauncher(),
        config=config or make_config(),
        clock=clock,
        background=background or InlineBackground(),
        timer=timer or FakeTimer(),
        approver=approver or FakeApprover(),
        executor=executor or FakeExecutor(),
        on_status=on_status,
    )
