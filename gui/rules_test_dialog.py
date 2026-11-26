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

from .gi_compat import Adw, GLib, Gtk, markup_escape


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
        self._device_test_dialog = None

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
                    title=markup_escape(device.display_name),
                    subtitle=markup_escape(
                        error or tr("No se pudo consultar udev.")
                    ),
                )
                row.set_activatable(False)
                self._add_test_button(row, device)
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
            details = [
                device.bus_label,
                device.identifier,
                node.rsplit("/", 1)[-1],
                tr("ID_INPUT_JOYSTICK: {value}", value=tr("sí") if id_joystick else tr("no")),
                tr("uaccess: {value}", value=tr("sí") if has_uaccess else tr("no")),
                rule_state,
            ]
            row = Adw.ActionRow(
                title=markup_escape(device.display_name),
                subtitle=markup_escape(" · ".join(details)),
            )
            row.set_activatable(False)
            self._add_test_button(row, device)
            self.group.add(row)
        return False

    def _add_test_button(self, row: Adw.ActionRow, device: Joystick) -> None:
        button = Gtk.Button(label=tr("Probar botones"))
        button.add_css_class("flat")
        button.set_valign(Gtk.Align.CENTER)
        if not device.event_devices:
            button.set_sensitive(False)
            button.set_tooltip_text(
                tr("No hay un nodo event visible para este dispositivo.")
            )
        else:
            button.connect(
                "clicked",
                lambda _button, selected=device: self._open_device_test(
                    selected
                ),
            )
        row.add_suffix(button)

    def _open_device_test(self, device: Joystick) -> None:
        previous = self._device_test_dialog
        self._device_test_dialog = None
        if previous is not None:
            try:
                if previous.get_realized():
                    previous.destroy()
            except Exception:
                pass
        from .device_test_dialog import DeviceTestDialog

        self._device_test_dialog = DeviceTestDialog(
            device=device,
            parent=self,
        )
        self._device_test_dialog.connect(
            "close-request", self._on_device_test_close
        )
        self._device_test_dialog.connect(
            "destroy", self._on_device_test_destroyed
        )
        self._device_test_dialog.present()

    def _on_device_test_close(self, dialog) -> bool:
        if self._device_test_dialog is dialog:
            self._device_test_dialog = None
        return False

    def _on_device_test_destroyed(self, _dialog) -> None:
        self._device_test_dialog = None

    def _show_error(self, message: str) -> bool:
        if self._loading_row is not None:
            self.group.remove(self._loading_row)
            self._loading_row = None
        self.group.set_description(
            tr("No se pudieron probar las reglas: {error}", error=message)
        )
        return False
