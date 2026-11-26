"""Diálogo para activar o desactivar reglas de dispositivos guardados."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.installed import list_installed_rules
from udev_rule_generator.known import KnownDevice, KnownDevices
from udev_rule_generator.privileged import install_rule_files, remove_rule_files
from udev_rule_generator.rules import RuleSpec

from .gi_compat import Adw, GLib, Gtk


class KnownDialog(Adw.Dialog):
    """Lista dispositivos guardados y permite activar sus reglas sin USB."""

    def __init__(
        self,
        *,
        host: Host,
        store: KnownDevices,
        parent: Gtk.Window,
        on_changed: Callable[[str], None],
        connected_ids: set[str] | None = None,
    ) -> None:
        super().__init__()
        self.parent_window = parent
        self.host = host
        self.store = store
        self.on_changed = on_changed
        self.connected_ids = connected_ids
        self._rows: list[Adw.SwitchRow] = []
        self._busy = False
        self._updating = False

        self.set_title(tr("Dispositivos guardados"))
        self.set_content_width(740)
        self.set_content_height(680)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title=tr("Dispositivos guardados"),
                subtitle=tr("Activá o desactivá sus reglas sin conectar el mando"),
            )
        )
        close_button = Gtk.Button(
            icon_name="window-close-symbolic",
            tooltip_text=tr("Cerrar"),
        )
        close_button.add_css_class("flat")
        close_button.connect("clicked", lambda *_: self.close())
        header.pack_end(close_button)
        toolbar.add_top_bar(header)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_vexpand(True)

        spinner = Gtk.Spinner()
        spinner.set_size_request(36, 36)
        spinner.start()
        loading = Adw.StatusPage(
            icon_name="input-gaming-symbolic",
            title=tr("Leyendo dispositivos guardados…"),
        )
        loading.set_child(spinner)
        self.stack.add_named(loading, "loading")

        self.empty_page = Adw.StatusPage(
            icon_name="input-gaming-symbolic",
            title=tr("No hay dispositivos guardados"),
            description=tr(
                "Cuando instales una regla para un mando, la aplicación guarda "
                "su última regla acá.  Después podés activarla o desactivarla "
                "sin volver a conectarlo."
            ),
        )
        self.stack.add_named(self.empty_page, "empty")

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(660)
        clamp.set_tightening_threshold(560)
        clamp.set_hexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(18)
        content.set_margin_bottom(24)
        content.set_margin_start(18)
        content.set_margin_end(18)

        self.master_group = Adw.PreferencesGroup()
        self.master_row = Adw.SwitchRow(title=tr("Activar todos"))
        self.master_row.connect("notify::active", self._on_master_toggled)
        self.master_group.add(self.master_row)
        self.master_group.set_visible(False)
        content.append(self.master_group)

        self.group = Adw.PreferencesGroup(
            title=tr("Dispositivos guardados"),
            description=tr(
                "Cada interruptor de la lista instala o elimina la regla "
                "guardada de ese dispositivo.  La metadata y el contenido se "
                "conservan en "
                "devices.json aunque el mando esté desconectado."
            ),
        )
        self.group.set_hexpand(True)
        content.append(self.group)

        clamp.set_child(content)
        scroller.set_child(clamp)
        self.stack.add_named(scroller, "list")
        toolbar.set_content(self.stack)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bottom.set_margin_top(10)
        bottom.set_margin_bottom(10)
        bottom.set_margin_start(14)
        bottom.set_margin_end(14)
        self.status = Gtk.Label(label="", xalign=0)
        self.status.set_hexpand(True)
        self.status.add_css_class("dim-label")
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        bottom.append(self.status)
        bottom.append(self.spinner)
        toolbar.add_bottom_bar(bottom)
        self.set_child(toolbar)

    def _load(self) -> None:
        self.stack.set_visible_child_name("loading")
        self.status.set_text("")
        thread = threading.Thread(
            target=self._load_worker,
            name="udev-rule-generator-known-load",
            daemon=True,
        )
        thread.start()

    def _load_worker(self) -> None:
        try:
            rules = list_installed_rules(self.host)
            self.store.reconcile(rules)
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._load_failed, str(exc))
            return
        GLib.idle_add(self._load_succeeded)

    def _load_succeeded(self) -> bool:
        self._reload()
        self.status.set_text("")
        return False

    def _load_failed(self, message: str) -> bool:
        self._reload()
        self.status.set_text(
            tr(
                "No se pudieron leer las reglas instaladas: {error}",
                error=message,
            )
        )
        return False

    def _reload(self) -> None:
        self._updating = True
        for row in self._rows:
            self.group.remove(row)
        self._rows.clear()

        devices = self.store.devices()
        for device in devices:
            self.group.add(self._device_row(device))
        self.master_group.set_visible(bool(devices))
        self._update_master(devices)
        self.stack.set_visible_child_name("list" if devices else "empty")
        self._updating = False

    def _update_master(self, devices: list[KnownDevice]) -> None:
        count = len(devices)
        active = sum(1 for device in devices if device.active)
        missing = count - active
        self.master_row.set_active(bool(devices) and missing == 0)
        if not devices:
            subtitle = ""
        elif missing == 0:
            subtitle = tr("Todos activos ({count})", count=count)
        elif active == 0:
            subtitle = tr("Ninguno activo ({count})", count=count)
        elif missing == 1:
            subtitle = tr(
                "{active} de {count} activos · falta 1",
                active=active,
                count=count,
            )
        else:
            subtitle = tr(
                "{active} de {count} activos · faltan {missing}",
                active=active,
                count=count,
                missing=missing,
            )
        self.master_row.set_subtitle(subtitle)

    def _device_row(self, device: KnownDevice) -> Adw.SwitchRow:
        state = tr("Activa") if device.active else tr("Desactivada")
        details = [
            state,
            device.bus_label,
            device.identifier,
            device.action_label,
        ]
        if self.connected_ids is not None:
            if device.id in self.connected_ids:
                details.append(tr("Conectado"))
            else:
                details.append(tr("No conectado"))
        row = Adw.SwitchRow(
            title=device.name,
            subtitle=" · ".join(details),
        )
        row.set_tooltip_text(device.filename)
        row.set_active(device.active)
        row.connect(
            "notify::active",
            lambda selected_row, _pspec, selected=device: self._toggle(
                selected, selected_row.get_active()
            ),
        )

        icon = Gtk.Image(icon_name="input-gaming-symbolic")
        icon.add_css_class("dim-label")
        icon.set_valign(Gtk.Align.CENTER)
        row.add_prefix(icon)
        self._rows.append(row)
        return row

    def _on_master_toggled(self, row: Adw.SwitchRow, _pspec) -> None:
        if self._updating or self._busy:
            return
        activate = row.get_active()
        devices = self.store.devices()
        targets = [
            device for device in devices if device.active != activate
        ]
        if not targets:
            self._reload()
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
                files = {
                    spec.filename: spec.content
                    for _device, spec in specs
                }
                trigger = (
                    "add"
                    if any(
                        spec.trigger == "add"
                        for _device, spec in specs
                    )
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
                        "  "
                        + tr(
                            "No se pudo guardar el estado: {error}",
                            error=exc,
                        )
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
                        "  "
                        + tr(
                            "No se pudo guardar el estado: {error}",
                            error=exc,
                        )
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
            return tr(
                "Se activaron {count} dispositivos.", count=count
            )
        if count == 1:
            return tr("Se desactivó {count} dispositivo.", count=count)
        return tr("Se desactivaron {count} dispositivos.", count=count)

    def _master_succeeded(self, message: str) -> bool:
        self._set_busy(False)
        self._reload()
        self.on_changed(message)
        return False

    def _master_failed(self, message: str) -> bool:
        self._set_busy(False)
        self._reload()
        dialog = Adw.AlertDialog(
            heading=tr("No se pudieron cambiar los dispositivos guardados"),
            body=message,
        )
        dialog.add_response("close", tr("Cerrar"))
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)
        return False

    def _toggle(self, device: KnownDevice, active: bool) -> None:
        if self._updating or self._busy or active == device.active:
            return
        self._set_busy(True)
        thread = threading.Thread(
            target=self._toggle_worker,
            args=(device, active),
            name="udev-rule-generator-known",
            daemon=True,
        )
        thread.start()

    def _toggle_worker(self, device: KnownDevice, active: bool) -> None:
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
            GLib.idle_add(self._toggle_failed, str(exc))
            return
        GLib.idle_add(self._toggle_succeeded, message)

    def _toggle_succeeded(self, message: str) -> bool:
        self._set_busy(False)
        self._reload()
        self.on_changed(message)
        return False

    def _toggle_failed(self, message: str) -> bool:
        self._set_busy(False)
        self._reload()
        dialog = Adw.AlertDialog(
            heading=tr("No se pudo cambiar la regla guardada"),
            body=message,
        )
        dialog.add_response("close", tr("Cerrar"))
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)
        return False

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.master_row.set_sensitive(not busy)
        for row in self._rows:
            row.set_sensitive(not busy)
        self.spinner.set_visible(busy)
        if busy:
            self.spinner.start()
            self.status.set_text(
                tr("Esperando el diálogo de autenticación de GNOME/polkit…")
            )
            return
        self.spinner.stop()
        self.status.set_text("")
