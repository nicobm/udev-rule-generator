"""Lista principal de dispositivos y reglas guardadas."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator.devices import Joystick
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.known import KnownDevice, KnownDevices
from udev_rule_generator.privileged import apply_rule_changes
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
        self._pending_known: dict[str, bool] = {}
        self._pending_unknown: dict[str, Joystick] = {}
        self._rows: list[Gtk.Widget] = []
        self._controls: list[Gtk.Widget] = []
        self._busy = False
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

        self.action_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        self.action_bar.set_margin_top(10)
        self.action_bar.set_margin_bottom(10)
        self.action_bar.set_margin_start(14)
        self.action_bar.set_margin_end(14)

        self.pending_label = Gtk.Label(label="", xalign=0)
        self.pending_label.set_hexpand(True)
        self.pending_label.add_css_class("dim-label")
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        self.apply_button = Gtk.Button(label=tr("Aplicar cambios"))
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.set_sensitive(False)
        self.apply_button.connect("clicked", lambda *_: self._apply_pending())
        self.action_bar.append(self.pending_label)
        self.action_bar.append(self.spinner)
        self.action_bar.append(self.apply_button)
        self.action_bar.set_visible(False)

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
        known_ids = {device.id for device in known}
        for key in list(self._pending_known):
            record = next(
                (device for device in known if device.id == key), None
            )
            if record is None or record.active == self._pending_known[key]:
                self._pending_known.pop(key, None)
        for key in list(self._pending_unknown):
            if key in known_ids:
                self._pending_unknown.pop(key, None)

        connected = self._connected
        connected_ids = {device_identity(device) for device in connected}

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
        self._update_pending_ui()
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

        switch = Gtk.Switch(
            active=self._pending_known.get(device.id, device.active)
        )
        switch.set_valign(Gtk.Align.CENTER)
        switch.connect(
            "notify::active",
            lambda selected_switch, _pspec, selected=device: self._set_known_pending(
                selected, selected_switch.get_active()
            ),
        )
        row.add_suffix(switch)
        self._controls.append(switch)
        return row

    def _unknown_row(self, device: Joystick) -> Adw.ActionRow:
        key = device_identity(device)
        row = Adw.ActionRow(
            title=device.display_name,
            subtitle=f"{device.bus_label} · {device.identifier} · "
            f"{tr('Sin regla guardada')}",
        )
        row.set_activatable(False)
        row.add_suffix(self._connected_badge())

        switch = Gtk.Switch(active=key in self._pending_unknown)
        switch.set_valign(Gtk.Align.CENTER)
        switch.connect(
            "notify::active",
            lambda selected_switch, _pspec, selected=device: self._set_unknown_pending(
                selected, selected_switch.get_active()
            ),
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

    def _set_known_pending(self, device: KnownDevice, active: bool) -> None:
        if self._updating or self._busy:
            return
        if active == device.active:
            self._pending_known.pop(device.id, None)
        else:
            self._pending_known[device.id] = active
        self._update_pending_ui()

    def _set_unknown_pending(self, device: Joystick, active: bool) -> None:
        if self._updating or self._busy:
            return
        key = device_identity(device)
        if active:
            self._pending_unknown[key] = device
        else:
            self._pending_unknown.pop(key, None)
        self._update_pending_ui()

    def _update_pending_ui(self) -> None:
        pending = bool(self._pending_known or self._pending_unknown)
        self.action_bar.set_visible(pending)
        self.pending_label.set_text(
            tr("Cambios pendientes") if pending else ""
        )
        self.apply_button.set_sensitive(pending and not self._busy)

    def _apply_pending(self) -> None:
        if self._busy or not (self._pending_known or self._pending_unknown):
            return
        self._set_busy(True)
        thread = threading.Thread(
            target=self._apply_worker,
            name="udev-rule-generator-apply",
            daemon=True,
        )
        thread.start()

    def _apply_worker(self) -> None:
        try:
            install_files: dict[str, str] = {}
            updated: list[KnownDevice] = []
            removed: list[str] = []
            trigger_add = False

            for record in self.store.devices():
                desired = self._pending_known.get(record.id)
                if desired is None or desired == record.active:
                    continue
                if desired:
                    spec = record.build_spec()
                    if not spec.filename:
                        raise ValueError(
                            tr("No hay una regla guardada para activar.")
                        )
                    install_files[spec.filename] = spec.content
                    updated.append(record.update_from_spec(spec))
                    trigger_add = trigger_add or spec.trigger == "add"
                elif record.filename:
                    removed.append(record.filename)

            for device in self._pending_unknown.values():
                spec = build_rule(device, RuleAction.ALLOW)
                if not spec.filename:
                    raise ValueError(
                        tr("No hay una regla guardada para activar.")
                    )
                install_files[spec.filename] = spec.content
                updated.append(
                    KnownDevice.from_joystick(device, spec)
                )
                trigger_add = trigger_add or spec.trigger == "add"

            if not install_files and not removed:
                message = tr("No hay cambios para aplicar.")
            else:
                apply_rule_changes(
                    self.host,
                    install_files,
                    removed,
                    trigger="add" if trigger_add else "change",
                )
                try:
                    if updated:
                        self.store.update_many(updated)
                    if removed:
                        self.store.mark_inactive_by_filenames(removed)
                except OSError as exc:
                    message = tr(
                        "Cambios aplicados, pero no se pudo guardar el "
                        "estado: {error}",
                        error=exc,
                    )
                else:
                    message = tr("Cambios aplicados.")
            self._pending_known.clear()
            self._pending_unknown.clear()
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._apply_failed, str(exc))
            return
        GLib.idle_add(self._apply_succeeded, message)

    def _apply_succeeded(self, message: str) -> bool:
        self._set_busy(False)
        self.reload()
        self.on_changed(message)
        return False

    def _apply_failed(self, message: str) -> bool:
        self._set_busy(False)
        self.reload()
        self._show_error(
            tr("No se pudieron aplicar los cambios"),
            message,
        )
        return False

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for control in self._controls:
            control.set_sensitive(not busy)
        self.apply_button.set_sensitive(
            not busy and bool(self._pending_known or self._pending_unknown)
        )
        self.spinner.set_visible(busy)
        if busy:
            self.spinner.start()
            self.action_bar.set_visible(True)
            self.pending_label.set_text(
                tr("Esperando el diálogo de autenticación de GNOME/polkit…")
            )
            return
        self.spinner.stop()
        self._update_pending_ui()

    def _apply_sensitivity(self) -> None:
        enabled = not self._busy
        for control in self._controls:
            control.set_sensitive(enabled)

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", tr("Cerrar"))
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)
