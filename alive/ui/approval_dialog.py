"""Diálogo modal para aprobar o rechazar un comando propuesto por el modelo."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from alive.domain.actions import CommandRequest  # noqa: E402


class _ApprovalWindow(Gtk.Dialog):
    """GTK3 no expone la respuesta por defecto: la registramos al fijarla."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._default_response = Gtk.ResponseType.NONE

    def set_default_response(self, response) -> None:
        self._default_response = response
        super().set_default_response(response)

    def get_default_response(self):
        return self._default_response


class ApprovalDialog:
    def __init__(
        self,
        request: CommandRequest,
        *,
        timeout_s: float = 120.0,
        share_output: bool = True,
        parent=None,
        on_decision: Callable[[bool], None] | None = None,
    ) -> None:
        self.request = request
        self.timeout_s = timeout_s
        self.share_output = share_output
        self.parent = parent
        self.on_decision = on_decision
        self.decided = False
        self._timeout_id = 0

        self.window = _ApprovalWindow(title="Alive quiere ejecutar un comando")
        self.window.set_modal(True)
        self.window.set_default_response(Gtk.ResponseType.CANCEL)
        if parent is not None:
            self.window.set_transient_for(parent)

        area = self.window.get_content_area()
        area.set_spacing(8)

        aviso = Gtk.Label(label="Revisa el comando. La explicación la generó el modelo.")
        aviso.set_line_wrap(True)
        aviso.set_xalign(0.0)
        area.add(aviso)

        self.what_label = Gtk.Label(label=f"Qué hace: {request.what}")
        self.what_label.set_line_wrap(True)
        self.what_label.set_xalign(0.0)
        area.add(self.what_label)

        self.why_label = Gtk.Label(label=f"Por qué: {request.why}")
        self.why_label.set_line_wrap(True)
        self.why_label.set_xalign(0.0)
        area.add(self.why_label)

        self.command_view = Gtk.TextView()
        self.command_view.set_editable(False)
        self.command_view.set_monospace(True)
        self.command_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.command_view.get_buffer().set_text(request.command, -1)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(80)
        scroll.add(self.command_view)
        area.add(scroll)

        directorio = Gtk.Label(label=f"Directorio: {request.workdir}")
        directorio.set_line_wrap(True)
        directorio.set_xalign(0.0)
        area.add(directorio)

        limite = Gtk.Label(label=f"Tiempo límite: {timeout_s:g} s")
        limite.set_xalign(0.0)
        area.add(limite)

        salida = (
            "La salida se enviará al modelo"
            if share_output
            else "La salida no se enviará al modelo"
        )
        aviso_salida = Gtk.Label(label=salida)
        aviso_salida.set_line_wrap(True)
        aviso_salida.set_xalign(0.0)
        area.add(aviso_salida)

        aviso_tty = Gtk.Label(
            label=(
                "No hay terminal interactiva: sudo o los comandos que piden "
                "contraseña pueden fallar."
            )
        )
        aviso_tty.set_line_wrap(True)
        aviso_tty.set_xalign(0.0)
        area.add(aviso_tty)

        self.cancel_button = self.window.add_button(
            "Cancelar", Gtk.ResponseType.CANCEL
        )
        self.run_button = self.window.add_button(
            "Ejecutar una vez", Gtk.ResponseType.OK
        )
        self.window.connect("response", self._on_response)
        self.window.connect("delete-event", self._on_delete)

    def present(self) -> None:
        self.window.present()
        self._timeout_id = GLib.timeout_add(
            int(self.timeout_s * 1000), self._on_timeout
        )

    def _on_response(self, dialog, response) -> None:
        self._decide(response == Gtk.ResponseType.OK)

    def _on_delete(self, widget, event) -> bool:
        self._decide(False)
        return True

    def _decide(self, approved: bool) -> None:
        if self.decided:
            return
        self.decided = True
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = 0
        if self.on_decision is not None:
            self.on_decision(approved)
        self.window.destroy()

    def _on_timeout(self) -> bool:
        self._decide(False)
        return False


class GtkApprover:
    """Muestra el diálogo de aprobación sin bloquear el bucle de GTK."""

    def __init__(
        self,
        *,
        timeout_s: float = 120.0,
        share_output: bool = True,
        parent=None,
    ) -> None:
        self.timeout_s = timeout_s
        self.share_output = share_output
        self.parent = parent
        self.dialog: ApprovalDialog | None = None

    def request(
        self, request: CommandRequest, on_decision: Callable[[bool], None]
    ) -> None:
        self.dialog = ApprovalDialog(
            request,
            timeout_s=self.timeout_s,
            share_output=self.share_output,
            parent=self.parent,
            on_decision=on_decision,
        )
        self.dialog.present()
