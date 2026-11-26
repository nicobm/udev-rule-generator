"""Diálogo para elegir permitir o ignorar un joystick."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator.devices import Joystick
from udev_rule_generator.hidden import HiddenDevices
from udev_rule_generator.host import Host
from udev_rule_generator.privileged import install_rule_files
from udev_rule_generator.rules import RuleAction, RuleSpec, build_rule

from .gi_compat import Adw, Gdk, GLib, Gtk


class DeviceDialog(Adw.Dialog):
    """Muestra los datos del dispositivo, la acción y la regla resultante."""

    def __init__(
        self,
        *,
        device: Joystick,
        host: Host,
        parent: Gtk.Window,
        hidden_store: HiddenDevices,
        on_installed: Callable[[str], None],
        on_hidden: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.parent_window = parent
        self.device = device
        self.host = host
        self.hidden_store = hidden_store
        self.on_installed = on_installed
        self.on_hidden = on_hidden
        self._spec: RuleSpec | None = None
        self._busy = False

        self.set_title("Configurar joystick")
        self.set_content_width(720)
        self.set_content_height(780)
        self._build_ui()
        self._update_preview()

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title="Configurar joystick",
                subtitle=self.device.display_name,
            )
        )
        copy_button = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text="Copiar la regla al portapapeles",
        )
        copy_button.add_css_class("flat")
        copy_button.connect("clicked", lambda *_: self._copy_rule())
        header.pack_start(copy_button)

        close_button = Gtk.Button(
            icon_name="window-close-symbolic",
            tooltip_text="Cerrar",
        )
        close_button.add_css_class("flat")
        close_button.connect("clicked", lambda *_: self.close())
        header.pack_end(close_button)
        toolbar.add_top_bar(header)

        self.banner = Adw.Banner(
            title=(
                "En Bluetooth no se puede desautorizar el USB.  La regla de "
                "ignorar deniega el acceso a los nodos de entrada, pero el "
                "dispositivo puede seguir apareciendo para root."
            )
        )
        self.banner.set_revealed(False)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)
        page.add(self._build_info_group())
        page.add(self._build_action_group())
        page.add(self._build_visibility_group())
        page.add(self._build_preview_group())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.banner)
        content.append(page)
        toolbar.set_content(content)

        bottom = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        bottom.set_margin_top(10)
        bottom.set_margin_bottom(10)
        bottom.set_margin_start(14)
        bottom.set_margin_end(14)

        self.status_label = Gtk.Label(label="", xalign=0)
        self.status_label.set_hexpand(True)
        self.status_label.add_css_class("dim-label")
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda *_: self.close())
        self.install_button = Gtk.Button(label="Instalar regla")
        self.install_button.add_css_class("suggested-action")
        self.install_button.connect("clicked", lambda *_: self._install())

        bottom.append(self.status_label)
        bottom.append(self.spinner)
        bottom.append(cancel)
        bottom.append(self.install_button)
        toolbar.add_bottom_bar(bottom)
        self.set_child(toolbar)

    def _build_info_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Dispositivo",
            description="Datos leídos de udev para identificar el mando.",
        )
        group.add(Adw.ActionRow(title="Nombre", subtitle=self.device.display_name))
        hardware = " ".join(
            part for part in (self.device.vendor, self.device.model) if part
        )
        if hardware:
            group.add(Adw.ActionRow(title="Fabricante y modelo", subtitle=hardware))
        group.add(Adw.ActionRow(title="Bus", subtitle=self.device.bus_label))
        group.add(Adw.ActionRow(title="VID:PID", subtitle=self.device.identifier))
        if self.device.serial:
            group.add(Adw.ActionRow(title="Serial", subtitle=self.device.serial))
        if self.device.nodes:
            group.add(
                Adw.ActionRow(title="Nodos", subtitle=", ".join(self.device.nodes))
            )
        if self.device.input_names:
            group.add(
                Adw.ActionRow(
                    title="Nombre de entrada",
                    subtitle="\n".join(self.device.input_names),
                )
            )
        return group

    def _build_action_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Acción",
            description=(
                "Permitir da acceso al usuario de la sesión y marca el "
                "dispositivo como joystick.  Ignorar lo desautoriza (USB) o "
                "deniega el acceso a sus nodos (Bluetooth)."
            ),
        )
        self.allow_radio = Gtk.CheckButton()
        self.ignore_radio = Gtk.CheckButton()
        self.ignore_radio.set_group(self.allow_radio)
        self.allow_radio.set_active(True)

        group.add(
            self._radio_row(
                "Permitir / detectar",
                RuleAction.ALLOW.description,
                self.allow_radio,
            )
        )
        group.add(
            self._radio_row(
                "Ignorar",
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
            title="Visibilidad",
            description=(
                "Ocultar un dispositivo no borra sus reglas ni cambia permisos.  "
                "Podés recuperarlo desde el menú → Dispositivos ocultos."
            ),
        )
        row = Adw.ActionRow(
            title="Ocultar este dispositivo",
            subtitle=(
                "Se moverá a Dispositivos ocultos y dejará de aparecer en la "
                "lista principal."
            ),
        )
        icon = Gtk.Image(icon_name="view-conceal-symbolic")
        icon.add_css_class("dim-label")
        icon.set_valign(Gtk.Align.CENTER)
        row.add_prefix(icon)

        button = Gtk.Button(label="Ocultar")
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
                heading="No se pudo ocultar el dispositivo",
                body=f"No se pudo guardar la preferencia: {exc}",
            )
            dialog.add_response("close", "Cerrar")
            root = self.get_root()
            dialog.present(root if root is not None else self.parent_window)
            return
        self.on_hidden(f"Dispositivo oculto: {self.device.display_name}")
        self.close()

    def _build_preview_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Vista previa",
            description=(
                "La regla se instalará en /etc/udev/rules.d: 10- para permitir "
                "y 99- para ignorar (así la denegación se aplica al final)."
            ),
        )
        self.preview = Gtk.TextView()
        self.preview.set_editable(False)
        self.preview.set_cursor_visible(False)
        self.preview.set_monospace(True)
        self.preview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.preview.set_top_margin(12)
        self.preview.set_bottom_margin(12)
        self.preview.set_left_margin(12)
        self.preview.set_right_margin(12)
        self.preview.add_css_class("rule-preview")

        scroller = Gtk.ScrolledWindow()
        scroller.set_has_frame(True)
        scroller.set_min_content_height(210)
        scroller.set_vexpand(True)
        scroller.set_child(self.preview)
        scroller.set_margin_top(4)
        scroller.set_margin_bottom(4)
        group.add(scroller)
        return group

    def _action(self) -> RuleAction:
        return (
            RuleAction.IGNORE
            if self.ignore_radio.get_active()
            else RuleAction.ALLOW
        )

    def _on_action_changed(self) -> None:
        self._update_preview()
        self.banner.set_revealed(
            self.device.is_bluetooth and self._action() is RuleAction.IGNORE
        )

    def _update_preview(self) -> None:
        buffer = self.preview.get_buffer()
        try:
            self._spec = build_rule(self.device, self._action())
        except ValueError as exc:
            self._spec = None
            buffer.set_text(f"No se pudo generar la regla:\n{exc}")
            self.status_label.set_text("No se puede instalar esta regla.")
            self.install_button.set_sensitive(False)
            return
        buffer.set_text(self._spec.content)
        self.status_label.set_text(
            f"Se instalará como /etc/udev/rules.d/{self._spec.filename}"
        )
        self.install_button.set_sensitive(not self._busy)

    def _copy_rule(self) -> None:
        if self._spec is None:
            return
        display = Gdk.Display.get_default()
        if display is None:
            return
        display.get_clipboard().set(self._spec.content)
        self.status_label.set_text("Regla copiada al portapapeles.")

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
        self.on_installed(f"Regla instalada: {spec.filename}")
        self.close()
        return False

    def _install_failed(self, message: str) -> bool:
        self._set_busy(False)
        dialog = Adw.AlertDialog(
            heading="No se pudo instalar la regla",
            body=message,
        )
        dialog.add_response("close", "Cerrar")
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
                "Esperando el diálogo de autenticación de GNOME/polkit…"
            )
            return
        self.spinner.stop()
        if self._spec is not None:
            self.status_label.set_text(
                f"Se instalará como /etc/udev/rules.d/{self._spec.filename}"
            )
