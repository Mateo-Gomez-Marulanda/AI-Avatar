from alive.domain.actions import CommandResult
from alive.domain.config import Config, ProviderConfig, VoiceConfig
from alive.domain.contracts import AiReply


class InlineBackground:
    def run(self, work, done): done(work())


class DeferredBackground:
    def __init__(self): self.pending = []
    def run(self, work, done): self.pending.append((work, done))
    def flush(self):
        work, done = self.pending.pop(0)
        done(work())


class FakeView:
    def __init__(self): self.bubbles = []
    def show_bubble(self, text, ms): self.bubbles.append(text)
    def hide_bubble(self): pass
    def render(self, frame): pass
    def set_click_through(self, enabled): pass
    def snap_to(self, zone): pass


class FakeVoice:
    def __init__(self): self.spoken = []
    def record(self, seconds): return b""
    def transcribe(self, audio): return ""
    def speak(self, text, on_level): self.spoken.append(text)


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
                  clock=lambda: 0.0, on_status=None):
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
        approver=approver or FakeApprover(),
        executor=executor or FakeExecutor(),
        on_status=on_status,
    )
