"""Diálogo para instalar las reglas preconfiguradas."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator import PRESETS_URL
from udev_rule_generator.host import Host
from udev_rule_generator.presets import (
    RECOMMENDED,
    UPSTREAM,
    Preset,
    preset_files,
    presets_trigger,
)
from udev_rule_generator.privileged import install_rule_files

from .gi_compat import Adw, GLib, Gtk


class PresetsDialog(Adw.Dialog):
    """Selección de reglas de fabricantes y reglas recomendadas."""

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
        self._recommended_rows: dict[Preset, Adw.SwitchRow] = {}
        self._upstream_rows: list[tuple[Preset, Adw.SwitchRow]] = []
        self._all_row: Adw.SwitchRow | None = None
        self._updating = False
        self._busy = False

        self.set_title("Reglas preconfiguradas")
        self.set_content_width(760)
        self.set_content_height(820)
        self._build_ui()
        self._update_summary()

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title="Reglas preconfiguradas",
                subtitle="ASRock, Microsoft y game-devices-udev",
            )
        )
        close_button = Gtk.Button(
            icon_name="window-close-symbolic",
            tooltip_text="Cerrar",
        )
        close_button.add_css_class("flat")
        close_button.connect("clicked", lambda *_: self.close())
        header.pack_end(close_button)
        toolbar.add_top_bar(header)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)

        intro = Adw.PreferencesGroup(
            title="¿Qué se instala?",
            description=(
                "Las reglas se copian a /etc/udev/rules.d con permisos de "
                "administrador.  Se pedirá la contraseña con el diálogo de "
                "polkit de GNOME."
            ),
        )
        page.add(intro)

        recommended = Adw.PreferencesGroup(
            title="Recomendadas",
            description=(
                "Pensadas para el caso típico: un mando Xbox y el controlador "
                "de LEDs ASRock que aparece como joystick falso."
            ),
        )
        for preset in RECOMMENDED:
            row = self._switch_row(preset)
            self._recommended_rows[preset] = row
            recommended.add(row)
        page.add(recommended)

        upstream = Adw.PreferencesGroup(
            title="game-devices-udev",
            description=(
                "Biblioteca de Fabian Bornschein (fabiscafe), licencia MIT.  "
                "Cada archivo agrupa los mandos de un fabricante."
            ),
        )
        self._all_row = Adw.SwitchRow(
            title="Todos los fabricantes",
            subtitle=(
                f"Instala las {len(UPSTREAM)} reglas de la biblioteca upstream, "
                "incluida la creación temprana de uinput."
            ),
        )
        self._all_row.connect("notify::active", self._on_all_toggled)
        upstream.add(self._all_row)

        expander = Adw.ExpanderRow(
            title="Elegir fabricante",
            subtitle="Desplegá para instalar solo algunos fabricantes.",
        )
        for preset in UPSTREAM:
            row = self._switch_row(preset)
            self._upstream_rows.append((preset, row))
            expander.add_row(row)
        upstream.add(expander)
        page.add(upstream)

        license_group = Adw.PreferencesGroup(title="Licencia y origen")
        license_row = Adw.ActionRow(
            title="game-devices-udev",
            subtitle="MIT · Fabian Bornschein (fabiscafe) · Codeberg/GitHub",
        )
        link = Gtk.LinkButton(uri=PRESETS_URL)
        link.set_label("Abrir")
        link.add_css_class("flat")
        link.set_valign(Gtk.Align.CENTER)
        license_row.add_suffix(link)
        license_group.add(license_row)
        page.add(license_group)

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
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda *_: self.close())
        self.install_button = Gtk.Button(label="Instalar seleccionadas")
        self.install_button.add_css_class("suggested-action")
        self.install_button.connect("clicked", lambda *_: self._install())

        bottom.append(self.summary)
        bottom.append(self.spinner)
        bottom.append(cancel)
        bottom.append(self.install_button)
        toolbar.add_bottom_bar(bottom)
        self.set_child(toolbar)

    def _switch_row(self, preset: Preset) -> Adw.SwitchRow:
        row = Adw.SwitchRow(
            title=preset.title,
            subtitle=preset.description,
        )
        row.set_active(False)
        row.connect("notify::active", lambda *_: self._on_row_toggled())
        return row

    def _selected_presets(self) -> list[Preset]:
        selected = [
            preset
            for preset, row in self._recommended_rows.items()
            if row.get_active()
        ]
        selected.extend(
            preset for preset, row in self._upstream_rows if row.get_active()
        )
        unique: list[Preset] = []
        seen: set[str] = set()
        for preset in selected:
            if preset.install_name in seen:
                continue
            seen.add(preset.install_name)
            unique.append(preset)
        return unique

    def _on_row_toggled(self) -> None:
        if self._updating:
            return
        self._update_summary()

    def _on_all_toggled(self, row: Adw.SwitchRow, _parameter) -> None:
        if self._updating:
            return
        active = row.get_active()
        self._updating = True
        for _preset, vendor_row in self._upstream_rows:
            vendor_row.set_active(active)
        self._updating = False
        self._update_summary()

    def _update_summary(self) -> None:
        selected = self._selected_presets()
        count = len(selected)
        self.summary.set_text(
            f"{count} archivo{'s' if count != 1 else ''} seleccionado"
            f"{'s' if count != 1 else ''}"
        )
        self.install_button.set_sensitive(count > 0 and not self._busy)

        if self._all_row is not None and self._upstream_rows:
            all_active = all(row.get_active() for _preset, row in self._upstream_rows)
            if self._all_row.get_active() != all_active:
                self._updating = True
                self._all_row.set_active(all_active)
                self._updating = False

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
        self.on_installed(
            f"Se instalaron {count} archivo{'s' if count != 1 else ''} de reglas."
        )
        self.close()
        return False

    def _install_failed(self, message: str) -> bool:
        self._set_busy(False)
        dialog = Adw.AlertDialog(
            heading="No se pudieron instalar las reglas",
            body=message,
        )
        dialog.add_response("close", "Cerrar")
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
                "Esperando el diálogo de autenticación de GNOME/polkit…"
            )
            return
        self.spinner.stop()
        self._update_summary()
