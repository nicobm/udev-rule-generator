"""Interfaz gráfica GTK4/libadwaita del generador de reglas udev."""

from __future__ import annotations

__all__ = ["main"]


def main(argv=None):
    from .main import main as run

    return run(argv)
