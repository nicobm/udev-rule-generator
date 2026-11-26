"""Dispositivos ocultos de la GUI, persistidos en la configuración del usuario."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .devices import Joystick


def default_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "udev-rule-generator" / "hidden.json"
    return Path.home() / ".config" / "udev-rule-generator" / "hidden.json"


def device_identity(device: Joystick) -> str:
    """Identidad estable para ocultar un dispositivo entre reconexiones.

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
    }.get(bus, bus.title() if bus else "Bus desconocido")


@dataclass(frozen=True)
class HiddenDevice:
    """Metadatos de un dispositivo oculto, aunque no esté conectado."""

    id: str
    name: str
    vendor_id: str
    product_id: str
    bus: str
    serial: str
    nodes: tuple[str, ...]
    hidden_at: str

    @property
    def identifier(self) -> str:
        if self.vendor_id and self.product_id:
            return f"{self.vendor_id}:{self.product_id}"
        return "VID/PID desconocido"

    @property
    def bus_label(self) -> str:
        return bus_label(self.bus)

    @classmethod
    def from_joystick(cls, device: Joystick) -> "HiddenDevice":
        return cls(
            id=device_identity(device),
            name=device.display_name,
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            bus=device.bus,
            serial=device.serial,
            nodes=device.nodes,
            hidden_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "HiddenDevice":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "Dispositivo")),
            vendor_id=str(data.get("vendor_id", "")),
            product_id=str(data.get("product_id", "")),
            bus=str(data.get("bus", "")),
            serial=str(data.get("serial", "")),
            nodes=tuple(str(node) for node in data.get("nodes", [])),
            hidden_at=str(data.get("hidden_at", "")),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "bus": self.bus,
            "serial": self.serial,
            "nodes": list(self.nodes),
            "hidden_at": self.hidden_at,
        }


class HiddenDevices:
    """Lista persistente de dispositivos que la GUI no debe mostrar."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()
        self._devices: dict[str, HiddenDevice] = {}
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._devices = {}
            return
        devices = raw.get("devices", {}) if isinstance(raw, dict) else {}
        if not isinstance(devices, dict):
            self._devices = {}
            return
        self._devices = {
            key: HiddenDevice.from_dict(value)
            for key, value in devices.items()
            if isinstance(value, dict)
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "devices": {
                key: device.to_dict() for key, device in self._devices.items()
            },
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary, 0o644)
        os.replace(temporary, self.path)

    def is_hidden(self, device: Joystick) -> bool:
        return device_identity(device) in self._devices

    def hide(self, device: Joystick) -> HiddenDevice:
        hidden = HiddenDevice.from_joystick(device)
        self._devices[hidden.id] = hidden
        try:
            self.save()
        except OSError:
            self._devices.pop(hidden.id, None)
            raise
        return hidden

    def unhide(self, device_id: str) -> HiddenDevice | None:
        hidden = self._devices.pop(device_id, None)
        if hidden is not None:
            try:
                self.save()
            except OSError:
                self._devices[hidden.id] = hidden
                raise
        return hidden

    def devices(self) -> list[HiddenDevice]:
        return sorted(
            self._devices.values(),
            key=lambda device: (device.name.casefold(), device.id),
        )

    def __len__(self) -> int:
        return len(self._devices)
