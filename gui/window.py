"""Ventana principal de la GUI."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from udev_rule_generator import APP_NAME
from udev_rule_generator.devices import Joystick, detect_joysticks
from udev_rule_generator.host import Host

from .gi_compat import Adw, Gio, GLib, Gtk


class MainWindow(Adw.ApplicationWindow):
    """Lista los joysticks y permite configurarlos."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.host = Host()
        self._executor = ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="udev-rule-generator"
        )
        self._closed = False
        self._refresh_generation = 0
        self._devices: list[Joystick] = []
        self._device_rows: list[Adw.ActionRow] = []

        self.set_title(APP_NAME)
        self.set_default_size(780, 760)
        self._build_ui()
        self.connect("close-request", self._on_close)
        self.refresh()

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        title = Adw.WindowTitle(
            title=APP_NAME,
            subtitle="Permitir o ignorar mandos conectados",
        )
        header.set_title_widget(title)

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
        page = Adw.StatusPage(
            icon_name="input-gaming-symbolic",
            title="No hay joysticks conectados",
            description=(
                "Conectá un mando por USB o Bluetooth y actualizá.  Si ya está "
                "conectado, revisá que el sistema lo detecte con "
                "«udevadm info --export-db»."
            ),
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

        page = Adw.PreferencesPage()
        page.set_vexpand(True)

        self.devices_group = Adw.PreferencesGroup(
            title="Joysticks detectados",
            description=(
                "Elegí un dispositivo para crear una regla udev que lo permita "
                "o que lo ignore.  Las reglas se instalan en "
                "/etc/udev/rules.d con prioridad 10- para permitir y 99- para "
                "ignorar."
            ),
        )
        page.add(self.devices_group)

        actions_group = Adw.PreferencesGroup(title="Más acciones")
        actions_group.add(
            self._action_row(
                "Reglas preconfiguradas",
                "Microsoft Xbox, game-devices-udev y ASRock opcional.",
                "app.presets",
            )
        )
        actions_group.add(
            self._action_row(
                "Reglas instaladas",
                "Ver o eliminar las reglas creadas por esta aplicación.",
                "app.installed",
            )
        )
        actions_group.add(
            self._action_row(
                "Acerca de",
                "Versión, licencia y enlaces del proyecto.",
                "app.about",
            )
        )
        page.add(actions_group)
        box.append(page)
        self.stack.add_named(box, "list")

    @staticmethod
    def _action_row(title: str, subtitle: str, action: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.set_activatable(True)
        row.connect("activated", lambda *_: row.activate_action(action, None))
        icon = Gtk.Image(icon_name="go-next-symbolic")
        icon.add_css_class("dim-label")
        row.add_suffix(icon)
        return row

    def _set_state(self, name: str) -> None:
        self.stack.set_visible_child_name(name)

    def refresh(self) -> None:
        """Vuelve a detectar joysticks en segundo plano."""
        if self._closed:
            return
        self._refresh_generation += 1
        generation = self._refresh_generation
        self.banner.set_revealed(False)
        self._set_state("loading")
        future = self._executor.submit(detect_joysticks, self.host)
        future.add_done_callback(
            lambda completed: GLib.idle_add(
                self._apply_detection, completed, generation
            )
        )

    def _apply_detection(self, future: Future, generation: int) -> bool:
        if self._closed or generation != self._refresh_generation:
            return False
        try:
            devices = future.result()
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            self._set_state("empty")
            self.show_error(
                "No se pudieron detectar joysticks",
                f"{exc}\n\nRevisá que udev esté funcionando y que la aplicación "
                "tenga acceso al host.",
            )
            return False

        self._devices = devices
        self._populate(devices)
        if devices:
            self._set_state("list")
        else:
            self._set_state("empty")
        return False

    def _populate(self, devices: list[Joystick]) -> None:
        for row in self._device_rows:
            self.devices_group.remove(row)
        self._device_rows.clear()

        for device in devices:
            row = Adw.ActionRow(
                title=device.display_name,
                subtitle=f"{device.hardware_label} · {device.nodes_label}",
            )
            row.set_activatable(True)
            row.connect(
                "activated",
                lambda _row, selected=device: self._open_device(selected),
            )
            icon = Gtk.Image(icon_name="input-gaming-symbolic")
            icon.add_css_class("dim-label")
            row.add_prefix(icon)

            badge = Gtk.Label(label=device.bus_label)
            badge.add_css_class("dim-label")
            badge.add_css_class("caption")
            badge.set_valign(Gtk.Align.CENTER)
            row.add_suffix(badge)

            arrow = Gtk.Image(icon_name="go-next-symbolic")
            arrow.add_css_class("dim-label")
            row.add_suffix(arrow)
            self.devices_group.add(row)
            self._device_rows.append(row)

    def _open_device(self, device: Joystick) -> None:
        from .device_dialog import DeviceDialog

        dialog = DeviceDialog(
            device=device,
            host=self.host,
            parent=self,
            on_installed=self._on_rule_installed,
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

    def _on_rule_installed(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=5))
        # Si se ignoró un dispositivo, udev puede tardar un instante en
        # retirarlo; refrescar un poco después da una lista más realista.
        GLib.timeout_add(1200, self._refresh_after_change)

    def _refresh_after_change(self) -> bool:
        self.refresh()
        return False

    def add_toast(self, message: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=message, timeout=5))

    def show_error(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", "Cerrar")
        dialog.present(self)

    def _on_close(self, _window) -> bool:
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
        return False
