def test_domain_imports():
    from alive.domain.config import Config, Zone
    from alive.domain.orders import parse_orders
    from alive.domain.animation import AnimationEngine
    from alive.domain.geometry import Rect
    from alive.domain.contracts import AiReply, ProviderError, CommandRunner


def test_application_imports():
    from alive.application.mediator import Mediator
    from alive.application.apps import AppLauncher
    from alive.application.audio import VoiceService, rms_envelope


def test_infrastructure_imports():
    from alive.infrastructure.providers.cli import CliProvider, SubprocessRunner
    from alive.infrastructure.background import GtkBackgroundRunner
