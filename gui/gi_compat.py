"""Carga GTK4 y libadwaita una sola vez, con mensajes de error claros."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

__all__ = [
    "Adw",
    "Gdk",
    "Gio",
    "GLib",
    "Gtk",
    "Pango",
    "markup_escape",
]


def markup_escape(value: object) -> str:
    """Escapa texto para widgets de libadwaita que interpretan Pango markup."""
    return GLib.markup_escape_text(str(value))
