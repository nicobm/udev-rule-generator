"""Lista principal de dispositivos y reglas guardadas."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator.devices import Joystick
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.known import KnownDevice, KnownDevices
from udev_rule_generator.privileged import install_rule_files, remove_rule_files
from udev_rule_generator.rules import RuleAction, build_rule
from udev_rule_generator.userconfig import device_identity

from .gi_compat import Adw, GLib, Gtk


class DeviceManager(Gtk.Box):
    """Gestiona las reglas guardadas y los mandos conectados sin guardar."""

    def __init__(
        self,
        *,
        host: Host,
        store: KnownDevices,
        parent: Gtk.Window,
        on_changed: Callable[[str], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.host = host
        self.store = store
        self.parent_window = parent
        self.on_changed = on_changed
        self._connected: list[Joystick] = []
        self._rows: list[Gtk.Widget] = []
        self._controls: list[Gtk.Widget] = []
        self._known_busy = False
        self._updating = False

        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        self.devices_group = Adw.PreferencesGroup(
            title=tr("Gestionar dispositivos"),
            description=tr("Activá o desactivá las reglas guardadas."),
        )
        self.devices_group.set_separate_rows(True)
        self.devices_group.set_hexpand(True)
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

        known = self.store.devices()
        connected = self._connected
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
            subtitle=f"{device.bus_label} · {device.identifier}",
        )
        row.set_activatable(False)
        row.set_tooltip_text(device.filename)

        if connected:
            row.add_suffix(self._connected_badge())

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
        return row

    def _unknown_row(self, device: Joystick) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=device.display_name,
            subtitle=f"{device.bus_label} · {device.identifier} · "
            f"{tr('Sin regla guardada')}",
        )
        row.set_activatable(False)
        row.add_suffix(self._connected_badge())

        switch = Gtk.Switch(active=False)
        switch.set_valign(Gtk.Align.CENTER)
        switch.connect(
            "notify::active",
            lambda selected_switch, _pspec, selected=device: self._enable_unknown(
                selected
            )
            if selected_switch.get_active()
            else None,
        )
        row.add_suffix(switch)
        self._controls.append(switch)
        return row

    def _connected_badge(self) -> Gtk.Label:
        badge = Gtk.Label(label=tr("Conectado"))
        badge.add_css_class("device-badge")
        badge.add_css_class("device-badge-connected")
        badge.set_valign(Gtk.Align.CENTER)
        return badge

    def _enable_unknown(self, device: Joystick) -> None:
        if self._updating or self._known_busy:
            return
        self._set_busy(True)
        thread = threading.Thread(
            target=self._unknown_worker,
            args=(device,),
            name="udev-rule-generator-known-new",
            daemon=True,
        )
        thread.start()

    def _unknown_worker(self, device: Joystick) -> None:
        try:
            spec = build_rule(device, RuleAction.ALLOW)
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
                self.store.record_rule(device, spec)
            except OSError as exc:
                message = tr(
                    "Regla activada: {name}.  No se pudo guardar el "
                    "estado: {error}",
                    name=device.display_name,
                    error=exc,
                )
            else:
                message = tr(
                    "Regla activada: {name}", name=device.display_name
                )
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._unknown_failed, str(exc))
            return
        GLib.idle_add(self._unknown_succeeded, message)

    def _unknown_succeeded(self, message: str) -> bool:
        self._set_busy(False)
        self.reload()
        self.on_changed(message)
        return False

    def _unknown_failed(self, message: str) -> bool:
        self._set_busy(False)
        self.reload()
        self._show_error(
            tr("No se pudo activar el dispositivo"),
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
        for control in self._controls:
            control.set_sensitive(enabled)

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", tr("Cerrar"))
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)
