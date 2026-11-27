"""Ventana principal de la GUI."""

from __future__ import annotations

import threading
from datetime import datetime

from udev_rule_generator import APP_NAME
from udev_rule_generator.backup import (
    BackupError,
    BackupInfo,
    ImportResult,
    create_backup,
)
from udev_rule_generator.backup import import_backup as restore_backup
from udev_rule_generator.devices import Detection, Joystick, detect_state
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.installed import list_installed_rules
from udev_rule_generator.known import KnownDevices
from udev_rule_generator.monitor import UdevMonitor
from udev_rule_generator.privileged import (
    HidBindingChange,
    apply_rule_changes,
)
from udev_rule_generator.steam import steam_running
from udev_rule_generator.uinput import uinput_available

from .device_manager import DeviceManager
from .gi_compat import Adw, Gio, GLib, Gtk, markup_escape
from .test_mode import test_mode_enabled


class MainWindow(Adw.ApplicationWindow):
    """Gestiona las reglas de los dispositivos y los paquetes externos."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.host = Host()
        self.known_store = KnownDevices()
        self._closed = False
        self._refresh_generation = 0
        self._detection_pending = False
        self._first_detection = True
        self._devices: list[Joystick] = []
        self._auto_refresh_source = 0
        self._poll_source = 0
        self._monitor: UdevMonitor | None = None
        self._hidden_dialog = None
        self._test_dialog = None
        self._emoji_dialog = None
        self._file_dialog = None
        self._backup_busy = False

        self.set_title(tr(APP_NAME))
        self.set_default_size(780, 760)
        self._build_ui()
        self.connect("close-request", self._on_close)

        self._monitor = UdevMonitor(
            self.host,
            self._on_udev_event,
            self._on_monitor_failed,
        )
        self._monitor.start()
        # Respaldo por si udevadm monitor no está disponible en el host.
        self._poll_source = GLib.timeout_add_seconds(5, self._poll_devices)
        self.refresh()
        self._refresh_rule_metadata()

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title=tr(APP_NAME))
        header.set_title_widget(self.window_title)

        menu = Gio.Menu()
        menu.append(tr("Exportar"), "app.export")
        menu.append(tr("Importar"), "app.import")
        menu.append(tr("Dispositivos ocultos"), "app.hidden")
        menu.append(tr("Test de reglas"), "app.test")
        if test_mode_enabled():
            menu.append(tr("Ver emoji"), "app.emoji")
        menu.append(tr("Acerca de"), "app.about")
        menu.append(tr("Eliminar todos los datos"), "app.clear")
        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=menu,
            tooltip_text=tr("Menú principal"),
        )
        menu_button.add_css_class("flat")
        header.pack_end(menu_button)

        toolbar.add_top_bar(header)

        self.toast_overlay = Adw.ToastOverlay()

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(18)
        content.set_margin_bottom(24)
        content.set_margin_start(18)
        content.set_margin_end(18)

        self.manager = DeviceManager(
            host=self.host,
            store=self.known_store,
            parent=self,
            on_changed=self._on_known_changed,
        )
        toolbar.add_bottom_bar(self.manager.action_bar)
        content.append(self.manager)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(720)
        clamp.set_tightening_threshold(600)
        clamp.set_hexpand(True)
        clamp.set_child(content)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)
        scroller.set_child(clamp)

        self.toast_overlay.set_child(scroller)
        toolbar.set_content(self.toast_overlay)
        self.set_content(toolbar)

    def refresh(self, *, silent: bool = False, notify: bool = True) -> None:
        """Vuelve a detectar joysticks en segundo plano."""
        if self._closed:
            return
        if silent and self._detection_pending:
            return
        self._refresh_generation += 1
        generation = self._refresh_generation
        self._detection_pending = True

        def worker() -> None:
            error: Exception | None = None
            detection = Detection(joysticks=[], hid_devices=[])
            steam = False
            try:
                detection = detect_state(self.host)
                steam = steam_running(self.host)
            except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
                error = exc
            GLib.idle_add(
                self._apply_detection,
                detection,
                error,
                generation,
                silent,
                notify,
                steam,
            )

        threading.Thread(
            target=worker,
            name="udev-rule-generator-detect",
            daemon=True,
        ).start()

    def _apply_detection(
        self,
        detection: Detection,
        error: Exception | None,
        generation: int,
        silent: bool,
        notify: bool = True,
        steam: bool = False,
    ) -> bool:
        if self._closed or generation != self._refresh_generation:
            return False
        self._detection_pending = False
        if error is not None:
            if not silent:
                self.show_error(
                    tr("No se pudieron detectar joysticks"),
                    tr(
                        "{error}\n\nRevisá que udev esté funcionando y que la "
                        "aplicación tenga acceso al host.",
                        error=error,
                    ),
                )
            return False

        devices = detection.joysticks
        previous_devices = list(self._devices)
        previous_keys = {device.key for device in previous_devices}
        new_keys = {device.key for device in devices}
        added = [device for device in devices if device.key not in previous_keys]
        removed = [
            device
            for device in previous_devices
            if device.key not in new_keys
        ]

        self._devices = devices
        self.manager.set_connected_devices(devices)
        self.manager.set_hid_devices(detection.hid_devices)
        self.manager.set_usb_devices(detection.usb_devices)

        if notify and not self._first_detection and not steam:
            for device in added:
                if self._should_notify(device):
                    self._notify_device(device, connected=True)
            for device in removed:
                if self._should_notify(device):
                    self._notify_device(device, connected=False)
        self._first_detection = False
        return False

    @staticmethod
    def _should_notify(device: Joystick) -> bool:
        if device.is_ignorable:
            return False
        return bool(device.vendor_id and device.product_id)

    def _notify_device(self, device: Joystick, *, connected: bool) -> None:
        app = self.get_application()
        if app is None:
            return
        display_name = " ".join(device.display_name.split())
        title = (
            tr("Joystick conectado")
            if connected
            else tr("Joystick desconectado")
        )
        notification = Gio.Notification.new(title)
        notification.set_body(
            f"{display_name} · {device.bus_label} · {device.identifier}"
        )
        notification.set_icon(Gio.ThemedIcon.new("input-gaming-symbolic"))
        notification.set_priority(Gio.NotificationPriority.NORMAL)
        notification.set_default_action("app.show")
        state = "connected" if connected else "disconnected"
        app.send_notification(
            f"joystick-{state}-{abs(hash(device.key))}",
            notification,
        )

    def _on_udev_event(self, _event: dict[str, str]) -> None:
        """Se llama desde el hilo del monitor udev."""
        if self._closed:
            return
        GLib.idle_add(self._schedule_auto_refresh)

    def _schedule_auto_refresh(self) -> bool:
        if self._closed:
            return False
        if self._auto_refresh_source:
            GLib.source_remove(self._auto_refresh_source)
        self._auto_refresh_source = GLib.timeout_add(350, self._auto_refresh)
        return False

    def _auto_refresh(self) -> bool:
        self._auto_refresh_source = 0
        self.refresh(silent=True)
        return False

    def _poll_devices(self) -> bool:
        if self._closed:
            return False
        self.refresh(silent=True)
        return True

    def _on_monitor_failed(self) -> None:
        # El sondeo de respaldo sigue activo; no hace falta molestar al usuario.
        pass

    def show_hidden_devices(self) -> None:
        if self._closed:
            return
        # Create a fresh window every time. Reusing an Adw.Window after it
        # has been destroyed leaves GTK in an inconsistent state and freezes.
        previous = self._hidden_dialog
        self._hidden_dialog = None
        if previous is not None:
            try:
                if previous.get_realized():
                    previous.destroy()
            except Exception:
                pass
        from .hidden_dialog import HiddenDevicesDialog

        self._hidden_dialog = HiddenDevicesDialog(
            store=self.known_store,
            parent=self,
            on_changed=self._on_hidden_changed,
        )
        self._hidden_dialog.connect("close-request", self._on_hidden_close)
        self._hidden_dialog.connect("destroy", self._on_hidden_destroyed)
        self._hidden_dialog.present()

    def _on_hidden_close(self, dialog) -> bool:
        if self._hidden_dialog is dialog:
            self._hidden_dialog = None
        return False

    def _on_hidden_destroyed(self, _dialog) -> None:
        self._hidden_dialog = None

    def show_rules_test(self) -> None:
        if self._closed:
            return
        previous = self._test_dialog
        self._test_dialog = None
        if previous is not None:
            try:
                if previous.get_realized():
                    previous.destroy()
            except Exception:
                pass
        from .rules_test_dialog import RulesTestDialog

        self._test_dialog = RulesTestDialog(
            host=self.host,
            store=self.known_store,
            parent=self,
        )
        self._test_dialog.connect("close-request", self._on_test_close)
        self._test_dialog.connect("destroy", self._on_test_destroyed)
        self._test_dialog.present()

    def _on_test_close(self, dialog) -> bool:
        if self._test_dialog is dialog:
            self._test_dialog = None
        return False

    def _on_test_destroyed(self, _dialog) -> None:
        self._test_dialog = None

    def show_emoji_catalog(self) -> None:
        if self._closed:
            return
        previous = self._emoji_dialog
        self._emoji_dialog = None
        if previous is not None:
            try:
                if previous.get_realized():
                    previous.destroy()
            except Exception:
                pass
        from .emoji_dialog import EmojiCatalogDialog

        self._emoji_dialog = EmojiCatalogDialog(parent=self)
        self._emoji_dialog.connect(
            "close-request", self._on_emoji_close
        )
        self._emoji_dialog.connect("destroy", self._on_emoji_destroyed)
        self._emoji_dialog.present()

    def _on_emoji_close(self, dialog) -> bool:
        if self._emoji_dialog is dialog:
            self._emoji_dialog = None
        return False

    def _on_emoji_destroyed(self, _dialog) -> None:
        self._emoji_dialog = None

    def _on_hidden_changed(self, message: str) -> None:
        self.add_toast(message)
        self.manager.reload()

    def _on_known_changed(self, message: str) -> None:
        if message:
            self.add_toast(message)
        self._refresh_rule_metadata()
        if message:
            GLib.timeout_add(1200, self._refresh_after_change)
        else:
            # Cambio de conexión desde el botón Conectar/Desconectar:
            # permitimos que el diff de detección anuncie por GNOME.
            GLib.timeout_add(1200, self._refresh_after_connection_change)

    def _refresh_after_connection_change(self) -> bool:
        self.refresh(silent=True)
        return False

    def _backup_filters(self) -> Gio.ListStore:
        filters = Gio.ListStore.new(Gtk.FileFilter)
        backup_filter = Gtk.FileFilter()
        backup_filter.set_name(tr("Copias de seguridad (.tar.gz)"))
        backup_filter.add_pattern("*.tar.gz")
        backup_filter.add_pattern("*.tgz")
        filters.append(backup_filter)
        all_filter = Gtk.FileFilter()
        all_filter.set_name(tr("Todos los archivos"))
        all_filter.add_pattern("*")
        filters.append(all_filter)
        return filters

    def _backup_dialog(self, title: str) -> Gtk.FileDialog:
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        dialog.set_modal(True)
        filters = self._backup_filters()
        dialog.set_filters(filters)
        dialog.set_default_filter(filters.get_item(0))
        self._file_dialog = dialog
        return dialog

    def export_backup(self) -> None:
        if self._closed or self._backup_busy or self._file_dialog is not None:
            return
        dialog = self._backup_dialog(tr("Exportar copia de seguridad"))
        dialog.set_initial_name(
            f"udev-rule-generator-backup-{datetime.now():%Y-%m-%d}.tar.gz"
        )
        dialog.set_accept_label(tr("Exportar"))
        dialog.save(self, None, self._on_export_chosen)

    def _on_export_chosen(self, dialog, result, *_args) -> None:
        self._file_dialog = None
        try:
            destination = dialog.save_finish(result)
        except GLib.Error:
            return
        if destination is None:
            return
        self._backup_busy = True
        self.add_toast(tr("Exportando copia de seguridad…"))
        threading.Thread(
            target=self._export_worker,
            args=(destination,),
            name="udev-rule-generator-export",
            daemon=True,
        ).start()

    def _export_worker(self, destination: Gio.File) -> None:
        try:
            data, info = create_backup(self.host, self.known_store)
            try:
                success, _etag = destination.replace_contents(
                    data,
                    None,
                    False,
                    Gio.FileCreateFlags.REPLACE_DESTINATION,
                    None,
                )
            except GLib.Error as exc:
                raise BackupError(str(exc)) from exc
            if not success:
                raise BackupError(
                    tr("No se pudo escribir el archivo de copia de seguridad.")
                )
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._export_failed, str(exc))
            return
        GLib.idle_add(
            self._export_finished,
            info,
            destination.get_basename() or "",
        )

    def _export_failed(self, message: str) -> bool:
        if self._closed:
            return False
        self._backup_busy = False
        self.show_error(
            tr("No se pudo exportar la copia de seguridad"),
            message,
        )
        return False

    def _export_finished(
        self,
        _info: BackupInfo,
        filename: str,
    ) -> bool:
        if self._closed:
            return False
        self._backup_busy = False
        self.add_toast(
            tr(
                "Copia de seguridad exportada: {filename}",
                filename=filename or tr("archivo .tar.gz"),
            )
        )
        return False

    def import_backup(self) -> None:
        if self._closed or self._backup_busy or self._file_dialog is not None:
            return
        dialog = self._backup_dialog(tr("Importar copia de seguridad"))
        dialog.set_accept_label(tr("Importar"))
        dialog.open(self, None, self._on_import_chosen)

    def _on_import_chosen(self, dialog, result, *_args) -> None:
        self._file_dialog = None
        try:
            source = dialog.open_finish(result)
        except GLib.Error:
            return
        if source is None:
            return
        try:
            success, contents, _etag = source.load_contents(None)
        except GLib.Error as exc:
            self.show_error(
                tr("No se pudo importar la copia de seguridad"),
                str(exc),
            )
            return
        if not success or not contents:
            self.show_error(
                tr("No se pudo importar la copia de seguridad"),
                tr("No se pudo leer el archivo de copia de seguridad."),
            )
            return
        self._backup_busy = True
        self.add_toast(tr("Importando copia de seguridad…"))
        threading.Thread(
            target=self._import_worker,
            args=(bytes(contents),),
            name="udev-rule-generator-import",
            daemon=True,
        ).start()

    def _import_worker(self, contents: bytes) -> None:
        try:
            result = restore_backup(self.host, self.known_store, contents)
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._import_failed, str(exc))
            return
        GLib.idle_add(self._import_finished, result)

    def _import_failed(self, message: str) -> bool:
        if self._closed:
            return False
        self._backup_busy = False
        self.show_error(
            tr("No se pudo importar la copia de seguridad"),
            message,
        )
        return False

    def _import_finished(self, result: ImportResult) -> bool:
        if self._closed:
            return False
        self._backup_busy = False
        self.manager.reload()
        if self._hidden_dialog is not None:
            try:
                self._hidden_dialog.reload()
            except Exception:
                pass
        self._refresh_rule_metadata()
        GLib.timeout_add(1200, self._refresh_after_change)
        self.add_toast(
            tr(
                "Datos importados: {devices} dispositivos y {aliases} "
                "alias. Ninguna regla fue activada.",
                devices=result.devices,
                aliases=result.aliases,
            )
        )
        return False

    def clear_all_data(self) -> None:
        if self._closed or self._backup_busy or self._file_dialog is not None:
            return
        dialog = Adw.AlertDialog(
            heading=tr("¿Eliminar todos los datos?"),
            body=tr(
                "Se eliminarán los dispositivos guardados, sus alias, las "
                "reglas generadas y el estado de los dispositivos ocultos. "
                "Las reglas de steam-devices y game-devices-udev no se "
                "modifican. Esta acción no se puede deshacer."
            ),
        )
        dialog.add_response("cancel", tr("Cancelar"))
        dialog.add_response("clear", tr("Eliminar todos los datos"))
        dialog.set_response_appearance(
            "clear", Adw.ResponseAppearance.DESTRUCTIVE
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_clear_response)
        dialog.present(self)

    def _on_clear_response(self, _dialog, response: str) -> None:
        if response != "clear" or self._backup_busy:
            return
        self._backup_busy = True
        self.add_toast(tr("Eliminando todos los datos…"))
        threading.Thread(
            target=self._clear_worker,
            name="udev-rule-generator-clear",
            daemon=True,
        ).start()

    def _clear_worker(self) -> None:
        try:
            rules = list_installed_rules(self.host)
            filenames = sorted(
                {
                    rule.filename
                    for rule in rules
                    if rule.kind == "generated"
                }
            )
            hid_changes = [
                HidBindingChange(
                    record.vendor_id,
                    record.product_id,
                    bound=True,
                    driver=record.hid_driver or "hid-generic",
                )
                for record in self.known_store.devices()
                if record.ignored
                and record.vendor_id
                and record.product_id
            ]
            if filenames or hid_changes:
                apply_rule_changes(
                    self.host,
                    {},
                    filenames,
                    hid_changes=hid_changes,
                )
            self.known_store.clear_all()
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._clear_failed, str(exc))
            return
        GLib.idle_add(self._clear_finished)

    def _clear_failed(self, message: str) -> bool:
        if self._closed:
            return False
        self._backup_busy = False
        self.show_error(
            tr("No se pudieron eliminar todos los datos"),
            message,
        )
        return False

    def _clear_finished(self) -> bool:
        if self._closed:
            return False
        self._backup_busy = False
        self.manager.reset_after_clear()
        if self._hidden_dialog is not None:
            try:
                self._hidden_dialog.reload()
            except Exception:
                pass
        self._refresh_rule_metadata()
        GLib.timeout_add(1200, self._refresh_after_change)
        self.add_toast(tr("Todos los datos fueron eliminados."))
        return False

    def _refresh_rule_metadata(self) -> None:
        if self._closed:
            return

        def worker() -> None:
            rules = []
            error = None
            available = True
            try:
                rules = list_installed_rules(self.host)
                available = uinput_available(self.host)
            except Exception as exc:  # noqa: BLE001 (contador no crítico)
                error = exc
            GLib.idle_add(
                self._apply_rule_metadata,
                rules,
                error,
                available,
            )

        threading.Thread(
            target=worker,
            name="udev-rule-generator-metadata",
            daemon=True,
        ).start()

    def _apply_rule_metadata(
        self,
        rules: list,
        error: Exception | None = None,
        uinput_ready: bool = True,
    ) -> bool:
        if self._closed or error is not None:
            return False

        try:
            self.known_store.reconcile(rules)
        except OSError:
            # El registro es auxiliar; un fallo de escritura no debe romper la
            # ventana principal.
            pass
        self.manager.set_uinput_available(uinput_ready)
        self.manager.set_installed_rules(rules)
        self.manager.reload()
        return False

    def _on_rule_installed(self, message: str) -> None:
        self.add_toast(message)
        self.manager.reload()
        self._refresh_rule_metadata()
        # Si se ignoró un dispositivo, udev puede tardar un instante en
        # retirarlo; refrescar un poco después da una lista más realista.
        GLib.timeout_add(1200, self._refresh_after_change)

    def _refresh_after_change(self) -> bool:
        self.refresh(silent=True, notify=False)
        return False

    def add_toast(self, message: str) -> None:
        self.toast_overlay.add_toast(
            Adw.Toast(title=markup_escape(message), timeout=5)
        )

    def show_error(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", tr("Cerrar"))
        dialog.present(self)

    def shutdown(self) -> None:
        """Detiene el monitor, los timers y el executor una sola vez."""
        if self._closed:
            return
        self._closed = True
        if self._monitor is not None:
            self._monitor.stop()
        if self._poll_source:
            GLib.source_remove(self._poll_source)
            self._poll_source = 0
        if self._auto_refresh_source:
            GLib.source_remove(self._auto_refresh_source)
            self._auto_refresh_source = 0

    def _on_close(self, _window) -> bool:
        self.shutdown()
        return False
