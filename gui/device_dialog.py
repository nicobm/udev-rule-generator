"""Diálogo para elegir permitir o ignorar un joystick."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator.devices import Joystick
from udev_rule_generator.hidden import HiddenDevices
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.known import KnownDevices
from udev_rule_generator.privileged import install_rule_files
from udev_rule_generator.rules import RuleAction, RuleSpec, build_rule

from .gi_compat import Adw, GLib, Gtk, Pango


class DeviceDialog(Adw.Dialog):
    """Muestra los datos del dispositivo y permite instalar su regla."""

    def __init__(
        self,
        *,
        device: Joystick,
        host: Host,
        parent: Gtk.Window,
        hidden_store: HiddenDevices,
        known_store: KnownDevices,
        initial_action: RuleAction = RuleAction.ALLOW,
        on_installed: Callable[[str], None],
        on_hidden: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.parent_window = parent
        self.device = device
        self.host = host
        self.hidden_store = hidden_store
        self.known_store = known_store
        self.initial_action = initial_action
        self.on_installed = on_installed
        self.on_hidden = on_hidden
        self._spec: RuleSpec | None = None
        self._busy = False

        self.set_title(tr("Configurar joystick"))
        self.set_content_width(800)
        self.set_content_height(540)
        self._build_ui()
        self._update_rule()

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title=tr("Configurar joystick"),
                subtitle=self.device.display_name,
            )
        )
        toolbar.add_top_bar(header)

        self.banner = Adw.Banner(
            title=tr(
                "En Bluetooth no se puede desautorizar el USB.  La regla de "
                "ignorar deniega el acceso a los nodos de entrada, pero el "
                "dispositivo puede seguir apareciendo para root."
            )
        )
        self.banner.set_revealed(False)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)
        page.add(self._build_action_group())
        page.add(self._build_visibility_group())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.banner)
        content.append(page)
        toolbar.set_content(content)

        bottom = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
        )
        bottom.set_margin_top(10)
        bottom.set_margin_bottom(10)
        bottom.set_margin_start(14)
        bottom.set_margin_end(14)

        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.status_label = Gtk.Label(label="", xalign=0)
        self.status_label.set_hexpand(True)
        self.status_label.set_wrap(True)
        self.status_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.status_label.add_css_class("dim-label")
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        status_row.append(self.status_label)
        status_row.append(self.spinner)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        buttons.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label=tr("Cancelar"))
        cancel.connect("clicked", lambda *_: self.close())
        self.install_button = Gtk.Button(label=tr("Instalar regla"))
        self.install_button.add_css_class("suggested-action")
        self.install_button.connect("clicked", lambda *_: self._install())
        buttons.append(cancel)
        buttons.append(self.install_button)

        bottom.append(status_row)
        bottom.append(buttons)
        toolbar.add_bottom_bar(bottom)
        self.set_child(toolbar)

    def _build_action_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title=tr("Acción"),
            description=tr(
                "Habilitar da acceso al usuario de la sesión y marca el "
                "dispositivo como joystick.  Ignorar lo desautoriza (USB) o "
                "deniega el acceso a sus nodos (Bluetooth)."
            ),
        )
        self.allow_radio = Gtk.CheckButton()
        self.ignore_radio = Gtk.CheckButton()
        self.ignore_radio.set_group(self.allow_radio)
        if self.initial_action is RuleAction.IGNORE:
            self.ignore_radio.set_active(True)
        else:
            self.allow_radio.set_active(True)

        group.add(
            self._radio_row(
                tr("Habilitar (predeterminado)"),
                RuleAction.ALLOW.description,
                self.allow_radio,
            )
        )
        group.add(
            self._radio_row(
                tr("Ignorar"),
                RuleAction.IGNORE.description,
                self.ignore_radio,
            )
        )
        self.allow_radio.connect("toggled", lambda *_: self._on_action_changed())
        self.ignore_radio.connect("toggled", lambda *_: self._on_action_changed())
        return group

    @staticmethod
    def _radio_row(
        title: str, subtitle: str, radio: Gtk.CheckButton
    ) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.set_activatable(True)
        row.add_prefix(radio)
        row.connect("activated", lambda *_: radio.set_active(True))
        return row

    def _build_visibility_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title=tr("Visibilidad"),
            description=tr(
                "Ocultar un dispositivo no borra sus reglas ni cambia permisos.  "
                "Podés recuperarlo desde el menú → Dispositivos ocultos."
            ),
        )
        row = Adw.ActionRow(
            title=tr("Ocultar este dispositivo"),
            subtitle=tr(
                "Se moverá a Dispositivos ocultos y dejará de aparecer en la "
                "lista principal."
            ),
        )
        icon = Gtk.Image(icon_name="view-conceal-symbolic")
        icon.add_css_class("dim-label")
        icon.set_valign(Gtk.Align.CENTER)
        row.add_prefix(icon)

        button = Gtk.Button(label=tr("Ocultar"))
        button.add_css_class("flat")
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", lambda *_: self._hide_device())
        row.add_suffix(button)
        group.add(row)
        return group

    def _hide_device(self) -> None:
        try:
            self.hidden_store.hide(self.device)
        except OSError as exc:
            dialog = Adw.AlertDialog(
                heading=tr("No se pudo ocultar el dispositivo"),
                body=tr(
                    "No se pudo guardar la preferencia: {error}",
                    error=exc,
                ),
            )
            dialog.add_response("close", tr("Cerrar"))
            root = self.get_root()
            dialog.present(root if root is not None else self.parent_window)
            return
        self.on_hidden(tr("Dispositivo oculto: {name}", name=self.device.display_name))
        self.close()

    def _action(self) -> RuleAction:
        return (
            RuleAction.IGNORE
            if self.ignore_radio.get_active()
            else RuleAction.ALLOW
        )

    def _on_action_changed(self) -> None:
        self._update_rule()
        self.banner.set_revealed(
            self.device.is_bluetooth and self._action() is RuleAction.IGNORE
        )

    def _update_rule(self) -> None:
        try:
            self._spec = build_rule(self.device, self._action())
        except ValueError as exc:
            self._spec = None
            self.status_label.set_text(
                tr("No se pudo generar la regla: {error}", error=exc)
            )
            self.install_button.set_sensitive(False)
            return
        self.status_label.set_text(
            tr(
                "Se instalará como /etc/udev/rules.d/{filename}",
                filename=self._spec.filename,
            )
        )
        self.install_button.set_sensitive(not self._busy)

    def _install(self) -> None:
        if self._busy or self._spec is None:
            return
        spec = self._spec
        self._set_busy(True)
        thread = threading.Thread(
            target=self._install_worker,
            args=(spec,),
            name="udev-rule-generator-install",
            daemon=True,
        )
        thread.start()

    def _install_worker(self, spec: RuleSpec) -> None:
        try:
            result = install_rule_files(
                self.host,
                {spec.filename: spec.content},
                trigger=spec.trigger,
            )
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._install_failed, str(exc))
            return
        GLib.idle_add(self._install_succeeded, spec, result)

    def _install_succeeded(self, spec: RuleSpec, _result) -> bool:
        self._set_busy(False)
        try:
            self.known_store.record_rule(self.device, spec)
        except OSError as exc:
            message = tr(
                "Regla instalada: {filename}.  No se pudo guardar en "
                "Dispositivos guardados: {error}",
                filename=spec.filename,
                error=exc,
            )
        else:
            message = tr(
                "Regla instalada: {filename}", filename=spec.filename
            )
        self.on_installed(message)
        self.close()
        return False

    def _install_failed(self, message: str) -> bool:
        self._set_busy(False)
        dialog = Adw.AlertDialog(
            heading=tr("No se pudo instalar la regla"),
            body=message,
        )
        dialog.add_response("close", tr("Cerrar"))
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)
        return False

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.install_button.set_sensitive(not busy and self._spec is not None)
        self.spinner.set_visible(busy)
        if busy:
            self.spinner.start()
            self.status_label.set_text(
                tr("Esperando el diálogo de autenticación de GNOME/polkit…")
            )
            return
        self.spinner.stop()
        if self._spec is not None:
            self.status_label.set_text(
                tr(
                    "Se instalará como /etc/udev/rules.d/{filename}",
                    filename=self._spec.filename,
                )
            )
