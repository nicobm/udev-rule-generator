"""Rutas de configuración e identidad estable de los dispositivos."""

from __future__ import annotations

import os
from pathlib import Path

from .devices import Joystick
from .i18n import tr


def default_config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "udev-rule-generator"


def device_identity(device: Joystick) -> str:
    """Identidad estable entre reconexiones.

    Se usa VID/PID, nombre de entrada y serial.  Así no dependemos del path
    USB, que cambia si el mando se conecta en otro puerto.
    """
    name = device.primary_input_name or device.display_name
    return "|".join(
        (
            device.vendor_id,
            device.product_id,
            name,
            device.serial,
        )
    )


def bus_label(bus: str) -> str:
    return {
        "usb": "USB",
        "bluetooth": "Bluetooth",
        "i2c": "I2C",
        "pci": "PCI",
        "platform": "Platform",
    }.get(bus, bus.title() if bus else tr("Bus desconocido"))
