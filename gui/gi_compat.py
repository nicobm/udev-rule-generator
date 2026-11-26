"""Carga GTK4 y libadwaita una sola vez, con mensajes de error claros."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

__all__ = ["Adw", "Gdk", "Gio", "GLib", "Gtk", "Pango"]
