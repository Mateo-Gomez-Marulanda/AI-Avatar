import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from alive.domain.actions import CommandRequest
from alive.ui.approval_dialog import ApprovalDialog, GtkApprover

REQUEST = CommandRequest("printf hola", "Imprime hola", "El usuario lo pidió", "/tmp")


def make(**kw):
    decisions = []
    dialog = ApprovalDialog(REQUEST, on_decision=decisions.append, **kw)
    return dialog, decisions


def test_shows_exact_command_and_explanations():
    dialog, _ = make()
    text = dialog.command_view.get_buffer().get_text(
        dialog.command_view.get_buffer().get_start_iter(),
        dialog.command_view.get_buffer().get_end_iter(), False,
    )
    assert text == "printf hola"
    assert dialog.window.get_title() == "Alive quiere ejecutar un comando"
    assert dialog.what_label.get_text() == "Qué hace: Imprime hola"
    assert dialog.why_label.get_text() == "Por qué: El usuario lo pidió"
    dialog._decide(False)


def test_ok_button_approves_once():
    dialog, decisions = make()
    dialog.window.response(Gtk.ResponseType.OK)
    dialog.window.response(Gtk.ResponseType.OK)
    assert decisions == [True]


def test_cancel_button_denies():
    dialog, decisions = make()
    dialog.window.response(Gtk.ResponseType.CANCEL)
    assert decisions == [False]


def test_default_response_is_cancel():
    dialog, _ = make()
    assert dialog.window.get_default_response() == Gtk.ResponseType.CANCEL
    dialog._decide(False)


def test_timeout_denies():
    dialog, decisions = make(timeout_s=0.01)
    assert dialog._on_timeout() is False
    assert decisions == [False]


def test_is_modal_with_labelled_buttons_and_read_only_command():
    dialog, _ = make()
    assert dialog.window.get_modal() is True
    assert dialog.cancel_button.get_label() == "Cancelar"
    assert dialog.run_button.get_label() == "Ejecutar una vez"
    assert (
        dialog.window.get_widget_for_response(Gtk.ResponseType.CANCEL)
        is dialog.cancel_button
    )
    assert (
        dialog.window.get_widget_for_response(Gtk.ResponseType.OK) is dialog.run_button
    )
    assert dialog.command_view.get_editable() is False
    assert dialog.command_view.get_monospace() is True
    dialog._decide(False)


def test_shows_details_and_warnings():
    dialog, _ = make(share_output=False)
    labels = [
        child.get_text()
        for child in dialog.window.get_content_area().get_children()
        if isinstance(child, Gtk.Label)
    ]
    assert "Revisa el comando. La explicación la generó el modelo." in labels
    assert "Directorio: /tmp" in labels
    assert "Tiempo para decidir: 120 s" in labels
    assert "La salida no se enviará al modelo" in labels
    assert (
        "No hay terminal interactiva: sudo o los comandos que piden "
        "contraseña pueden fallar."
    ) in labels
    dialog._decide(False)


def test_shows_decision_and_execution_time_distinctly():
    dialog, _ = make(timeout_s=120.0, command_timeout_s=30.0)
    labels = [
        child.get_text()
        for child in dialog.window.get_content_area().get_children()
        if isinstance(child, Gtk.Label)
    ]
    assert "Tiempo para decidir: 120 s" in labels
    assert "Tiempo de ejecución: 30 s" in labels
    assert not any(label.startswith("Tiempo límite") for label in labels)
    dialog._decide(False)


def test_shares_output_by_default():
    dialog, _ = make()
    labels = [
        child.get_text()
        for child in dialog.window.get_content_area().get_children()
        if isinstance(child, Gtk.Label)
    ]
    assert "La salida se enviará al modelo" in labels
    dialog._decide(False)


def test_delete_event_denies():
    dialog, decisions = make()
    assert dialog._on_delete(None, None) is True
    assert decisions == [False]


def test_present_schedules_timeout_without_running_dialog():
    dialog, decisions = make(timeout_s=0.05)
    dialog.present()
    assert dialog.window.get_visible() is True
    assert dialog._timeout_id != 0
    dialog._decide(False)
    assert decisions == [False]
    assert dialog._timeout_id == 0


def test_approver_presents_dialog_with_options():
    decisions = []
    approver = GtkApprover(
        timeout_s=0.05, share_output=False, command_timeout_s=30.0
    )
    approver.request(REQUEST, decisions.append)
    assert approver.dialog.timeout_s == 0.05
    assert approver.dialog.command_timeout_s == 30.0
    assert approver.dialog.share_output is False
    assert approver.dialog.window.get_visible() is True
    approver.dialog._decide(False)
    assert decisions == [False]
