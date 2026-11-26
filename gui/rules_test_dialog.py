"""Diálogo para comprobar si las reglas udev llegan a los mandos."""

from __future__ import annotations

import threading

from udev_rule_generator.devices import (
    Joystick,
    detect_joysticks,
    parse_udev_properties,
)
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.known import KnownDevices
from udev_rule_generator.userconfig import device_identity

from .gi_compat import Adw, GLib, Gtk


class RulesTestDialog(Adw.Window):
    """Muestra el resultado de udev para cada mando conectado."""

    def __init__(
        self,
        *,
        host: Host,
        store: KnownDevices,
        parent: Gtk.Window,
    ) -> None:
        super().__init__(
            transient_for=parent,
            modal=True,
            title=tr("Test de reglas"),
            default_width=640,
            default_height=480,
        )
        self.host = host
        self.store = store
        self._loading_row: Adw.ActionRow | None = None

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(title=tr("Test de reglas"))
        )
        toolbar.add_top_bar(header)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)
        self.group = Adw.PreferencesGroup(
            description=tr(
                "Comprobación de las reglas udev de los mandos conectados."
            )
        )
        page.add(self.group)
        toolbar.set_content(page)
        self.set_content(toolbar)

        self._show_loading()
        threading.Thread(
            target=self._test_worker,
            name="udev-rule-generator-rules-test",
            daemon=True,
        ).start()

    def _show_loading(self) -> None:
        row = Adw.ActionRow(title=tr("Probando reglas…"))
        spinner = Gtk.Spinner()
        spinner.set_valign(Gtk.Align.CENTER)
        spinner.start()
        row.add_suffix(spinner)
        self.group.add(row)
        self._loading_row = row

    def _test_worker(self) -> None:
        try:
            devices = detect_joysticks(self.host)
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._show_error, str(exc))
            return
        results: list[tuple[Joystick, str | None, str | None]] = []
        for device in devices:
            target = (
                device.js_devices[0]
                if device.js_devices
                else device.event_devices[0]
                if device.event_devices
                else None
            )
            if target is None:
                results.append(
                    (device, None, tr("No tiene nodo de entrada visible."))
                )
                continue
            try:
                result = self.host.run(
                    ["udevadm", "info", "--query=property", "--name", target],
                    timeout=20,
                )
            except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
                results.append((device, None, str(exc)))
                continue
            if not result.ok:
                results.append(
                    (
                        device,
                        None,
                        result.stderr.strip()
                        or result.stdout.strip()
                        or tr("udevadm no devolvió información."),
                    )
                )
                continue
            results.append(
                (device, parse_udev_properties(result.stdout), None)
            )
        GLib.idle_add(self._apply_results, results)

    def _apply_results(
        self,
        results: list[tuple[Joystick, dict[str, str] | None, str | None]],
    ) -> bool:
        if self._loading_row is not None:
            self.group.remove(self._loading_row)
            self._loading_row = None
        if not results:
            self.group.set_description(
                tr("No hay mandos conectados para probar.")
            )
            return False

        for device, properties, error in results:
            if error is not None or properties is None:
                row = Adw.ActionRow(
                    title=device.display_name,
                    subtitle=error or tr("No se pudo consultar udev."),
                )
                row.set_activatable(False)
                row.add_suffix(
                    Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
                )
                self.group.add(row)
                continue

            tags = properties.get("CURRENT_TAGS") or properties.get(
                "TAGS", ""
            )
            has_uaccess = "uaccess" in tags.split(":")
            id_joystick = (
                properties.get("ID_INPUT_JOYSTICK", "").lower()
                in {"1", "true", "yes"}
            )
            record = self.store.get(device_identity(device))
            if record is None:
                rule_state = tr("Sin regla guardada")
            elif record.active:
                rule_state = tr("Regla activa")
            else:
                rule_state = tr("Regla desactivada")

            node = (
                device.js_devices[0]
                if device.js_devices
                else device.event_devices[0]
                if device.event_devices
                else tr("sin nodo")
            )
            ok = id_joystick and has_uaccess
            details = [
                device.bus_label,
                device.identifier,
                node.rsplit("/", 1)[-1],
                tr("ID_INPUT_JOYSTICK: {value}", value=tr("sí") if id_joystick else tr("no")),
                tr("uaccess: {value}", value=tr("sí") if has_uaccess else tr("no")),
                rule_state,
            ]
            row = Adw.ActionRow(
                title=device.display_name,
                subtitle=" · ".join(details),
            )
            row.set_activatable(False)
            row.add_suffix(
                Gtk.Image.new_from_icon_name(
                    "emblem-ok-symbolic"
                    if ok
                    else "dialog-warning-symbolic"
                )
            )
            self.group.add(row)
        return False

    def _show_error(self, message: str) -> bool:
        if self._loading_row is not None:
            self.group.remove(self._loading_row)
            self._loading_row = None
        self.group.set_description(
            tr("No se pudieron probar las reglas: {error}", error=message)
        )
        return False
