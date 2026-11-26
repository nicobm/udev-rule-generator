"""Lista principal de dispositivos, reglas guardadas y reglas de Steam."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator import GAME_DEVICES_URL, STEAM_DEVICES_URL
from udev_rule_generator.devices import HidDevice, Joystick
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.known import KnownDevice, KnownDevices
from udev_rule_generator.presets import (
    GAME_DEVICES,
    STEAM,
    preset_files,
    presets_trigger,
)
from udev_rule_generator.privileged import (
    HidBindingChange,
    apply_rule_changes,
    remove_rule_files,
)
from udev_rule_generator.rules import (
    RuleAction,
    build_rule,
    validate_rule_filename,
)
from udev_rule_generator.userconfig import device_identity

from .gi_compat import Adw, Gdk, GLib, GObject, Gtk, markup_escape

_DEVICE_ICON_CHOICES = (
    ("controller", "controller-symbolic", "Controller"),
    ("joystick", "joystick-symbolic", "Joystick"),
    ("gamepad", "input-gaming-symbolic", "Input gaming"),
    ("nintendo-switch", "nintendo-switch-symbolic", "Nintendo Switch"),
    ("playstation", "playstation-symbolic", "PlayStation"),
    ("xbox", "xbox-symbolic", "Xbox"),
    ("steam", "steam-symbolic", "Steam"),
    ("face-cool", "face-cool-symbolic", "Cara cool"),
    ("dpad", "dpad-symbolic", "D-pad"),
)
_DEVICE_ICONS = {
    icon_id: icon_name
    for icon_id, icon_name, _label in _DEVICE_ICON_CHOICES
}
_DEFAULT_DEVICE_ICON = "gamepad"
_DEVICE_COLOR_CHOICES = (
    ("red", "Rojo"),
    ("green", "Verde"),
    ("yellow", "Amarillo"),
    ("blue", "Azul"),
    ("magenta", "Magenta"),
    ("cyan", "Cian"),
    ("orange", "Naranja"),
    ("pink", "Rosa"),
    ("gray", "Gris"),
    ("white", "Blanco"),
)
_DEVICE_COLOR_IDS = tuple(color_id for color_id, _label in _DEVICE_COLOR_CHOICES)
_DEVICE_COLOR_ALIASES = {
    "black": "gray",
    "bright-black": "gray",
    "bright-red": "red",
    "bright-green": "green",
    "bright-yellow": "yellow",
    "bright-blue": "blue",
    "bright-magenta": "magenta",
    "bright-cyan": "cyan",
    "bright-white": "white",
}
_DEFAULT_DEVICE_COLOR = "white"


def _normalize_device_color(color_id: str) -> str:
    color_id = _DEVICE_COLOR_ALIASES.get(color_id, color_id)
    return color_id if color_id in _DEVICE_COLOR_IDS else _DEFAULT_DEVICE_COLOR


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
        self._hid_devices: dict[str, HidDevice] = {}
        self._hid_fingerprint: tuple = ()
        self._pending_known: dict[str, bool] = {}
        self._pending_unknown: dict[str, Joystick] = {}
        self._pending_ignored: dict[str, bool] = {}
        self._pending_ignored_joysticks: dict[str, Joystick] = {}
        self._ignored_actual: dict[str, bool] = {}
        self._pending_steam: bool | None = None
        self._pending_gdu: bool | None = None
        self._steam_installed = False
        self._gdu_installed = False
        self._steam_rule_count = 0
        self._gdu_rule_count = 0
        self._steam_rule_total = len(STEAM)
        self._gdu_rule_total = len(GAME_DEVICES)
        self._uinput_available = True
        self._rows: list[tuple[Adw.PreferencesGroup, Gtk.Widget]] = []
        self._row_identities: dict[Gtk.Widget, str] = {}
        self._live_order: list[str] = []
        self._animating_rows: set[str] = set()
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
        self.devices_overlay = Gtk.Overlay()
        self.devices_overlay.set_child(self.devices_group)
        self.preview_layer = Gtk.Fixed()
        self.preview_layer.set_can_target(False)
        self.preview_layer.set_hexpand(True)
        self.preview_layer.set_vexpand(True)
        self.devices_overlay.add_overlay(self.preview_layer)
        self.append(self.devices_overlay)
        self.devices_listbox = self._find_listbox(self.devices_group)
        if self.devices_listbox is not None:
            self.devices_listbox.set_sort_func(self._sort_device_rows)

        self.ignored_group = Adw.PreferencesGroup(
            title=tr("Ignorados"),
            description=tr(
                "Dispositivos que el kernel expone como joystick pero udev no "
                "reconoce como tales. Deshabilitalos para liberar su nodo js."
            ),
        )
        self.ignored_group.set_separate_rows(True)
        self.ignored_group.set_hexpand(True)
        self.ignored_group.set_visible(False)
        self.append(self.ignored_group)

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
        self._update_preset_tooltips()

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

    def set_hid_devices(self, devices: list[HidDevice]) -> None:
        """Actualiza el estado de binding de los dispositivos HID."""
        fingerprint = tuple(
            sorted((device.identifier, device.sysname, device.driver) for device in devices)
        )
        if fingerprint == self._hid_fingerprint:
            return
        self._hid_fingerprint = fingerprint
        by_id: dict[str, HidDevice] = {}
        for device in devices:
            existing = by_id.get(device.identifier)
            if existing is None or (device.bound and not existing.bound):
                by_id[device.identifier] = device
        self._hid_devices = by_id
        self.reload()

    def set_uinput_available(self, available: bool) -> None:
        self._uinput_available = available
        if not available:
            self._pending_steam = None
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
        self._update_preset_tooltips()
        self._apply_sensitivity()

    def set_installed_rules(self, rules: list) -> None:
        filenames = {
            rule.filename for rule in rules if rule.kind == "preset"
        }
        steam_files = set(preset_files(STEAM))
        gdu_files = set(preset_files(GAME_DEVICES))
        self._steam_installed = steam_files <= filenames
        self._gdu_installed = gdu_files <= filenames
        self._steam_rule_count = len(steam_files & filenames)
        self._gdu_rule_count = len(gdu_files & filenames)
        self._update_preset_tooltips()
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

    def _update_preset_tooltips(self) -> None:
        steam_lines = [
            tr(
                "{count} de {total} reglas instaladas",
                count=self._steam_rule_count,
                total=self._steam_rule_total,
            )
        ]
        if not self._uinput_available:
            steam_lines.append(tr("Requiere el módulo uinput del kernel."))
        self.steam_switch.set_tooltip_text("\n".join(steam_lines))
        self.gdu_switch.set_tooltip_text(
            tr(
                "{count} de {total} reglas instaladas",
                count=self._gdu_rule_count,
                total=self._gdu_rule_total,
            )
        )

    @staticmethod
    def _find_listbox(widget: Gtk.Widget) -> Gtk.ListBox | None:
        if isinstance(widget, Gtk.ListBox):
            return widget
        child = widget.get_first_child()
        while child is not None:
            found = DeviceManager._find_listbox(child)
            if found is not None:
                return found
            child = child.get_next_sibling()
        return None

    def _sort_device_rows(
        self,
        first: Gtk.ListBoxRow,
        second: Gtk.ListBoxRow,
    ) -> int:
        order = {
            device_id: index
            for index, device_id in enumerate(self._live_order)
        }
        fallback = len(order)

        def key(row: Gtk.ListBoxRow) -> int:
            device_id = self._row_identities.get(row)
            return order.get(device_id, fallback) if device_id else fallback

        left, right = key(first), key(second)
        return (left > right) - (left < right)

    def _refresh_row_order(self) -> None:
        if self.devices_listbox is not None:
            self.devices_listbox.invalidate_sort()

    def reload(self) -> None:
        self._updating = True
        for group, row in self._rows:
            group.remove(row)
        self._rows.clear()
        self._row_identities.clear()
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
        connected_by_id = {
            device_identity(device): device for device in connected
        }
        ignorable_ids = {
            device_identity(device)
            for device in connected
            if device.is_ignorable
        }

        allow_known = [
            device
            for device in known
            if device.action == "allow"
            and not device.hidden
            and not device.ignorable
            and device.id not in ignorable_ids
        ]

        regular_connected = [
            device
            for device in connected
            if not device.is_ignorable
            and device_identity(device) not in known_ids
        ]

        entries: list[tuple[str, str, object]] = [
            ("known", record.id, record) for record in allow_known
        ]
        entries.extend(
            ("unknown", device_identity(device), device)
            for device in regular_connected
        )
        if self.store.has_order():
            def entry_key(entry: tuple[str, str, object]) -> tuple:
                order_index = self.store.order_index(entry[1])
                return (
                    order_index is None,
                    order_index if order_index is not None else 0,
                    str(getattr(entry[2], "display_name", "")).casefold(),
                    entry[1],
                )

            entries.sort(key=entry_key)

        self._live_order = [
            device_id for _kind, device_id, _entry in entries
        ]

        for kind, device_id, entry in entries:
            if kind == "known":
                row = self._known_row(
                    entry,  # type: ignore[arg-type]
                    connected_by_id.get(device_id),
                    removable=True,
                )
            else:
                row = self._unknown_row(entry)  # type: ignore[arg-type]
            self._append(self.devices_group, row)

        if not entries:
            row = Adw.ActionRow(
                title=tr("No hay dispositivos guardados"),
                subtitle=tr(
                    "Conectá un mando para crear su primera regla."
                ),
            )
            row.set_activatable(False)
            self._append(self.devices_group, row)

        ignored_known = [
            record
            for record in known
            if (record.ignorable or record.id in ignorable_ids)
            and not record.hidden
        ]
        ignored_known_ids = {record.id for record in ignored_known}
        ignored_entries: list[tuple[str, str, object]] = [
            ("known", record.id, record) for record in ignored_known
        ]
        ignored_entries.extend(
            ("unknown", device_identity(device), device)
            for device in connected
            if device.is_ignorable
            and device_identity(device) not in ignored_known_ids
            and device_identity(device) not in known_ids
        )

        def ignored_name(entry: tuple[str, str, object]) -> str:
            item = entry[2]
            if isinstance(item, KnownDevice):
                return item.name
            return item.display_name  # type: ignore[union-attr]

        ignored_entries.sort(
            key=lambda item: (
                ignored_name(item).casefold(),
                item[1],
            )
        )

        self._ignored_actual.clear()
        for kind, device_id, entry in ignored_entries:
            if kind == "known":
                record = entry  # type: ignore[assignment]
                connected_device = connected_by_id.get(device_id)
                actual = self._actual_ignored(
                    record.identifier,
                    record,
                    connected_device,
                )
                self._ignored_actual[device_id] = actual
                row = self._ignored_row(
                    device_id,
                    record.name,
                    record.bus_label,
                    record.identifier,
                    connected_device,
                    actual,
                )
            else:
                joystick = entry  # type: ignore[assignment]
                actual = self._actual_ignored(
                    joystick.identifier,
                    None,
                    joystick,
                )
                self._ignored_actual[device_id] = actual
                row = self._ignored_row(
                    device_id,
                    joystick.display_name,
                    joystick.bus_label,
                    joystick.identifier,
                    joystick,
                    actual,
                )
            self._append(self.ignored_group, row)
        self.ignored_group.set_visible(bool(ignored_entries))

        for key in list(self._pending_ignored):
            actual = self._ignored_actual.get(key)
            if actual is not None and actual == self._pending_ignored[key]:
                self._pending_ignored.pop(key, None)
                self._pending_ignored_joysticks.pop(key, None)

        self._apply_sensitivity()
        self._update_pending_ui()
        self._updating = False

    def _append(self, group: Adw.PreferencesGroup, row: Gtk.Widget) -> None:
        group.add(row)
        self._rows.append((group, row))
        if row not in self._controls:
            self._controls.append(row)

    @staticmethod
    def _find_title_label(row: Adw.ActionRow) -> Gtk.Label | None:
        """Localiza la etiqueta interna del título de ``Adw.ActionRow``."""
        def walk(widget: Gtk.Widget) -> Gtk.Label | None:
            if (
                isinstance(widget, Gtk.Label)
                and "title" in widget.get_css_classes()
            ):
                return widget
            child = widget.get_first_child()
            while child is not None:
                found = walk(child)
                if found is not None:
                    return found
                child = child.get_next_sibling()
            return None

        return walk(row)

    def _add_device_icon(
        self,
        row: Adw.ActionRow,
        device_id: str,
    ) -> None:
        """Añade el selector de icono y color a la izquierda de la fila."""
        icon_id = self.store.icon_for(device_id)
        if icon_id not in _DEVICE_ICONS:
            icon_id = _DEFAULT_DEVICE_ICON
        color_id = _normalize_device_color(self.store.color_for(device_id))

        image = Gtk.Image.new_from_icon_name(_DEVICE_ICONS[icon_id])
        image.set_pixel_size(18)
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.CENTER)
        image.set_hexpand(True)
        image.set_vexpand(True)
        icon_box = Gtk.Box()
        icon_box.set_size_request(34, 34)
        icon_box.set_valign(Gtk.Align.CENTER)
        icon_box.add_css_class("device-icon-color")
        icon_box.add_css_class(f"device-color-{color_id}")
        icon_box.append(image)

        menu_button = Gtk.MenuButton()
        menu_button.add_css_class("flat")
        menu_button.add_css_class("device-icon-button")
        menu_button.set_has_frame(False)
        menu_button.set_always_show_arrow(False)
        menu_button.set_valign(Gtk.Align.CENTER)
        menu_button.set_size_request(36, 36)
        menu_button.set_child(icon_box)
        menu_button.set_tooltip_text(tr("Elegir icono"))

        popover = Gtk.Popover()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(10)
        content.set_margin_end(10)
        heading = Gtk.Label(label=tr("Icono del dispositivo"), xalign=0)
        heading.add_css_class("caption")
        content.append(heading)

        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_homogeneous(True)
        grid.set_min_children_per_line(5)
        grid.set_max_children_per_line(5)
        grid.set_column_spacing(4)
        grid.set_row_spacing(4)
        choices: dict[str, Gtk.Button] = {}

        def update_selection(selected_id: str) -> None:
            for choice_id, choice in choices.items():
                choice.remove_css_class("device-icon-selected")
                if choice_id == selected_id:
                    choice.add_css_class("device-icon-selected")

        for choice_id, choice_icon, label in _DEVICE_ICON_CHOICES:
            choice = Gtk.Button()
            choice.add_css_class("flat")
            choice.set_size_request(36, 36)
            choice_image = Gtk.Image.new_from_icon_name(choice_icon)
            choice_image.set_pixel_size(20)
            choice.set_child(choice_image)
            choice.set_tooltip_text(tr(label))
            choice.connect(
                "clicked",
                lambda _button, selected_id=choice_id: (
                    self._select_device_icon(
                        device_id,
                        selected_id,
                        image,
                        update_selection,
                    )
                ),
            )
            choices[choice_id] = choice
            grid.append(choice)

        update_selection(icon_id)
        content.append(grid)
        content.append(Gtk.Separator())

        color_heading = Gtk.Label(label=tr("Color"), xalign=0)
        color_heading.add_css_class("caption")
        content.append(color_heading)
        color_grid = Gtk.FlowBox()
        color_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        color_grid.set_homogeneous(True)
        color_grid.set_min_children_per_line(5)
        color_grid.set_max_children_per_line(5)
        color_grid.set_column_spacing(6)
        color_grid.set_row_spacing(6)
        color_choices: dict[str, Gtk.Button] = {}

        def update_color_selection(selected_id: str) -> None:
            for choice_id, choice in color_choices.items():
                choice.remove_css_class("device-color-selected")
                if choice_id == selected_id:
                    choice.add_css_class("device-color-selected")

        for choice_id, label in _DEVICE_COLOR_CHOICES:
            choice = Gtk.Button()
            choice.add_css_class("flat")
            choice.add_css_class("device-color-swatch")
            choice.add_css_class(f"device-color-{choice_id}")
            choice.set_size_request(26, 26)
            choice.set_halign(Gtk.Align.CENTER)
            choice.set_valign(Gtk.Align.CENTER)
            choice.set_tooltip_text(tr(label))
            choice.connect(
                "clicked",
                lambda _button, selected_id=choice_id: (
                    self._select_device_color(
                        device_id,
                        selected_id,
                        icon_box,
                        update_color_selection,
                    )
                ),
            )
            color_choices[choice_id] = choice
            color_grid.append(choice)

        update_color_selection(color_id)
        content.append(color_grid)
        popover.set_child(content)
        menu_button.set_popover(popover)
        row.add_prefix(menu_button)

    def _select_device_icon(
        self,
        device_id: str,
        icon_id: str,
        image: Gtk.Image,
        update_selection,
    ) -> None:
        try:
            self.store.set_icon(device_id, icon_id)
        except OSError as exc:
            self._show_error(
                tr("No se pudo guardar el icono"),
                str(exc),
            )
            return
        image.set_from_icon_name(_DEVICE_ICONS[icon_id])
        update_selection(icon_id)

    def _select_device_color(
        self,
        device_id: str,
        color_id: str,
        icon_box: Gtk.Box,
        update_selection,
    ) -> None:
        try:
            self.store.set_color(device_id, color_id)
        except OSError as exc:
            self._show_error(
                tr("No se pudo guardar el color"),
                str(exc),
            )
            return
        for known_color in _DEVICE_COLOR_IDS:
            icon_box.remove_css_class(f"device-color-{known_color}")
        icon_box.add_css_class(f"device-color-{color_id}")
        update_selection(color_id)

    def _add_alias_control(
        self,
        row: Adw.ActionRow,
        device_id: str,
        original_name: str,
    ) -> Callable[[], bool]:
        """Añade el lápiz pegado al título y la X para eliminarlo."""
        title = self._find_title_label(row)
        if title is None or title.get_parent() is None:
            return lambda: False
        title_box = title.get_parent()
        if not isinstance(title_box, Gtk.Box):
            return lambda: False
        title_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=2,
        )
        title_row.set_valign(Gtk.Align.CENTER)
        title_row.set_hexpand(True)
        title.unparent()
        title.set_hexpand(False)
        title_row.append(title)
        title_box.prepend(title_row)

        button = Gtk.Button()
        button.add_css_class("flat")
        button.set_valign(Gtk.Align.CENTER)
        title_row.append(button)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        title_row.append(spacer)

        entry: Gtk.Entry | None = None
        editing = False
        hovered = False
        visible_opacity = 0.55
        suspended_activatable: bool | None = None

        def suspend_row_activation() -> None:
            nonlocal suspended_activatable
            if suspended_activatable is None:
                suspended_activatable = row.get_activatable()
            row.set_activatable(False)

        def restore_row_activation() -> None:
            nonlocal suspended_activatable
            if suspended_activatable is not None:
                row.set_activatable(suspended_activatable)
                suspended_activatable = None

        def refresh_visibility() -> None:
            visible = hovered or editing
            button.set_opacity(visible_opacity if visible else 0.0)
            button.set_can_target(visible)
            button.set_focusable(visible)

        def update_state() -> None:
            nonlocal visible_opacity
            alias = self.store.alias_for(device_id)
            if editing:
                has_text = entry is not None and bool(entry.get_text().strip())
                button.set_icon_name(
                    "object-select-symbolic"
                    if has_text
                    else "document-edit-symbolic"
                )
                button.set_tooltip_text(
                    tr("Guardar alias")
                    if has_text
                    else tr("Agregar alias")
                )
                visible_opacity = 1.0 if has_text else 0.55
                refresh_visibility()
                return
            row.set_title(markup_escape(alias or original_name))
            title.set_visible(True)
            if alias:
                button.set_icon_name("window-close-symbolic")
                button.set_tooltip_text(tr("Eliminar alias"))
            else:
                button.set_icon_name("document-edit-symbolic")
                button.set_tooltip_text(tr("Agregar alias"))
            visible_opacity = 0.55
            refresh_visibility()

        def finish_edit(save: bool) -> None:
            nonlocal entry, editing
            if not editing or entry is None:
                return
            current = entry
            text = current.get_text().strip()
            if save and text:
                try:
                    self.store.set_alias(device_id, text)
                except OSError as exc:
                    self._show_error(
                        tr("No se pudo guardar el alias"),
                        str(exc),
                    )
                    return
            editing = False
            entry = None
            current.unparent()
            title.set_visible(True)
            restore_row_activation()
            update_state()

        def focus_entry() -> bool:
            if entry is not None:
                entry.grab_focus()
                entry.set_position(-1)
            return False

        def confirm_clear_alias() -> None:
            alias = self.store.alias_for(device_id)
            if not alias:
                update_state()
                return
            dialog = Adw.AlertDialog(
                heading=tr("¿Eliminar el alias?"),
                body=tr(
                    "Se eliminará el alias «{alias}».",
                    alias=alias,
                ),
            )
            dialog.add_response("cancel", tr("Cancelar"))
            dialog.add_response("remove", tr("Eliminar"))
            dialog.set_response_appearance(
                "remove", Adw.ResponseAppearance.DESTRUCTIVE
            )
            dialog.set_default_response("cancel")
            dialog.set_close_response("cancel")
            suspend_row_activation()

            def on_response(_dialog, response: str) -> None:
                if response != "remove":
                    restore_row_activation()
                    return
                try:
                    self.store.clear_alias(device_id)
                except OSError as exc:
                    restore_row_activation()
                    self._show_error(
                        tr("No se pudo guardar el alias"),
                        str(exc),
                    )
                    return
                restore_row_activation()
                update_state()

            dialog.connect("response", on_response)
            root = self.get_root()
            dialog.present(root if root is not None else self.parent_window)

        def start_edit() -> None:
            nonlocal entry, editing
            if editing:
                finish_edit(True)
                return
            if self.store.alias_for(device_id):
                confirm_clear_alias()
                return
            suspend_row_activation()
            editing = True
            title.set_visible(False)
            entry = Gtk.Entry()
            entry.set_placeholder_text(original_name)
            entry.set_text("")
            entry.set_hexpand(False)
            entry.set_width_chars(22)
            entry.set_valign(Gtk.Align.CENTER)
            entry.add_css_class("alias-entry")
            entry.connect("changed", lambda *_: update_state())
            entry.connect("activate", lambda *_: finish_edit(True))

            def on_key_pressed(
                _controller,
                keyval: int,
                _keycode: int,
                _state,
            ) -> bool:
                if keyval != Gdk.KEY_Escape:
                    return False
                finish_edit(False)
                return True

            key_controller = Gtk.EventControllerKey()
            key_controller.connect("key-pressed", on_key_pressed)
            entry.add_controller(key_controller)
            title_row.prepend(entry)
            update_state()
            GLib.idle_add(focus_entry)

        def on_clicked(_button: Gtk.Button) -> None:
            if editing:
                finish_edit(
                    entry is not None and bool(entry.get_text().strip())
                )
            else:
                start_edit()

        def on_enter(*_args) -> None:
            nonlocal hovered
            hovered = True
            refresh_visibility()

        def on_leave(*_args) -> None:
            nonlocal hovered
            hovered = False
            refresh_visibility()

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", on_enter)
        motion.connect("leave", on_leave)
        row.add_controller(motion)

        button.connect("clicked", on_clicked)
        update_state()
        return lambda: editing or suspended_activatable is not None

    def _add_hover_button(
        self,
        row: Adw.ActionRow,
        button: Gtk.Button,
    ) -> None:
        """Muestra un botón solo mientras el puntero está sobre la fila."""
        def update(visible: bool) -> None:
            button.set_opacity(1.0 if visible else 0.0)
            button.set_can_target(visible)
            button.set_focusable(visible)

        def on_enter(*_args) -> None:
            update(True)

        def on_leave(*_args) -> None:
            update(False)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", on_enter)
        motion.connect("leave", on_leave)
        row.add_controller(motion)
        update(False)

    def _add_hover_opacity(
        self,
        row: Adw.ActionRow,
        widget: Gtk.Widget,
        normal: float,
        hovered: float,
    ) -> None:
        def update(active: bool) -> None:
            widget.set_opacity(hovered if active else normal)

        def on_enter(*_args) -> None:
            update(True)

        def on_leave(*_args) -> None:
            update(False)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", on_enter)
        motion.connect("leave", on_leave)
        row.add_controller(motion)
        update(False)

    def _add_drag_handle(
        self,
        row: Adw.ActionRow,
        device_id: str,
    ) -> None:
        """Añade el tirador de tres puntos para reordenar la fila."""
        visual = Gtk.Box()
        visual.add_css_class("device-drag-handle")
        visual.set_size_request(24, 44)
        visual.set_valign(Gtk.Align.CENTER)
        image = Gtk.Image.new_from_icon_name("view-more-symbolic")
        image.set_pixel_size(18)
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.CENTER)
        visual.append(image)
        visual.set_tooltip_text(tr("Arrastrar para reordenar"))

        handle = Gtk.Overlay()
        handle.set_size_request(24, 44)
        handle.set_valign(Gtk.Align.CENTER)
        handle.set_overflow(Gtk.Overflow.VISIBLE)
        handle.set_child(visual)
        hitbox = Gtk.Box()
        hitbox.set_size_request(52, 52)
        hitbox.set_halign(Gtk.Align.END)
        hitbox.set_valign(Gtk.Align.CENTER)
        hitbox.set_tooltip_text(tr("Arrastrar para reordenar"))
        handle.add_overlay(hitbox)

        drag_state: dict[str, object] = {
            "timer": 0,
            "preview": None,
            "origin": None,
            "hot_y": 0,
        }

        def tuple_xy(value: object) -> tuple[float, float] | None:
            if not value:
                return None
            if len(value) >= 3:  # type: ignore[arg-type]
                if not value[0]:  # type: ignore[index]
                    return None
                return float(value[1]), float(value[2])  # type: ignore[index]
            if len(value) >= 2:  # type: ignore[arg-type]
                return float(value[0]), float(value[1])  # type: ignore[index]
            return None

        def pointer_position() -> tuple[float, float] | None:
            root = row.get_root()
            native = row.get_native()
            if root is None or native is None:
                return None
            surface = native.get_surface()
            display = Gdk.Display.get_default()
            if surface is None or display is None:
                return None
            seat = display.get_default_seat()
            pointer = seat.get_pointer() if seat is not None else None
            if pointer is None:
                return None
            pointer_xy = tuple_xy(surface.get_device_position(pointer))
            origin_xy = tuple_xy(row.translate_coordinates(root, 0, 0))
            if pointer_xy is None or origin_xy is None:
                return None
            return (
                pointer_xy[0] - origin_xy[0],
                pointer_xy[1] - origin_xy[1],
            )

        def overlay_origin() -> tuple[float, float] | None:
            return tuple_xy(
                row.translate_coordinates(self.devices_overlay, 0, 0)
            )

        def update_preview() -> bool:
            preview = drag_state.get("preview")
            origin = drag_state.get("origin")
            if preview is None or origin is None:
                return False
            position = pointer_position()
            current_origin = overlay_origin()
            if position is not None and current_origin is not None:
                pointer_y = current_origin[1] + position[1]
                self.preview_layer.move(
                    preview,  # type: ignore[arg-type]
                    int(origin[0]),  # type: ignore[index]
                    int(pointer_y - drag_state["hot_y"]),
                )
                target = self._live_target_under_pointer(
                    pointer_y,
                    device_id,
                )
                if target is not None:
                    target_row, target_y = target
                    self._live_reorder(
                        device_id,
                        target_row,
                        target_y,
                    )
            return True

        def on_drag_begin(drag_source, _drag) -> None:
            try:
                drag_source.set_icon(
                    Gdk.MemoryTexture.new(
                        1,
                        1,
                        Gdk.MemoryFormat.R8G8B8A8_PREMULTIPLIED,
                        GLib.Bytes.new(b"\x00\x00\x00\x00"),
                        4,
                    ),
                    0,
                    0,
                )
            except Exception:
                pass
            origin = overlay_origin()
            position = pointer_position()
            if origin is None or position is None:
                return
            width = max(1, row.get_width())
            height = max(1, row.get_height())
            snapshot = Gtk.WidgetPaintable.new(row).get_current_image()
            picture = Gtk.Picture.new_for_paintable(snapshot)
            picture.set_size_request(width, height)
            picture.set_can_shrink(True)
            picture.set_content_fit(Gtk.ContentFit.FILL)
            picture.set_can_target(False)
            preview = Gtk.Box()
            preview.add_css_class("device-dragging-card")
            preview.set_size_request(width, height)
            preview.set_can_target(False)
            preview.append(picture)
            self.preview_layer.put(preview, int(origin[0]), int(origin[1]))
            row.set_opacity(0.0)
            self.devices_group.add_css_class("drag-in-progress")
            drag_state["preview"] = preview
            drag_state["origin"] = origin
            drag_state["hot_y"] = min(20, max(0, int(position[1])))
            drag_state["timer"] = GLib.timeout_add(16, update_preview)

        def on_drag_end(*_args) -> None:
            timer = drag_state.get("timer")
            if timer:
                GLib.source_remove(timer)
                drag_state["timer"] = 0
            preview = drag_state.get("preview")
            if preview is not None:
                self.preview_layer.remove(preview)  # type: ignore[arg-type]
            row.set_opacity(1.0)
            self.devices_group.remove_css_class("drag-in-progress")
            drag_state["preview"] = None
            drag_state["origin"] = None

        source = Gtk.DragSource()
        source.set_actions(Gdk.DragAction.MOVE)
        source.connect(
            "prepare",
            lambda _source, _x, _y: Gdk.ContentProvider.new_for_value(
                device_id
            ),
        )
        source.connect("drag-begin", on_drag_begin)
        source.connect("drag-end", on_drag_end)
        source.connect("drag-cancel", lambda *_args: on_drag_end())
        hitbox.add_controller(source)

        target = Gtk.DropTarget.new(
            GObject.TYPE_STRING,
            Gdk.DragAction.MOVE,
        )
        target.connect(
            "drop",
            lambda _target, value, _x, y: self._drop_row(
                value,
                row,
                y,
            ),
        )
        target.connect(
            "motion",
            lambda _target, _x, y: self._live_reorder(
                device_id,
                row,
                y,
            ),
        )
        row.add_controller(target)
        row.add_prefix(handle)
        self._add_hover_opacity(row, visual, 0.25, 0.85)

    def _live_target_under_pointer(
        self,
        pointer_y: float,
        dragged_id: str,
    ) -> tuple[Adw.ActionRow, float] | None:
        for _group, row in self._rows:
            row_id = self._row_identities.get(row)
            if not row_id or row_id == dragged_id:
                continue
            origin = self._origin_in_overlay(row)
            if origin is None:
                continue
            top = origin[1]
            bottom = top + row.get_height()
            if top <= pointer_y <= bottom:
                return row, pointer_y - top
        return None

    def _live_reorder(
        self,
        dragged_id: str,
        target_row: Adw.ActionRow,
        y: float,
    ) -> Gdk.DragAction:
        target_id = self._row_identities.get(target_row)
        if not target_id or dragged_id == target_id:
            return Gdk.DragAction.MOVE

        visible = {
            row_id
            for _group, row in self._rows
            if (row_id := self._row_identities.get(row))
        }
        order = [
            device_id
            for device_id in self._live_order
            if device_id in visible
        ]
        if dragged_id not in order or target_id not in order:
            return Gdk.DragAction.MOVE

        order.remove(dragged_id)
        target_index = order.index(target_id)
        if y >= target_row.get_height() / 2:
            target_index += 1
        order.insert(target_index, dragged_id)
        if order == self._live_order:
            return Gdk.DragAction.MOVE

        animate = (
            target_id not in self._animating_rows
            and target_row.get_opacity() > 0
        )
        target_origin = (
            self._origin_in_overlay(target_row) if animate else None
        )
        target_width = max(1, target_row.get_width())
        target_height = max(1, target_row.get_height())
        target_snapshot = (
            Gtk.WidgetPaintable.new(target_row).get_current_image()
            if animate
            else None
        )

        self._live_order = order
        try:
            self.store.set_order(order)
        except OSError as exc:
            self._show_error(
                tr("No se pudo guardar el orden"),
                str(exc),
            )
            return Gdk.DragAction.MOVE
        self._refresh_row_order()
        if (
            animate
            and target_origin is not None
            and target_snapshot is not None
        ):
            self._animate_dropped_row(
                target_id,
                target_origin[1],
                target_width,
                target_height,
                target_snapshot,
            )
        return Gdk.DragAction.MOVE

    def _drop_row(
        self,
        dragged_id: object,
        target_row: Adw.ActionRow,
        y: float,
    ) -> bool:
        if not isinstance(dragged_id, str):
            return False
        target_id = self._row_identities.get(target_row)
        if not target_id or dragged_id == target_id:
            return False

        visible = {
            row_id
            for _group, row in self._rows
            if (row_id := self._row_identities.get(row))
        }
        order = [
            device_id
            for device_id in self._live_order
            if device_id in visible
        ]
        if dragged_id not in order or target_id not in order:
            order = [
                row_id
                for _group, row in self._rows
                if (row_id := self._row_identities.get(row))
            ]
        if dragged_id not in order or target_id not in order:
            return False

        order.remove(dragged_id)
        target_index = order.index(target_id)
        if y >= target_row.get_height() / 2:
            target_index += 1
        order.insert(target_index, dragged_id)

        target_origin = self._origin_in_overlay(target_row)
        target_width = max(1, target_row.get_width())
        target_height = max(1, target_row.get_height())
        target_snapshot = Gtk.WidgetPaintable.new(
            target_row
        ).get_current_image()

        try:
            self.store.set_order(order)
        except OSError as exc:
            self._show_error(
                tr("No se pudo guardar el orden"),
                str(exc),
            )
            return False
        self.reload()
        if target_origin is not None:
            self._animate_dropped_row(
                target_id,
                target_origin[1],
                target_width,
                target_height,
                target_snapshot,
            )
        return True

    @staticmethod
    def _tuple_xy(value: object) -> tuple[float, float] | None:
        if not value:
            return None
        if len(value) >= 3:  # type: ignore[arg-type]
            if not value[0]:  # type: ignore[index]
                return None
            return float(value[1]), float(value[2])  # type: ignore[index]
        if len(value) >= 2:  # type: ignore[arg-type]
            return float(value[0]), float(value[1])  # type: ignore[index]
        return None

    def _origin_in_overlay(
        self,
        widget: Gtk.Widget,
    ) -> tuple[float, float] | None:
        return self._tuple_xy(
            widget.translate_coordinates(self.devices_overlay, 0, 0)
        )

    def _animate_dropped_row(
        self,
        device_id: str,
        old_y: float,
        width: int,
        height: int,
        snapshot: Gdk.Paintable,
    ) -> None:
        """Anima la fila que fue desplazada al soltar la tarjeta."""
        if device_id in self._animating_rows:
            return
        self._animating_rows.add(device_id)
        attempts = 0

        def finish() -> bool:
            self._animating_rows.discard(device_id)
            return False

        def start() -> bool:
            nonlocal attempts
            row = next(
                (
                    candidate
                    for _group, candidate in self._rows
                    if self._row_identities.get(candidate) == device_id
                ),
                None,
            )
            if row is None or row.get_width() == 0:
                attempts += 1
                if attempts >= 8:
                    return finish()
                return True
            origin = self._origin_in_overlay(row)
            if origin is None:
                return finish()
            new_y = origin[1]
            if abs(new_y - old_y) < 2:
                return finish()

            picture = Gtk.Picture.new_for_paintable(snapshot)
            picture.set_size_request(width, height)
            picture.set_can_shrink(True)
            picture.set_content_fit(Gtk.ContentFit.FILL)
            picture.set_can_target(False)
            card = Gtk.Box()
            card.add_css_class("device-reorder-card")
            card.set_size_request(width, height)
            card.set_can_target(False)
            card.append(picture)
            self.preview_layer.put(card, int(origin[0]), int(old_y))
            row.set_opacity(0.0)

            now = GLib.get_monotonic_time()
            duration = 160_000

            def tick() -> bool:
                elapsed = GLib.get_monotonic_time() - now
                progress = min(1.0, elapsed / duration)
                eased = 1.0 - (1.0 - progress) ** 3
                current_y = old_y + (new_y - old_y) * eased
                self.preview_layer.move(
                    card,
                    int(origin[0]),
                    int(current_y),
                )
                if progress >= 1.0:
                    self.preview_layer.remove(card)
                    row.set_opacity(1.0)
                    return finish()
                return True

            GLib.timeout_add(16, tick)
            return False

        GLib.timeout_add(16, start)

    def _known_row(
        self,
        device: KnownDevice,
        connected_device: Joystick | None,
        *,
        removable: bool = False,
    ) -> Adw.ActionRow:
        details = [device.bus_label, device.identifier]
        row = Adw.ActionRow(
            title=markup_escape(device.name),
            subtitle=markup_escape(" · ".join(details)),
        )
        self._row_identities[row] = device.id
        can_open = bool(device.active and device.filename)
        row.set_activatable(True)
        if can_open:
            row.set_tooltip_text(
                tr("Abrir {filename}", filename=device.filename)
            )
        self._add_device_icon(row, device.id)
        self._add_drag_handle(row, device.id)
        alias_active = self._add_alias_control(
            row,
            device.id,
            device.name,
        )
        row.connect(
            "activated",
            lambda _row, selected=device: (
                None
                if alias_active()
                else self._open_known_rule(selected)
            ),
        )

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
            self._add_hover_button(row, hide)

        if connected_device is not None:
            row.add_suffix(self._connected_badge(connected_device))

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
        row = Adw.ActionRow(
            title=markup_escape(device.display_name),
            subtitle=markup_escape(" · ".join(details)),
        )
        self._row_identities[row] = key
        row.set_activatable(False)
        self._add_device_icon(row, key)
        self._add_drag_handle(row, key)
        self._add_alias_control(row, key, device.display_name)
        row.add_suffix(self._connected_badge(device))

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

    def _connected_badge(self, device: Joystick | None = None) -> Gtk.Label:
        label = tr("Conectado")
        js_label = _js_nodes_label(device)
        if js_label:
            label = f"{label} · {js_label}"
        badge = Gtk.Label(label=label)
        badge.add_css_class("device-badge")
        badge.add_css_class("device-badge-connected")
        badge.set_valign(Gtk.Align.CENTER)
        return badge

    def _actual_ignored(
        self,
        identifier: str,
        record: KnownDevice | None,
        connected: Joystick | None,
    ) -> bool:
        """Estado real: ¿el driver HID está desvinculado?"""
        if connected is not None:
            # Si udev lo vuelve a detectar como js, el HID está enlazado.
            return False
        hid = self._hid_devices.get(identifier)
        if hid is not None:
            # El dispositivo HID sigue en el bus pero no expone js: está
            # desvinculado (o al menos no está entregando su interfaz de
            # entrada).
            return True
        if record is not None:
            return record.ignored
        return False

    def _ignored_row(
        self,
        device_id: str,
        name: str,
        bus: str,
        identifier: str,
        connected: Joystick | None,
        actual_ignored: bool,
    ) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=markup_escape(name),
            subtitle=markup_escape(f"{bus} · {identifier}"),
        )
        self._row_identities[row] = device_id
        row.set_activatable(False)
        self._add_device_icon(row, device_id)

        if actual_ignored:
            badge = Gtk.Label(label=tr("Deshabilitado"))
            badge.add_css_class("device-badge")
            badge.add_css_class("device-badge-disabled")
            badge.set_valign(Gtk.Align.CENTER)
            badge.set_tooltip_text(
                tr(
                    "El driver HID está desvinculado y el nodo js está "
                    "liberado."
                )
            )
            row.add_suffix(badge)
        elif connected is not None:
            row.add_suffix(self._connected_badge(connected))

        active = self._pending_ignored.get(device_id, actual_ignored)
        switch = Gtk.Switch(active=active)
        switch.set_valign(Gtk.Align.CENTER)
        switch.set_tooltip_text(
            tr("Volver a habilitar y recuperar el nodo js")
            if active
            else tr("Deshabilitar y liberar el nodo js")
        )
        switch.connect(
            "notify::active",
            lambda selected_switch, _pspec, selected_id=device_id, selected_device=connected: (
                self._set_ignored_pending(
                    selected_id,
                    selected_switch.get_active(),
                    selected_device,
                )
            ),
        )
        row.add_suffix(switch)
        self._controls.append(switch)
        return row

    def _set_ignored_pending(
        self,
        device_id: str,
        active: bool,
        device: Joystick | None,
    ) -> None:
        if self._updating or self._busy:
            return
        actual = self._ignored_actual.get(device_id, False)
        if active == actual:
            self._pending_ignored.pop(device_id, None)
            self._pending_ignored_joysticks.pop(device_id, None)
        else:
            self._pending_ignored[device_id] = active
            if device is not None:
                self._pending_ignored_joysticks[device_id] = device
        self._update_pending_ui()

    def _set_known_pending(self, device: KnownDevice, active: bool) -> None:
        if self._updating or self._busy:
            return
        if active == device.active:
            self._pending_known.pop(device.id, None)
        else:
            self._pending_known[device.id] = active
        self._update_pending_ui()

    def _open_known_rule(self, device: KnownDevice) -> None:
        if not device.active or not device.filename:
            self._show_error(
                tr("Regla no instalada"),
                tr(
                    "El dispositivo «{name}» no tiene una regla instalada. "
                    "Activá esta regla para poder leer el archivo.",
                    name=device.name,
                ),
            )
            return
        try:
            validate_rule_filename(device.filename)
        except ValueError as exc:
            self._show_error(tr("No se pudo abrir la regla"), str(exc))
            return
        thread = threading.Thread(
            target=self._open_rule_worker,
            args=(device,),
            name="udev-rule-generator-open-rule",
            daemon=True,
        )
        thread.start()

    def _open_rule_worker(self, device: KnownDevice) -> None:
        path = f"/etc/udev/rules.d/{device.filename}"
        last_error = tr("xdg-open no pudo abrir el archivo.")
        for argv in (["xdg-open", path], ["gio", "open", path]):
            try:
                result = self.host.run(argv, timeout=20)
            except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
                last_error = str(exc)
                continue
            if result.ok:
                return
            last_error = (
                result.stderr.strip()
                or result.stdout.strip()
                or last_error
            )
        GLib.idle_add(self._open_rule_failed, last_error)

    def _open_rule_failed(self, message: str) -> bool:
        self._show_error(tr("No se pudo abrir la regla"), message)
        return False

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

    def reset_after_clear(self) -> None:
        """Descarta cambios pendientes y recarga tras borrar todos los datos."""
        self._pending_known.clear()
        self._pending_unknown.clear()
        self._pending_ignored.clear()
        self._pending_ignored_joysticks.clear()
        self.reload()

    def _update_pending_ui(self) -> None:
        pending = bool(
            self._pending_known
            or self._pending_unknown
            or self._pending_ignored
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
            or self._pending_ignored
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

            hid_changes: list[HidBindingChange] = []
            ignored_updates: list[tuple[str, bool, Joystick, str]] = []
            for device_id, ignored in self._pending_ignored.items():
                record = self.store.get(device_id)
                joystick = self._pending_ignored_joysticks.get(device_id)
                if joystick is None and record is not None:
                    joystick = record.to_joystick()
                if joystick is None:
                    continue
                hid = self._hid_devices.get(joystick.identifier)
                driver = record.hid_driver if record is not None else ""
                if not driver and hid is not None:
                    driver = hid.driver
                if not driver:
                    driver = "hid-generic"
                hid_changes.append(
                    HidBindingChange(
                        joystick.vendor_id,
                        joystick.product_id,
                        bound=not ignored,
                        driver=driver,
                    )
                )
                ignored_updates.append(
                    (device_id, ignored, joystick, driver)
                )

            if not install_files and not removed and not hid_changes:
                message = tr("No hay cambios para aplicar.")
            else:
                apply_rule_changes(
                    self.host,
                    install_files,
                    removed,
                    hid_changes=hid_changes,
                    trigger="add" if trigger_add else "change",
                )
                try:
                    if updated:
                        self.store.update_many(updated)
                    if removed:
                        self.store.mark_inactive_by_filenames(removed)
                    for device_id, ignored, joystick, driver in ignored_updates:
                        self.store.set_ignored(
                            device_id,
                            ignored,
                            device=joystick,
                            driver=driver,
                        )
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
            self._pending_ignored.clear()
            self._pending_ignored_joysticks.clear()
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
                or self._pending_ignored
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
