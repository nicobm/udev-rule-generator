"""Punto de entrada de la GUI."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap() -> None:
    """Permite ejecutar ``python3 gui/main.py`` desde el repositorio."""
    if __package__:
        return
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)


def _log(message: str) -> None:
    """Mensaje breve para la terminal; se ve también dentro del Flatpak."""
    print(message, file=sys.stderr, flush=True)


def main(argv=None) -> int:
    _bootstrap()
    from udev_rule_generator import __version__
    from udev_rule_generator.i18n import tr

    arguments = list(sys.argv if argv is None else argv)

    # La GUI también puede actuar como lanzador del CLI, útil dentro del
    # Flatpak: ``flatpak run ... --cli``.
    if "--cli" in arguments[1:]:
        from udev_rule_generator.cli import main as cli_main

        return cli_main([argument for argument in arguments[1:] if argument != "--cli"])

    try:
        from gui.gi_compat import Adw, Gio, Gtk  # noqa: F401
    except (ImportError, ValueError) as exc:
        print(
            tr(
                "No se pudo cargar GTK4/libadwaita.\n"
                "En Fedora instalá:\n"
                "  sudo dnf install python3-gobject gtk4 libadwaita\n\n"
                "Detalle: {error}",
                error=exc,
            ),
            file=sys.stderr,
        )
        return 1

    from gui.application import Application

    application = Application()
    _log(
        tr(
            "Iniciando udev-rule-generator {version}…",
            version=__version__,
        )
    )
    try:
        result = application.run(arguments)
    except KeyboardInterrupt:
        application.shutdown()
        result = 130
    finally:
        _log(tr("Cerrando…"))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
