"""Ventana principal de la GUI."""

from __future__ import annotations

import threading

from udev_rule_generator import APP_NAME
from udev_rule_generator.devices import Joystick, detect_joysticks
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.installed import list_installed_rules
from udev_rule_generator.known import KnownDevices
from udev_rule_generator.monitor import UdevMonitor

from .device_manager import DeviceManager
from .gi_compat import Adw, Gio, GLib, Gtk


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
        menu.append(tr("Acerca de"), "app.about")
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
            devices: list[Joystick] = []
            try:
                devices = detect_joysticks(self.host)
            except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
                error = exc
            GLib.idle_add(
                self._apply_detection,
                devices,
                error,
                generation,
                silent,
                notify,
            )

        threading.Thread(
            target=worker,
            name="udev-rule-generator-detect",
            daemon=True,
        ).start()

    def _apply_detection(
        self,
        devices: list[Joystick],
        error: Exception | None,
        generation: int,
        silent: bool,
        notify: bool = True,
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

        previous_keys = {device.key for device in self._devices}
        added = [device for device in devices if device.key not in previous_keys]

        self._devices = devices
        self.manager.set_connected_devices(devices)

        if notify and not self._first_detection:
            for device in added:
                self._notify_device(device)
        self._first_detection = False
        return False

    def _notify_device(self, device: Joystick) -> None:
        app = self.get_application()
        if app is None:
            return
        display_name = " ".join(device.display_name.split())
        notification = Gio.Notification.new(tr("Joystick conectado"))
        notification.set_body(
            f"{display_name} · {device.bus_label} · {device.identifier}"
        )
        notification.set_icon(Gio.ThemedIcon.new("input-gaming-symbolic"))
        notification.set_priority(Gio.NotificationPriority.NORMAL)
        notification.set_default_action("app.show")
        app.send_notification(
            f"joystick-connected-{abs(hash(device.key))}",
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

    def _on_known_changed(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=5))
        self._refresh_rule_metadata()
        GLib.timeout_add(1200, self._refresh_after_change)

    def _refresh_rule_metadata(self) -> None:
        if self._closed:
            return

        def worker() -> None:
            rules = []
            error = None
            try:
                rules = list_installed_rules(self.host)
            except Exception as exc:  # noqa: BLE001 (contador no crítico)
                error = exc
            GLib.idle_add(self._apply_rule_metadata, rules, error)

        threading.Thread(
            target=worker,
            name="udev-rule-generator-metadata",
            daemon=True,
        ).start()

    def _apply_rule_metadata(
        self, rules: list, error: Exception | None = None
    ) -> bool:
        if self._closed or error is not None:
            return False

        try:
            self.known_store.reconcile(rules)
        except OSError:
            # El registro es auxiliar; un fallo de escritura no debe romper la
            # ventana principal.
            pass
        self.manager.set_installed_rules(rules)
        self.manager.reload()
        return False

    def _on_rule_installed(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=5))
        self.manager.reload()
        self._refresh_rule_metadata()
        # Si se ignoró un dispositivo, udev puede tardar un instante en
        # retirarlo; refrescar un poco después da una lista más realista.
        GLib.timeout_add(1200, self._refresh_after_change)

    def _refresh_after_change(self) -> bool:
        self.refresh(silent=True, notify=False)
        return False

    def add_toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=5))

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
