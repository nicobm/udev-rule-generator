"""Diálogo para instalar las reglas preconfiguradas."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator import PRESETS_URL, STEAM_DEVICES_URL
from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.presets import (
    STEAM,
    UPSTREAM,
    Preset,
    preset_files,
    presets_trigger,
)
from udev_rule_generator.privileged import install_rule_files

from .gi_compat import Adw, GLib, Gtk


class PresetsDialog(Adw.Dialog):
    """Selección de los paquetes completos de presets."""

    def __init__(
        self,
        *,
        host: Host,
        parent: Gtk.Window,
        on_installed: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.parent_window = parent
        self.host = host
        self.on_installed = on_installed
        self._steam_switch: Adw.SwitchRow | None = None
        self._fabiscafe_switch: Adw.SwitchRow | None = None
        self._busy = False

        self.set_title(tr("Reglas preconfiguradas"))
        self.set_content_width(760)
        self.set_content_height(620)
        self._build_ui()
        self._update_summary()

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(title=tr("Reglas preconfiguradas"))
        )
        toolbar.add_top_bar(header)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)

        steam = Adw.PreferencesGroup(
            title=tr("steam-devices (Valve)"),
            description=tr(
                "Reglas oficiales de ValveSoftware/steam-devices (MIT) · "
                "{url}",
                url=STEAM_DEVICES_URL,
            ),
        )
        self._steam_switch = Adw.SwitchRow(
            title=tr("Instalar steam-devices"),
        )
        self._steam_switch.set_active(False)
        self._steam_switch.connect(
            "notify::active", lambda *_: self._update_summary()
        )
        steam.add(self._steam_switch)
        page.add(steam)

        upstream = Adw.PreferencesGroup(
            title=tr("game-devices-udev (fabiscafe)"),
            description=tr(
                "Reglas del repositorio de Fabian Bornschein "
                "(fabiscafe/game-devices-udev) (MIT) · {url}",
                url=PRESETS_URL,
            ),
        )
        self._fabiscafe_switch = Adw.SwitchRow(
            title=tr("Instalar todas las reglas de fabiscafe"),
        )
        self._fabiscafe_switch.set_active(False)
        self._fabiscafe_switch.connect(
            "notify::active", lambda *_: self._update_summary()
        )
        upstream.add(self._fabiscafe_switch)
        page.add(upstream)

        toolbar.set_content(page)

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bottom.set_margin_top(10)
        bottom.set_margin_bottom(10)
        bottom.set_margin_start(14)
        bottom.set_margin_end(14)

        self.summary = Gtk.Label(label="", xalign=0)
        self.summary.set_hexpand(True)
        self.summary.add_css_class("dim-label")
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        cancel = Gtk.Button(label=tr("Cancelar"))
        cancel.connect("clicked", lambda *_: self.close())
        self.install_button = Gtk.Button(label=tr("Instalar seleccionadas"))
        self.install_button.add_css_class("suggested-action")
        self.install_button.connect("clicked", lambda *_: self._install())

        bottom.append(self.summary)
        bottom.append(self.spinner)
        bottom.append(cancel)
        bottom.append(self.install_button)
        toolbar.add_bottom_bar(bottom)
        self.set_child(toolbar)

    def _selected_presets(self) -> list[Preset]:
        selected: list[Preset] = []
        if self._fabiscafe_switch is not None and self._fabiscafe_switch.get_active():
            selected.extend(UPSTREAM)
        if self._steam_switch is not None and self._steam_switch.get_active():
            selected.extend(STEAM)
        return selected

    def _update_summary(self) -> None:
        selected = self._selected_presets()
        self.summary.set_text(
            tr("Listo para instalar") if selected else ""
        )
        self.install_button.set_sensitive(bool(selected) and not self._busy)

    def _install(self) -> None:
        presets = self._selected_presets()
        if not presets or self._busy:
            return
        files = preset_files(presets)
        trigger = presets_trigger(presets)
        self._set_busy(True)
        thread = threading.Thread(
            target=self._install_worker,
            args=(files, trigger),
            name="udev-rule-generator-presets",
            daemon=True,
        )
        thread.start()

    def _install_worker(self, files: dict[str, str], trigger: str) -> None:
        try:
            result = install_rule_files(self.host, files, trigger=trigger)
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._install_failed, str(exc))
            return
        GLib.idle_add(self._install_succeeded, len(result.filenames))

    def _install_succeeded(self, count: int) -> bool:
        self._set_busy(False)
        if count == 1:
            message = tr("Se instalaron {count} archivo de reglas.", count=count)
        else:
            message = tr("Se instalaron {count} archivos de reglas.", count=count)
        self.on_installed(message)
        self.close()
        return False

    def _install_failed(self, message: str) -> bool:
        self._set_busy(False)
        dialog = Adw.AlertDialog(
            heading=tr("No se pudieron instalar las reglas"),
            body=message,
        )
        dialog.add_response("close", tr("Cerrar"))
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)
        return False

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.install_button.set_sensitive(
            not busy and bool(self._selected_presets())
        )
        self.spinner.set_visible(busy)
        if busy:
            self.spinner.start()
            self.summary.set_text(
                tr("Esperando el diálogo de autenticación de GNOME/polkit…")
            )
            return
        self.spinner.stop()
        self._update_summary()
