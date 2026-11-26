"""Diálogo para ver y eliminar las reglas instaladas."""

from __future__ import annotations

import threading
from typing import Callable

from udev_rule_generator.host import Host
from udev_rule_generator.i18n import tr
from udev_rule_generator.installed import InstalledRule, list_installed_rules
from udev_rule_generator.known import KnownDevices
from udev_rule_generator.privileged import remove_rule_files

from .gi_compat import Adw, GLib, Gtk


class InstalledDialog(Adw.Dialog):
    """Lista las reglas administradas y permite eliminarlas."""

    def __init__(
        self,
        *,
        host: Host,
        parent: Gtk.Window,
        known_store: KnownDevices,
        on_changed: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.parent_window = parent
        self.host = host
        self.known_store = known_store
        self.on_changed = on_changed
        self._rules: list[InstalledRule] = []
        self._delete_buttons: list[Gtk.Button] = []
        self._rows: list[Adw.ActionRow] = []
        self._busy = False

        self.set_title(tr("Reglas instaladas"))
        self.set_content_width(720)
        self.set_content_height(680)
        self._build_ui()
        self._reload()

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title=tr("Reglas instaladas"),
                subtitle=tr("Solo las creadas por esta aplicación"),
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
            icon_name="document-open-symbolic",
            title=tr("Leyendo reglas instaladas…"),
        )
        loading.set_child(spinner)
        self.stack.add_named(loading, "loading")

        self.empty_page = Adw.StatusPage(
            icon_name="document-open-symbolic",
            title=tr("No hay reglas administradas"),
            description=tr(
                "Cuando instales una regla desde esta aplicación va a aparecer "
                "acá, con la opción de eliminarla."
            ),
        )
        self.stack.add_named(self.empty_page, "empty")

        self.list_page = Adw.PreferencesPage()
        self.list_page.set_vexpand(True)
        self.group = Adw.PreferencesGroup(
            title=tr("Reglas instaladas"),
            description=tr(
                "Podés eliminar una regla y udev se recargará automáticamente."
            ),
        )
        self.list_page.add(self.group)
        self.stack.add_named(self.list_page, "list")

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

    def _reload(self) -> None:
        self.stack.set_visible_child_name("loading")
        self.status.set_text("")
        thread = threading.Thread(
            target=self._load_worker,
            name="udev-rule-generator-installed",
            daemon=True,
        )
        thread.start()

    def _load_worker(self) -> None:
        try:
            rules = list_installed_rules(self.host)
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._load_failed, str(exc))
            return
        GLib.idle_add(self._load_succeeded, rules)

    def _load_succeeded(self, rules: list[InstalledRule]) -> bool:
        self._rules = rules
        self._populate()
        self.stack.set_visible_child_name("list" if rules else "empty")
        return False

    def _load_failed(self, message: str) -> bool:
        self.stack.set_visible_child_name("empty")
        self.empty_page.set_description(
            tr("No se pudieron leer las reglas: {error}", error=message)
        )
        return False

    def _populate(self) -> None:
        for row in self._rows:
            self.group.remove(row)
        self._rows.clear()
        self._delete_buttons.clear()

        for rule in self._rules:
            kind = tr("generada") if rule.kind == "generated" else tr("preconfigurada")
            subtitle = f"{rule.title} · {kind}"
            if rule.source:
                subtitle = f"{subtitle} · {rule.source}"
            row = Adw.ActionRow(title=rule.filename, subtitle=subtitle)
            row.set_activatable(False)

            delete = Gtk.Button(
                icon_name="user-trash-symbolic",
                tooltip_text=tr("Eliminar {filename}", filename=rule.filename),
            )
            delete.add_css_class("flat")
            delete.add_css_class("destructive-action")
            delete.set_valign(Gtk.Align.CENTER)
            delete.connect(
                "clicked",
                lambda _button, selected=rule: self._confirm_remove(selected),
            )
            row.add_suffix(delete)
            self._delete_buttons.append(delete)
            self.group.add(row)
            self._rows.append(row)

    def _confirm_remove(self, rule: InstalledRule) -> None:
        if self._busy:
            return
        dialog = Adw.AlertDialog(
            heading=tr("¿Eliminar la regla?"),
            body=tr(
                "Se eliminará /etc/udev/rules.d/{filename} y se recargará "
                "udev.  Esta acción necesita autenticación de administrador.",
                filename=rule.filename,
            ),
        )
        dialog.add_response("cancel", tr("Cancelar"))
        dialog.add_response("remove", tr("Eliminar"))
        dialog.set_response_appearance(
            "remove", Adw.ResponseAppearance.DESTRUCTIVE
        )
        dialog.connect(
            "response",
            lambda _dialog, response: self._remove(rule)
            if response == "remove"
            else None,
        )
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)

    def _remove(self, rule: InstalledRule) -> None:
        if self._busy:
            return
        self._set_busy(True)
        thread = threading.Thread(
            target=self._remove_worker,
            args=(rule,),
            name="udev-rule-generator-remove",
            daemon=True,
        )
        thread.start()

    def _remove_worker(self, rule: InstalledRule) -> None:
        try:
            result = remove_rule_files(self.host, [rule.filename])
        except Exception as exc:  # noqa: BLE001 (se muestra al usuario)
            GLib.idle_add(self._remove_failed, str(exc))
            return
        GLib.idle_add(self._remove_succeeded, result)

    def _remove_succeeded(self, result) -> bool:
        self._set_busy(False)
        for filename in result.filenames:
            try:
                self.known_store.mark_inactive_by_filename(filename)
            except OSError:
                # El registro es auxiliar; la regla ya se eliminó.
                pass
            self.on_changed(
                tr("Regla eliminada: {filename}", filename=filename)
            )
        self._reload()
        return False

    def _remove_failed(self, message: str) -> bool:
        self._set_busy(False)
        dialog = Adw.AlertDialog(
            heading=tr("No se pudo eliminar la regla"),
            body=message,
        )
        dialog.add_response("close", tr("Cerrar"))
        root = self.get_root()
        dialog.present(root if root is not None else self.parent_window)
        return False

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in self._delete_buttons:
            button.set_sensitive(not busy)
        self.spinner.set_visible(busy)
        if busy:
            self.spinner.start()
            self.status.set_text(
                tr("Esperando el diálogo de autenticación de GNOME/polkit…")
            )
            return
        self.spinner.stop()
        self.status.set_text("")
