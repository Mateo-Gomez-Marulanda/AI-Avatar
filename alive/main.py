"""Arranque del avatar: CLI configurable, voz, overlay y bucle GTK."""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from alive.application.apps import AppLauncher  # noqa: E402
from alive.application.audio import VoiceService, missing_voice_commands  # noqa: E402
from alive.application.commands import ShellCommandExecutor  # noqa: E402
from alive.application.mediator import Mediator  # noqa: E402
from alive.application.music import MusicMonitor  # noqa: E402
from alive.domain.animation import AnimationEngine  # noqa: E402
from alive.domain.config import load_config  # noqa: E402
from alive.domain.geometry import Rect  # noqa: E402
from alive.infrastructure.background import GtkBackgroundRunner  # noqa: E402
from alive.infrastructure.logging import configure_logging  # noqa: E402
from alive.infrastructure.mpris import PlayerctlMusicSource  # noqa: E402
from alive.infrastructure.providers.cli import CliProvider, SubprocessRunner  # noqa: E402
from alive.ui.approval_dialog import GtkApprover  # noqa: E402
from alive.ui.avatar_view import AvatarView  # noqa: E402
from alive.ui.input_panel import InputPanel  # noqa: E402


def build(config_path: str | Path) -> tuple[Mediator, AvatarView, InputPanel, AnimationEngine]:
    config = load_config(config_path)
    geometry = Gdk.Display.get_default().get_monitor(0).get_geometry()
    monitor = Rect(geometry.x, geometry.y, geometry.width, geometry.height)

    missing_voice = missing_voice_commands(config.voice)
    runner = SubprocessRunner()
    ai_runner = SubprocessRunner(os.path.expanduser(config.provider.workdir) or None)
    ai = CliProvider(config.provider, ai_runner)
    voice = VoiceService(config.voice, runner)
    launcher = AppLauncher(config.apps, lambda argv: subprocess.Popen(argv))
    engine = AnimationEngine(
        config.idle_states,
        config.drag_snap_ms,
        config.bubble_ms_per_char,
        config.idle_switch_s,
    )
    view = AvatarView(config, monitor)

    def on_text_submit(text: str) -> None:
        mediator.submit_text(text)

    def on_ptt_start() -> None:
        mediator.ptt_start()

    def on_ptt_hold(seconds: float) -> None:
        mediator.ptt_end(seconds)

    def on_toggle_quiet() -> None:
        mediator.toggle_no_molestar()

    panel = InputPanel(
        on_text_submit,
        on_ptt_hold,
        on_ptt_start=on_ptt_start,
        on_toggle_quiet=on_toggle_quiet,
        voice_enabled=config.voice.enabled and not missing_voice,
        on_quit=Gtk.main_quit,
    )
    if missing_voice:
        view.show_bubble(
            "Voz no disponible: faltan herramientas", config.bubble_ms_per_char
        )

    executor = ShellCommandExecutor(
        config.commands.timeout_s,
        max_output_bytes=config.commands.max_output_bytes,
        workdir=config.commands.working_dir,
    )
    approver = GtkApprover(
        timeout_s=config.commands.approval_timeout_s,
        share_output=config.commands.share_output_with_model,
        parent=view.window,
    )
    mediator = Mediator(
        engine=engine,
        view=view,
        ai=ai,
        voice=voice,
        launcher=launcher,
        config=config,
        clock=time.monotonic,
        background=GtkBackgroundRunner(),
        approver=approver,
        executor=executor,
        on_status=panel.set_busy,
    )
    view.set_callbacks(
        mediator.on_drag_start,
        mediator.on_drag_end,
        lambda: (panel.show(), panel.present()),
    )
    if config.music.enabled:
        source = PlayerctlMusicSource(config.music.players)
        monitor = MusicMonitor(source, engine, time.monotonic)
        # MusicMonitor solo reenvía cambios: sondear no reinicia el idle del motor.
        GLib.timeout_add(
            max(250, int(config.music.poll_s * 1000)),
            lambda: (monitor.poll(), True)[1],
        )
    return mediator, view, panel, engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Avatar 2D para Linux/KDE")
    parser.add_argument("--config", default="config.toml", help="ruta al config.toml")
    args = parser.parse_args()
    configure_logging()

    _, view, _, engine = build(args.config)
    view.show_all()


    def tick():
        view.render(engine.tick(time.monotonic()))
        return True

    GLib.timeout_add(33, tick)
    Gtk.main()


if __name__ == "__main__":
    main()
