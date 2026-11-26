"""Permite ejecutar la interfaz de terminal con ``python3 -m udev_rule_generator``."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
