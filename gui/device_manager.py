"""Lista principal de dispositivos y reglas guardadas."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator.devices import Joystick
from udev_rule_generator.hidden import HiddenDevices, device_identity
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.known import KnownDevice, KnownDevices
from udev_rule_generator.privileged import install_rule_files, remove_rule_files
from udev_rule_generator.rules import RuleAction, RuleSpec

from .gi_compat import Adw, GLib, Gtk


class DeviceManager(Gtk.Box):
    """Gestiona las reglas guardadas y los mandos conectados sin guardar."""

    def __init__(
        self,
        *,
        host: Host,
        store: KnownDevices,
        hidden_store: HiddenDevices,
        parent: Gtk.Window,
        on_changed: Callable[[str], None],
        on_configure: Callable[[Joystick, RuleAction], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.host = host
        self.store = store
        self.hidden_store = hidden_store
        self.parent_window = parent
        self.on_changed = on_changed
        self.on_configure = on_configure
        self._connected: list[Joystick] = []
        self._visible_known: list[KnownDevice] = []
        self._rows: list[Gtk.Widget] = []
        self._controls: list[Gtk.Widget] = []
        self._known_busy = False
        self._updating = False

        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        self.master_group = Adw.PreferencesGroup()
        self.master_group.set_separate_rows(True)
        self.master_row = Adw.SwitchRow(title=tr("Activar todos"))
        self.master_row.connect("notify::active", self._on_master_toggled)
        self.master_group.add(self.master_row)
        self.master_group.set_visible(False)
        self.append(self.master_group)

        self.devices_group = Adw.PreferencesGroup(
            title=tr("Gestionar dispositivos"),
            description=tr(
                "Activá o desactivá las reglas guardadas.  Los mandos "
                "conectados llevan una etiqueta verde."
            ),
        )
        self.devices_group.set_separate_rows(True)
        self.devices_group.set_hexpand(True)

        self.badges = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
        )
        self.badges.set_valign(Gtk.Align.CENTER)
        self.active_label = Gtk.Label(label="")
        self.active_label.add_css_class("device-badge")
        self.active_label.add_css_class("device-badge-active")
        self.active_label.set_valign(Gtk.Align.CENTER)
        self.active_label.set_width_chars(2)
        self.active_label.set_xalign(0.5)
        self.active_label.set_visible(False)
        self.badges.append(self.active_label)

        self.inactive_label = Gtk.Label(label="")
        self.inactive_label.add_css_class("device-badge")
        self.inactive_label.set_valign(Gtk.Align.CENTER)
        self.inactive_label.set_width_chars(2)
        self.inactive_label.set_xalign(0.5)
        self.inactive_label.set_visible(False)
        self.badges.append(self.inactive_label)
        self.devices_group.set_header_suffix(self.badges)
        self.append(self.devices_group)

    def set_connected_devices(self, devices: list[Joystick]) -> None:
        fingerprint = tuple(
            (device.key, device.display_name, device.identifier)
            for device in devices
        )
        previous = tuple(
            (device.key, device.display_name, device.identifier)
            for device in self._connected
        )
        self._connected = list(devices)
        if fingerprint != previous:
            self.reload()

    def reload(self) -> None:
        self._updating = True
        for row in self._rows:
            self.devices_group.remove(row)
        self._rows.clear()
        self._controls.clear()

        hidden_ids = {device.id for device in self.hidden_store.devices()}
        known = [
            device
            for device in self.store.devices()
            if device.id not in hidden_ids
            and not self.hidden_store.is_hidden(device.to_joystick())
        ]
        self._visible_known = known
        connected = [
            device
            for device in self._connected
            if not self.hidden_store.is_hidden(device)
        ]
        connected_ids = {device_identity(device) for device in connected}
        known_ids = {device.id for device in known}

        for record in known:
            self._append(self._known_row(record, record.id in connected_ids))
        for device in connected:
            if device_identity(device) not in known_ids:
                self._append(self._unknown_row(device))

        if not self._rows:
            row = Adw.ActionRow(
                title=tr("No hay dispositivos guardados"),
                subtitle=tr(
                    "Conectá un mando para crear su primera regla."
                ),
            )
            row.set_activatable(False)
            self._append(row)

        self.master_group.set_visible(bool(known))
        self._update_master(known)
        self._update_badges(known)
        self._apply_sensitivity()
        self._updating = False

    def _append(self, row: Gtk.Widget) -> None:
        self.devices_group.add(row)
        self._rows.append(row)
        if row not in self._controls:
            self._controls.append(row)

    def _known_row(self, device: KnownDevice, connected: bool) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=device.name,
            subtitle=f"{device.bus_label} · {device.identifier} · "
            f"{device.action_label}",
        )
        row.set_activatable(False)
        row.set_tooltip_text(device.filename)

        if connected:
            row.add_suffix(self._connected_badge())

        configure = Gtk.Button(
            icon_name="document-edit-symbolic",
            tooltip_text=tr("Configurar"),
        )
        configure.add_css_class("flat")
        configure.set_valign(Gtk.Align.CENTER)
        configure.connect(
            "clicked",
            lambda _button, selected=device: self.on_configure(
                selected.to_joystick(), RuleAction(selected.action)
            ),
        )
        row.add_suffix(configure)

        switch = Gtk.Switch(active=device.active)
        switch.set_valign(Gtk.Align.CENTER)
        switch.connect(
            "notify::active",
            lambda selected_switch, _pspec, selected=device: self._toggle_known(
                selected, selected_switch.get_active()
            ),
        )
        row.add_suffix(switch)
        self._controls.append(switch)
        self._controls.append(configure)
        return row

    def _unknown_row(self, device: Joystick) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=device.display_name,
            subtitle=f"{device.bus_label} · {device.identifier} · "
            f"{tr('Sin regla guardada')}",
        )
        row.set_activatable(True)
        row.connect(
            "activated",
            lambda _row, selected=device: self.on_configure(
                selected, RuleAction.ALLOW
            ),
        )
        row.add_suffix(self._connected_badge())
        arrow = Gtk.Image(icon_name="go-next-symbolic")
        arrow.add_css_class("dim-label")
        row.add_suffix(arrow)
        return row

    def _connected_badge(self) -> Gtk.Label:
        badge = Gtk.Label(label=tr("Conectado"))
        badge.add_css_class("device-badge")
        badge.add_css_class("device-badge-connected")
        badge.set_valign(Gtk.Align.CENTER)
        return badge

    def _update_master(self, devices: list[KnownDevice]) -> None:
        active = sum(1 for device in devices if device.active)
        self.master_row.set_active(bool(devices) and active == len(devices))

    def _update_badges(self, devices: list[KnownDevice]) -> None:
        active = sum(1 for device in devices if device.active)
        inactive = len(devices) - active
        self.active_label.set_text(str(active))
        self.active_label.set_visible(active > 0)
        self.inactive_label.set_text(str(inactive))
        self.inactive_label.set_visible(inactive > 0)
        if active == 1:
            active_tooltip = tr("{count} regla activa", count=active)
        else:
            active_tooltip = tr("{count} reglas activas", count=active)
        self.active_label.set_tooltip_text(active_tooltip)
        if inactive == 1:
            inactive_tooltip = tr(
                "{count} regla desactivada", count=inactive
            )
        else:
            inactive_tooltip = tr(
                "{count} reglas desactivadas", count=inactive
            )
        self.inactive_label.set_tooltip_text(inactive_tooltip)

    def _on_master_toggled(self, row: Adw.SwitchRow, _pspec) -> None:
        if self._updating or self._known_busy:
            return
        activate = row.get_active()
        targets = [
            device
            for device in self._visible_known
            if device.active != activate
        ]
        if not targets:
            self.reload()
            return
        self._set_busy(True)
        thread = threading.Thread(
            target=self._master_worker,
            args=(targets, activate),
            name="udev-rule-generator-known-all",
            daemon=True,
        )
        thread.start()

    def _master_worker(
        self, devices: list[KnownDevice], activate: bool
    ) -> None:
        try:
            if activate:
                specs: list[tuple[KnownDevice, RuleSpec]] = []
                for device in devices:
                    spec = device.build_spec()
                    if not spec.filename:
                        raise ValueError(
                            tr("No hay una regla guardada para activar.")
                        )
                    specs.append((device, spec))
                files = {spec.filename: spec.content for _device, spec in specs}
                trigger = (
                    "add"
                    if any(spec.trigger == "add" for _device, spec in specs)
                    else "change"
                )
                install_rule_files(self.host, files, trigger=trigger)
                updated = [
                    device.update_from_spec(spec)
                    for device, spec in specs
                ]
                try:
                    self.store.update_many(updated)
                except OSError as exc:
                    message = self._bulk_message(len(devices), True) + (
                        "  " + tr("No se pudo guardar el estado: {error}", error=exc)
                    )
                else:
                    message = self._bulk_message(len(devices), True)
            else:
                filenames = list(
                    dict.fromkeys(
                        device.filename
                        for device in devices
                        if device.filename
                    )
                )
                if not filenames:
                    raise ValueError(
                        tr("No hay reglas guardadas para desactivar.")
                    )
                remove_rule_files(self.host, filenames)
                try:
                    self.store.mark_inactive_by_filenames(filenames)
                except OSError as exc:
                    message = self._bulk_message(len(filenames), False) + (
                        "  " + tr("No se pudo guardar el estado: {error}", error=exc)
                    )
                else:
                    message = self._bulk_message(len(filenames), False)
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._master_failed, str(exc))
            return
        GLib.idle_add(self._master_succeeded, message)

    @staticmethod
    def _bulk_message(count: int, activate: bool) -> str:
        if activate:
            if count == 1:
                return tr("Se activó {count} dispositivo.", count=count)
            return tr("Se activaron {count} dispositivos.", count=count)
        if count == 1:
            return tr("Se desactivó {count} dispositivo.", count=count)
        return tr("Se desactivaron {count} dispositivos.", count=count)

    def _master_succeeded(self, message: str) -> bool:
        self._set_busy(False)
        self.reload()
        self.on_changed(message)
        return False

    def _master_failed(self, message: str) -> bool:
        self._set_busy(False)
        self.reload()
        self._show_error(
            tr("No se pudieron cambiar los dispositivos guardados"),
            message,
        )
        return False

    def _toggle_known(self, device: KnownDevice, active: bool) -> None:
        if self._updating or self._known_busy or active == device.active:
            return
        self._set_busy(True)
        thread = threading.Thread(
            target=self._known_worker,
            args=(device, active),
            name="udev-rule-generator-known",
            daemon=True,
        )
        thread.start()

    def _known_worker(self, device: KnownDevice, active: bool) -> None:
        try:
            if active:
                spec = device.build_spec()
                if not spec.filename:
                    raise ValueError(
                        tr("No hay una regla guardada para activar.")
                    )
                install_rule_files(
                    self.host,
                    {spec.filename: spec.content},
                    trigger=spec.trigger,
                )
                try:
                    self.store.update(device.update_from_spec(spec))
                except OSError as exc:
                    message = tr(
                        "Regla activada: {name}.  No se pudo guardar el "
                        "estado: {error}",
                        name=device.name,
                        error=exc,
                    )
                else:
                    message = tr("Regla activada: {name}", name=device.name)
            else:
                if not device.filename:
                    raise ValueError(
                        tr("No hay una regla guardada para desactivar.")
                    )
                remove_rule_files(self.host, [device.filename])
                try:
                    self.store.mark_inactive_by_filename(device.filename)
                except OSError as exc:
                    message = tr(
                        "Regla desactivada: {name}.  No se pudo guardar el "
                        "estado: {error}",
                        name=device.name,
                        error=exc,
                    )
                else:
                    message = tr("Regla desactivada: {name}", name=device.name)
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._known_failed, str(exc))
            return
        GLib.idle_add(self._known_succeeded, message)

    def _known_succeeded(self, message: str) -> bool:
        self._set_busy(False)
        self.reload()
        self.on_changed(message)
        return False

    def _known_failed(self, message: str) -> bool:
        self._set_busy(False)
        self.reload()
        self._show_error(
            tr("No se pudo cambiar la regla guardada"),
            message,
        )
        return False

    def _set_busy(self, busy: bool) -> None:
        self._known_busy = busy
        self._apply_sensitivity()

    def _apply_sensitivity(self) -> None:
        enabled = not self._known_busy
        self.master_row.set_sensitive(enabled)
        for control in self._controls:
            control.set_sensitive(enabled)

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", tr("Cerrar"))
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)
