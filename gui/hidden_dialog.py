"""Diálogo para volver a mostrar dispositivos ocultos."""

from __future__ import annotations

from typing import Callable

from udev_rule_generator.i18n import tr
from udev_rule_generator.known import KnownDevice, KnownDevices

from .gi_compat import Adw, Gtk


class HiddenDevicesDialog(Adw.Window):
    """Lista los dispositivos guardados que están ocultos."""

    def __init__(
        self,
        *,
        store: KnownDevices,
        parent: Gtk.Window,
        on_changed: Callable[[str], None],
    ) -> None:
        super().__init__(
            transient_for=parent,
            modal=True,
            title=tr("Dispositivos ocultos"),
            default_width=520,
            default_height=420,
        )
        self.store = store
        self.on_changed = on_changed
        self._rows: list[Gtk.Widget] = []
        self._unhide_buttons: list[Gtk.Button] = []
        self._busy = False

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(title=tr("Dispositivos ocultos"))
        )
        toolbar.add_top_bar(header)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)
        self.group = Adw.PreferencesGroup(
            title=tr("Dispositivos ocultos"),
        )
        page.add(self.group)
        toolbar.set_content(page)
        self.set_content(toolbar)

        self.reload()

    def reload(self) -> None:
        for row in self._rows:
            self.group.remove(row)
        self._rows.clear()
        self._unhide_buttons.clear()

        hidden = [d for d in self.store.devices() if d.hidden]
        if not hidden:
            self.group.set_description(
                tr("No hay dispositivos ocultos")
            )
            return
        self.group.set_description(
            tr("Dispositivos que no se muestran en la ventana principal.")
        )

        for device in hidden:
            state = tr("Activa") if device.active else tr("Desactivada")
            row = Adw.ActionRow(
                title=device.name,
                subtitle=(
                    f"{device.bus_label} · {device.identifier} · {state}"
                ),
            )
            row.set_activatable(False)

            show = Gtk.Button(
                icon_name="view-reveal-symbolic",
                tooltip_text=tr("Mostrar de nuevo"),
            )
            show.add_css_class("flat")
            show.set_valign(Gtk.Align.CENTER)
            show.connect(
                "clicked",
                lambda _button, selected=device: self._unhide(selected),
            )
            row.add_suffix(show)
            self._unhide_buttons.append(show)
            self.group.add(row)
            self._rows.append(row)

    def _unhide(self, device: KnownDevice) -> None:
        if self._busy:
            return
        self._busy = True
        for button in self._unhide_buttons:
            button.set_sensitive(False)
        try:
            self.store.set_hidden(device.id, False)
        except OSError as exc:
            self._busy = False
            self.reload()
            self._show_error(
                tr("No se pudo mostrar el dispositivo"),
                str(exc),
            )
            return
        self._busy = False
        self.reload()
        self.on_changed(
            tr("Dispositivo desocultado: {name}", name=device.name)
        )

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", tr("Cerrar"))
        dialog.present(self)
