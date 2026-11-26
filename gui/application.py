"""Aplicación Adwaita."""

from __future__ import annotations

from pathlib import Path

from udev_rule_generator import (
    APP_ID,
    APP_NAME,
    APP_SUMMARY,
    ISSUE_URL,
    PROJECT_URL,
    __version__,
)

from .gi_compat import Adw, Gdk, Gio, Gtk


class Application(Adw.Application):
    """Aplicación principal de la GUI."""

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window = None
        self._css_provider = None

    def do_startup(self) -> None:  # noqa: N802 (API de GObject)
        Adw.Application.do_startup(self)
        self._install_css()
        self._add_actions()

    def _install_css(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        try:
            provider = Gtk.CssProvider()
            provider.load_from_path(str(Path(__file__).parent / "style.css"))
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            self._css_provider = provider
        except Exception:
            # El CSS es cosmético: si falla, la aplicación sigue siendo usable.
            self._css_provider = None

        icon_theme = Gtk.IconTheme.get_for_display(display)
        icon_theme.add_search_path(str(Path(__file__).parent / "data" / "icons"))

    def _add_actions(self) -> None:
        actions = (
            ("refresh", self._on_refresh),
            ("presets", self._on_presets),
            ("installed", self._on_installed),
            ("about", self._on_about),
            ("quit", self._on_quit),
        )
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        self.set_accels_for_action("app.refresh", ["<Primary>r"])
        self.set_accels_for_action("app.presets", ["<Primary>p"])
        self.set_accels_for_action("app.installed", ["<Primary>i"])
        self.set_accels_for_action("app.quit", ["<Primary>q"])

    def do_activate(self) -> None:  # noqa: N802 (API de GObject)
        if self.window is None:
            from .window import MainWindow

            self.window = MainWindow(application=self)
            self.window.connect("destroy", self._on_window_destroyed)
        self.window.present()

    def _on_window_destroyed(self, _window) -> None:
        self.window = None

    def _on_refresh(self, _action, _parameter) -> None:
        if self.window is not None:
            self.window.refresh()

    def _on_presets(self, _action, _parameter) -> None:
        if self.window is not None:
            self.window.show_presets()

    def _on_installed(self, _action, _parameter) -> None:
        if self.window is not None:
            self.window.show_installed()

    def _on_about(self, _action, _parameter) -> None:
        if self.window is None:
            return
        license_type = getattr(Gtk.License, "MIT_X11", Gtk.License.MIT)
        dialog = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=APP_ID,
            developer_name="Nicolás (nicobm)",
            version=__version__,
            developers=["Nicolás (nicobm)"],
            copyright="© 2026 Nicolás",
            license_type=license_type,
            website=PROJECT_URL,
            issue_url=ISSUE_URL,
            comments=APP_SUMMARY,
        )
        dialog.present(self.window)

    def _on_quit(self, _action, _parameter) -> None:
        self.quit()
