"""Diálogo para ver y desocultar dispositivos."""

from __future__ import annotations

from typing import Callable

from udev_rule_generator.hidden import HiddenDevice, HiddenDevices
from udev_rule_generator.i18n import tr

from .gi_compat import Adw, Gtk


class HiddenDialog(Adw.Dialog):
    """Lista los dispositivos ocultos y permite volver a mostrarlos."""

    def __init__(
        self,
        *,
        store: HiddenDevices,
        parent: Gtk.Window,
        on_changed: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.parent_window = parent
        self.store = store
        self.on_changed = on_changed
        self._rows: list[Adw.ActionRow] = []

        self.set_title(tr("Dispositivos ocultos"))
        self.set_content_width(680)
        self.set_content_height(620)
        self._build_ui()
        self._reload()

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title=tr("Dispositivos ocultos"),
                subtitle=tr("No aparecen en la lista principal"),
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

        self.empty_page = Adw.StatusPage(
            icon_name="view-conceal-symbolic",
            title=tr("No hay dispositivos ocultos"),
            description=tr(
                "Cuando ocultes un dispositivo desde su ficha, va a aparecer "
                "acá para que puedas recuperarlo."
            ),
        )
        self.stack.add_named(self.empty_page, "empty")

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(620)
        clamp.set_tightening_threshold(520)
        clamp.set_hexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(18)
        content.set_margin_bottom(24)
        content.set_margin_start(18)
        content.set_margin_end(18)

        self.group = Adw.PreferencesGroup(
            title=tr("Dispositivos ocultos"),
            description=tr(
                "Desocultá un dispositivo para que vuelva a aparecer en la "
                "lista principal.  Las reglas udev no se modifican."
            ),
        )
        self.group.set_hexpand(True)
        content.append(self.group)

        clamp.set_child(content)
        scroller.set_child(clamp)
        self.stack.add_named(scroller, "list")
        toolbar.set_content(self.stack)
        self.set_child(toolbar)

    def _reload(self) -> None:
        for row in self._rows:
            self.group.remove(row)
        self._rows.clear()

        devices = self.store.devices()
        for device in devices:
            self.group.add(self._device_row(device))
        self.stack.set_visible_child_name("list" if devices else "empty")

    def _device_row(self, device: HiddenDevice) -> Adw.ActionRow:
        row = Adw.ActionRow(
            title=device.name,
            subtitle=f"{device.bus_label} · {device.identifier}",
        )
        row.set_tooltip_text(", ".join(device.nodes) if device.nodes else "")
        icon = Gtk.Image(icon_name="view-conceal-symbolic")
        icon.add_css_class("dim-label")
        icon.set_valign(Gtk.Align.CENTER)
        row.add_prefix(icon)

        button = Gtk.Button(label=tr("Desocultar"))
        button.add_css_class("flat")
        button.set_valign(Gtk.Align.CENTER)
        button.connect(
            "clicked",
            lambda _button, selected=device: self._unhide(selected),
        )
        row.add_suffix(button)
        self._rows.append(row)
        return row

    def _unhide(self, device: HiddenDevice) -> None:
        try:
            self.store.unhide(device.id)
        except OSError as exc:
            dialog = Adw.AlertDialog(
                heading=tr("No se pudo desocultar el dispositivo"),
                body=tr(
                    "No se pudo guardar la preferencia: {error}",
                    error=exc,
                ),
            )
            dialog.add_response("close", tr("Cerrar"))
            root = self.get_root()
            dialog.present(root if root is not None else self.parent_window)
            return
        self.on_changed(
            tr("Dispositivo desocultado: {name}", name=device.name)
        )
        self._reload()
