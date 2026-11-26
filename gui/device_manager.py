"""Lista principal de dispositivos, reglas guardadas y reglas de Steam."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator import GAME_DEVICES_URL, STEAM_DEVICES_URL
from udev_rule_generator.devices import Joystick
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.known import KnownDevice, KnownDevices
from udev_rule_generator.presets import (
    GAME_DEVICES,
    STEAM,
    preset_files,
    presets_trigger,
)
from udev_rule_generator.privileged import apply_rule_changes, remove_rule_files
from udev_rule_generator.rules import RuleAction, build_rule
from udev_rule_generator.userconfig import device_identity

from .gi_compat import Adw, GLib, Gtk


def _js_nodes_label(device: Joystick | None) -> str:
    """Devuelve los nombres cortos de los nodos js, por ejemplo ``js0``."""
    if device is None:
        return ""
    names: list[str] = []
    for node in device.js_devices:
        name = node.rsplit("/", 1)[-1]
        if name and name not in names:
            names.append(name)
    return ", ".join(names)


class DeviceManager(Gtk.Box):
    """Gestiona reglas guardadas, dispositivos ocultos y reglas externas."""

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
        self._pending_steam: bool | None = None
        self._pending_gdu: bool | None = None
        self._steam_installed = False
        self._gdu_installed = False
        self._uinput_available = True
        self._rows: list[tuple[Adw.PreferencesGroup, Gtk.Widget]] = []
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

        self.external_group = Adw.PreferencesGroup(
            title=tr("Reglas externas"),
            description=tr(
                "Paquetes opcionales de reglas udev. No se instalan "
                "automáticamente."
            ),
        )
        self.external_group.set_separate_rows(True)
        self.external_group.set_hexpand(True)

        self._steam_subtitle = tr(
            "Añade las reglas udev de Valve para usar Steam Input y "
            "SteamVR. · {url} (MIT)",
            url=STEAM_DEVICES_URL,
        )
        self.steam_switch = Adw.SwitchRow(
            title=tr("steam-devices"),
            subtitle=self._steam_subtitle,
        )
        self.steam_switch.connect(
            "notify::active", self._on_steam_toggled
        )
        self.external_group.add(self.steam_switch)

        self.gdu_switch = Adw.SwitchRow(
            title=tr("game-devices-udev"),
            subtitle=tr(
                "Añade las reglas udev del repositorio de Fabian Bornschein "
                "fabiscafe/game-devices-udev (MIT) · {url}",
                url=GAME_DEVICES_URL,
            ),
        )
        self.gdu_switch.connect("notify::active", self._on_gdu_toggled)
        self.external_group.add(self.gdu_switch)

        self.append(self.external_group)

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

    def set_uinput_available(self, available: bool) -> None:
        self._uinput_available = available
        if not available:
            self._pending_steam = None
        tooltip = (
            ""
            if available
            else tr("Requiere el módulo uinput del kernel.")
        )
        self.steam_switch.set_tooltip_text(tooltip)
        if available:
            self.steam_switch.remove_css_class("uinput-error")
            self.steam_switch.set_subtitle(self._steam_subtitle)
        else:
            self.steam_switch.add_css_class("uinput-error")
            self.steam_switch.set_subtitle(
                tr(
                    "uinput no está activo. Para habilitar estas reglas "
                    "udev, activá el módulo uinput en tu sistema operativo."
                )
            )
        self._update_preset_switches()
        self._apply_sensitivity()

    def set_installed_rules(self, rules: list) -> None:
        filenames = {
            rule.filename for rule in rules if rule.kind == "preset"
        }
        self._steam_installed = set(preset_files(STEAM)) <= filenames
        self._gdu_installed = set(preset_files(GAME_DEVICES)) <= filenames
        if (
            self._pending_steam is not None
            and self._pending_steam == self._steam_installed
        ):
            self._pending_steam = None
        if (
            self._pending_gdu is not None
            and self._pending_gdu == self._gdu_installed
        ):
            self._pending_gdu = None
        self._update_preset_switches()

    def _update_preset_switches(self) -> None:
        if self._updating:
            return
        self._updating = True
        self.steam_switch.set_active(
            self._pending_steam
            if self._pending_steam is not None
            else self._steam_installed
        )
        self.gdu_switch.set_active(
            self._pending_gdu
            if self._pending_gdu is not None
            else self._gdu_installed
        )
        self._updating = False
        self._update_pending_ui()

    def reload(self) -> None:
        self._updating = True
        for group, row in self._rows:
            group.remove(row)
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
        allow_known = [
            device
            for device in known
            if device.action == "allow" and not device.hidden
        ]
        connected = self._connected
        connected_by_id = {
            device_identity(device): device for device in connected
        }

        regular_connected = [
            device
            for device in connected
            if device_identity(device) not in known_ids
        ]

        for record in allow_known:
            self._append(
                self.devices_group,
                self._known_row(
                    record,
                    connected_by_id.get(record.id),
                    removable=True,
                ),
            )
        for device in regular_connected:
            self._append(self.devices_group, self._unknown_row(device))

        if not allow_known and not regular_connected:
            row = Adw.ActionRow(
                title=tr("No hay dispositivos guardados"),
                subtitle=tr(
                    "Conectá un mando para crear su primera regla."
                ),
            )
            row.set_activatable(False)
            self._append(self.devices_group, row)

        self._apply_sensitivity()
        self._update_pending_ui()
        self._updating = False

    def _append(self, group: Adw.PreferencesGroup, row: Gtk.Widget) -> None:
        group.add(row)
        self._rows.append((group, row))
        if row not in self._controls:
            self._controls.append(row)

    def _known_row(
        self,
        device: KnownDevice,
        connected_device: Joystick | None,
        *,
        removable: bool = False,
    ) -> Adw.ActionRow:
        details = [device.bus_label, device.identifier]
        js_label = _js_nodes_label(connected_device)
        if js_label:
            details.append(js_label)
        row = Adw.ActionRow(
            title=device.name,
            subtitle=" · ".join(details),
        )
        row.set_activatable(False)
        row.set_tooltip_text(device.filename)

        if connected_device is not None:
            row.add_suffix(self._connected_badge())

        if removable:
            hide = Gtk.Button(
                icon_name="view-conceal-symbolic",
                tooltip_text=tr("Ocultar este dispositivo"),
            )
            hide.add_css_class("flat")
            hide.set_valign(Gtk.Align.CENTER)
            hide.connect(
                "clicked",
                lambda _button, selected=device: self._hide_known(
                    selected
                ),
            )
            row.add_suffix(hide)

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
        details = [device.bus_label, device.identifier]
        js_label = _js_nodes_label(device)
        if js_label:
            details.append(js_label)
        details.append(tr("Sin regla guardada"))
        row = Adw.ActionRow(
            title=device.display_name,
            subtitle=" · ".join(details),
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

    def _hide_known(self, device: KnownDevice) -> None:
        if self._busy:
            return
        self._pending_known.pop(device.id, None)
        if not device.active or not device.filename:
            self.store.set_hidden(device.id, True)
            self.reload()
            self.on_changed(
                tr("Dispositivo oculto: {name}", name=device.name)
            )
            return
        self._set_busy(True)
        thread = threading.Thread(
            target=self._hide_worker,
            args=(device,),
            name="udev-rule-generator-hide",
            daemon=True,
        )
        thread.start()

    def _hide_worker(self, device: KnownDevice) -> None:
        try:
            remove_rule_files(self.host, [device.filename])
            self.store.mark_inactive_by_filenames([device.filename])
            self.store.set_hidden(device.id, True)
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._hide_failed, str(exc))
            return
        GLib.idle_add(self._hide_succeeded, device)

    def _hide_succeeded(self, device: KnownDevice) -> bool:
        self._set_busy(False)
        self.reload()
        self.on_changed(
            tr("Dispositivo oculto: {name}", name=device.name)
        )
        return False

    def _hide_failed(self, message: str) -> bool:
        self._set_busy(False)
        self._show_error(
            tr("No se pudo ocultar el dispositivo"),
            message,
        )
        return False

    def _set_unknown_pending(self, device: Joystick, active: bool) -> None:
        if self._updating or self._busy:
            return
        key = device_identity(device)
        if active:
            self._pending_unknown[key] = device
        else:
            self._pending_unknown.pop(key, None)
        self._update_pending_ui()

    def _on_steam_toggled(self, row: Adw.SwitchRow, _pspec) -> None:
        if self._updating or self._busy or not self._uinput_available:
            return
        active = row.get_active()
        self._pending_steam = (
            None if active == self._steam_installed else active
        )
        self._update_pending_ui()

    def _on_gdu_toggled(self, row: Adw.SwitchRow, _pspec) -> None:
        if self._updating or self._busy:
            return
        active = row.get_active()
        self._pending_gdu = (
            None if active == self._gdu_installed else active
        )
        self._update_pending_ui()

    def _update_pending_ui(self) -> None:
        pending = bool(
            self._pending_known
            or self._pending_unknown
            or self._pending_steam is not None
            or self._pending_gdu is not None
        )
        self.action_bar.set_visible(pending)
        self.pending_label.set_text(
            tr("Cambios pendientes") if pending else ""
        )
        self.apply_button.set_sensitive(pending and not self._busy)

    def _apply_pending(self) -> None:
        if self._busy or not (
            self._pending_known
            or self._pending_unknown
            or self._pending_steam is not None
            or self._pending_gdu is not None
        ):
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

            preset_changes = (
                (STEAM, self._pending_steam),
                (GAME_DEVICES, self._pending_gdu),
            )
            for presets, desired in preset_changes:
                if desired is None:
                    continue
                package_files = preset_files(presets)
                if desired:
                    install_files.update(package_files)
                    trigger_add = trigger_add or (
                        presets_trigger(presets) == "add"
                    )
                else:
                    removed.extend(package_files)

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
            for presets, desired in preset_changes:
                if desired is None:
                    continue
                if presets is STEAM:
                    self._steam_installed = desired
                else:
                    self._gdu_installed = desired
            self._pending_known.clear()
            self._pending_unknown.clear()
            self._pending_steam = None
            self._pending_gdu = None
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
        self.steam_switch.set_sensitive(
            not busy and self._uinput_available
        )
        self.gdu_switch.set_sensitive(not busy)
        self.apply_button.set_sensitive(
            not busy
            and bool(
                self._pending_known
                or self._pending_unknown
                or self._pending_steam is not None
                or self._pending_gdu is not None
            )
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
        self.steam_switch.set_sensitive(
            enabled and self._uinput_available
        )
        self.gdu_switch.set_sensitive(enabled)

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", tr("Cerrar"))
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)
