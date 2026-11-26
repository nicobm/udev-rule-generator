"""Ventana principal de la GUI."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from udev_rule_generator import APP_NAME
from udev_rule_generator.devices import Joystick, detect_joysticks
from udev_rule_generator.hidden import HiddenDevices
from udev_rule_generator.host import Host
from udev_rule_generator.monitor import UdevMonitor

from .gi_compat import Adw, Gio, GLib, Gtk


class MainWindow(Adw.ApplicationWindow):
    """Lista los joysticks y permite configurarlos."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.host = Host()
        self.hidden_store = HiddenDevices()
        self._executor = ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="udev-rule-generator"
        )
        self._closed = False
        self._refresh_generation = 0
        self._detection_pending = False
        self._first_detection = True
        self._devices: list[Joystick] = []
        self._device_rows: list[Adw.ActionRow] = []
        self._auto_refresh_source = 0
        self._poll_source = 0
        self._monitor: UdevMonitor | None = None

        self.set_title(APP_NAME)
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

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(
            title=APP_NAME,
            subtitle="Buscando mandos…",
        )
        header.set_title_widget(self.window_title)

        refresh_button = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Buscar joysticks de nuevo (Ctrl+R)",
        )
        refresh_button.add_css_class("flat")
        refresh_button.connect("clicked", lambda *_: self.refresh())
        header.pack_start(refresh_button)

        menu = Gio.Menu()
        menu.append("Reglas preconfiguradas", "app.presets")
        menu.append("Reglas instaladas", "app.installed")
        menu.append("Dispositivos ocultos", "app.hidden")
        menu.append("Acerca de", "app.about")
        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=menu,
            tooltip_text="Menú principal",
        )
        menu_button.add_css_class("flat")
        header.pack_end(menu_button)

        toolbar.add_top_bar(header)

        self.toast_overlay = Adw.ToastOverlay()
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(180)

        self._build_loading_page()
        self._build_empty_page()
        self._build_list_page()
        self.toast_overlay.set_child(self.stack)
        toolbar.set_content(self.toast_overlay)
        self.set_content(toolbar)

    def _build_loading_page(self) -> None:
        spinner = Gtk.Spinner()
        spinner.set_size_request(36, 36)
        spinner.start()
        page = Adw.StatusPage(
            icon_name="input-gaming-symbolic",
            title="Buscando joysticks…",
            description="Consultando udev y los dispositivos de entrada del sistema.",
        )
        page.set_child(spinner)
        self.stack.add_named(page, "loading")

    def _build_empty_page(self) -> None:
        self._empty_description = (
            "Conectá un mando por USB o Bluetooth.  La ventana se actualiza "
            "sola y te avisa con una notificación cuando aparece.  Si ya está "
            "conectado, revisá que el sistema lo detecte con "
            "«udevadm info --export-db»."
        )
        page = Adw.StatusPage(
            icon_name="input-gaming-symbolic",
            title="No hay joysticks conectados",
            description=self._empty_description,
        )
        button = Gtk.Button(label="Buscar de nuevo")
        button.add_css_class("pill")
        button.add_css_class("suggested-action")
        button.set_halign(Gtk.Align.CENTER)
        button.connect("clicked", lambda *_: self.refresh())
        page.set_child(button)
        self.empty_page = page
        self.stack.add_named(page, "empty")

    def _build_list_page(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.banner = Adw.Banner()
        self.banner.set_revealed(False)
        box.append(self.banner)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(720)
        clamp.set_tightening_threshold(600)
        clamp.set_hexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(18)
        content.set_margin_bottom(24)
        content.set_margin_start(18)
        content.set_margin_end(18)

        self.devices_group = Adw.PreferencesGroup(
            title="Joysticks conectados",
            description=(
                "La lista se actualiza sola al conectar o desconectar un mando.  "
                "Elegí uno para crear su regla udev."
            ),
        )
        self.devices_group.set_hexpand(True)
        content.append(self.devices_group)

        status_group = Adw.PreferencesGroup(title="Estado")
        status_group.set_hexpand(True)
        status_group.add(
            self._status_row(
                "Detección automática",
                "Los mandos aparecen solos y se avisa con una notificación.",
                "object-select-symbolic",
                success=True,
            )
        )
        status_group.add(
            self._action_row(
                "Reglas preconfiguradas",
                "Microsoft Xbox, fabiscafe, Steam/SteamVR y ASRock opcional.",
                "app.presets",
                icon_name="application-x-addon-symbolic",
            )
        )
        status_group.add(
            self._action_row(
                "Reglas instaladas",
                "Ver o eliminar las reglas creadas por esta aplicación.",
                "app.installed",
                icon_name="document-open-symbolic",
            )
        )
        content.append(status_group)

        clamp.set_child(content)
        scroller.set_child(clamp)
        box.append(scroller)
        self.stack.add_named(box, "list")

    @staticmethod
    def _status_row(
        title: str,
        subtitle: str,
        icon_name: str,
        *,
        success: bool = False,
    ) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.set_activatable(False)
        icon = Gtk.Image(icon_name=icon_name)
        icon.add_css_class("success" if success else "dim-label")
        icon.set_valign(Gtk.Align.CENTER)
        row.add_prefix(icon)
        return row

    @staticmethod
    def _action_row(
        title: str,
        subtitle: str,
        action: str,
        *,
        icon_name: str | None = None,
    ) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.set_activatable(True)
        row.connect("activated", lambda *_: row.activate_action(action, None))
        if icon_name:
            prefix = Gtk.Image(icon_name=icon_name)
            prefix.add_css_class("dim-label")
            prefix.set_valign(Gtk.Align.CENTER)
            row.add_prefix(prefix)
        arrow = Gtk.Image(icon_name="go-next-symbolic")
        arrow.add_css_class("dim-label")
        row.add_suffix(arrow)
        return row

    @staticmethod
    def _device_badges(device: Joystick) -> list[str]:
        badges = [device.bus_label]
        if device.nodes:
            badges.append(device.nodes[0].rsplit("/", 1)[-1])
        return badges

    def _device_row(self, device: Joystick) -> Adw.ActionRow:
        details = [device.identifier]
        if device.serial:
            details.append(device.serial)
        row = Adw.ActionRow(
            title=device.display_name,
            subtitle=" · ".join(details),
        )
        row.set_activatable(True)
        row.set_tooltip_text(device.nodes_label)
        row.connect(
            "activated",
            lambda _row, selected=device: self._open_device(selected),
        )

        avatar = Gtk.CenterBox()
        avatar.set_size_request(46, 46)
        avatar.set_halign(Gtk.Align.CENTER)
        avatar.set_valign(Gtk.Align.CENTER)
        avatar.add_css_class("device-avatar")
        icon = Gtk.Image(icon_name="input-gaming-symbolic")
        icon.set_pixel_size(24)
        icon.set_halign(Gtk.Align.CENTER)
        icon.set_valign(Gtk.Align.CENTER)
        avatar.set_center_widget(icon)
        row.add_prefix(avatar)

        for text in self._device_badges(device):
            badge = Gtk.Label(label=text)
            badge.add_css_class("device-badge")
            badge.set_valign(Gtk.Align.CENTER)
            row.add_suffix(badge)

        arrow = Gtk.Image(icon_name="go-next-symbolic")
        arrow.add_css_class("dim-label")
        row.add_suffix(arrow)
        return row

    def _count_label(self, count: int) -> str:
        if count == 0:
            if len(self.hidden_store):
                return "Sin mandos visibles"
            return "Sin mandos conectados"
        if count == 1:
            return "1 mando detectado"
        return f"{count} mandos detectados"

    def _update_empty_page(self) -> None:
        count = len(self.hidden_store)
        if count:
            noun = "dispositivo oculto" if count == 1 else "dispositivos ocultos"
            self.empty_page.set_title("No hay joysticks visibles")
            self.empty_page.set_description(
                f"Tenés {count} {noun}.  Podés desocultarlos desde el menú "
                "→ Dispositivos ocultos."
            )
            return
        self.empty_page.set_title("No hay joysticks conectados")
        self.empty_page.set_description(self._empty_description)

    def _set_state(self, name: str) -> None:
        self.stack.set_visible_child_name(name)

    def refresh(self, *, silent: bool = False, notify: bool = True) -> None:
        """Vuelve a detectar joysticks en segundo plano."""
        if self._closed:
            return
        if silent and self._detection_pending:
            return
        self._refresh_generation += 1
        generation = self._refresh_generation
        self._detection_pending = True
        if not silent:
            self.banner.set_revealed(False)
            self._set_state("loading")
        future = self._executor.submit(detect_joysticks, self.host)
        future.add_done_callback(
            lambda completed: GLib.idle_add(
                self._apply_detection, completed, generation, silent, notify
            )
        )

    def _apply_detection(
        self,
        future: Future,
        generation: int,
        silent: bool,
        notify: bool = True,
    ) -> bool:
        if self._closed or generation != self._refresh_generation:
            return False
        self._detection_pending = False
        try:
            devices = future.result()
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            if not silent:
                self._set_state("empty")
                self._first_detection = False
                self.show_error(
                    "No se pudieron detectar joysticks",
                    f"{exc}\n\nRevisá que udev esté funcionando y que la "
                    "aplicación tenga acceso al host.",
                )
            return False

        devices = [
            device for device in devices if not self.hidden_store.is_hidden(device)
        ]
        previous_keys = {device.key for device in self._devices}
        previous_fingerprint = {
            (device.key, device.display_name, device.identifier)
            for device in self._devices
        }
        fingerprint = {
            (device.key, device.display_name, device.identifier)
            for device in devices
        }
        added = [device for device in devices if device.key not in previous_keys]

        self._devices = devices
        if not silent or fingerprint != previous_fingerprint:
            self._populate(devices)
            self._set_state("list" if devices else "empty")
        self._update_empty_page()

        if notify and not self._first_detection:
            for device in added:
                self._notify_device(device)
        self._first_detection = False
        return False

    def _populate(self, devices: list[Joystick]) -> None:
        for row in self._device_rows:
            self.devices_group.remove(row)
        self._device_rows.clear()

        for device in devices:
            row = self._device_row(device)
            self.devices_group.add(row)
            self._device_rows.append(row)

        self.window_title.set_subtitle(self._count_label(len(devices)))

    def _notify_device(self, device: Joystick) -> None:
        app = self.get_application()
        if app is None:
            return
        display_name = " ".join(device.display_name.split())
        notification = Gio.Notification.new("Joystick conectado")
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

    def _open_device(self, device: Joystick) -> None:
        from .device_dialog import DeviceDialog

        dialog = DeviceDialog(
            device=device,
            host=self.host,
            parent=self,
            hidden_store=self.hidden_store,
            on_installed=self._on_rule_installed,
            on_hidden=self._on_device_hidden,
        )
        dialog.present(self)

    def show_presets(self) -> None:
        from .presets_dialog import PresetsDialog

        dialog = PresetsDialog(
            host=self.host,
            parent=self,
            on_installed=self._on_rule_installed,
        )
        dialog.present(self)

    def show_installed(self) -> None:
        from .installed_dialog import InstalledDialog

        dialog = InstalledDialog(
            host=self.host,
            parent=self,
            on_changed=self._on_rule_installed,
        )
        dialog.present(self)

    def show_hidden(self) -> None:
        from .hidden_dialog import HiddenDialog

        dialog = HiddenDialog(
            store=self.hidden_store,
            parent=self,
            on_changed=self._on_hidden_changed,
        )
        dialog.present(self)

    def _on_device_hidden(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=5))
        self.refresh(silent=True, notify=False)

    def _on_hidden_changed(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=5))
        self.refresh(silent=True, notify=False)

    def _on_rule_installed(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=5))
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
        dialog.add_response("close", "Cerrar")
        dialog.present(self)

    def _on_close(self, _window) -> bool:
        self._closed = True
        if self._monitor is not None:
            self._monitor.stop()
        if self._poll_source:
            GLib.source_remove(self._poll_source)
            self._poll_source = 0
        if self._auto_refresh_source:
            GLib.source_remove(self._auto_refresh_source)
            self._auto_refresh_source = 0
        self._executor.shutdown(wait=False, cancel_futures=True)
        return False
