def test_domain_imports():
    from alive.domain.config import Config, Zone
    from alive.domain.conversation import Conversation
    from alive.domain.actions import parse_action, AppAction, CommandAction
    from alive.domain.animation import AnimationEngine
    from alive.domain.geometry import Rect
    from alive.domain.contracts import (
        AiReply, ProviderError, CommandRunner, CommandExecutor, Approver, MusicSource,
    )


def test_application_imports():
    from alive.application.mediator import Mediator
    from alive.application.apps import AppLauncher
    from alive.application.audio import VoiceService, rms_envelope
    from alive.application.commands import ShellCommandExecutor
    from alive.application.music import MusicMonitor
    from alive.application.prompt import build_prompt, build_system_prompt


def test_infrastructure_imports():
    from alive.infrastructure.providers.cli import CliProvider, SubprocessRunner
    from alive.infrastructure.providers.opencode import parse_opencode_output
    from alive.infrastructure.background import GtkBackgroundRunner
    from alive.infrastructure.mpris import PlayerctlMusicSource
    from alive.infrastructure.logging import configure_logging


def test_ui_and_entrypoint_imports():
    from alive.ui.avatar_view import AvatarView
    from alive.ui.input_panel import InputPanel
    from alive.ui.approval_dialog import GtkApprover, ApprovalDialog
    from alive.main import build, main
