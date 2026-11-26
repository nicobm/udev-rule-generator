"""Dispositivos conocidos y copia de la última regla generada.

La app guarda un JSON pequeño en la configuración del usuario.  No es una base
de datos: alcanza para conservar la metadata del dispositivo y el contenido de
la última regla, de modo que se pueda activar o desactivar sin tener el mando
conectado.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .devices import Joystick
from .i18n import tr
from .installed import InstalledRule
from .rules import RuleAction, RuleSpec, build_rule
from .userconfig import bus_label, default_config_dir, device_identity


def default_path() -> Path:
    return default_config_dir() / "devices.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _strip_transient_comments(content: str) -> str:
    lines = [
        line
        for line in content.splitlines()
        if not line.startswith(("# Nodos: ", "# Nodes: "))
    ]
    return "\n".join(lines).rstrip() + "\n"


def _first(content: str, pattern: str) -> str:
    match = re.search(pattern, content, re.MULTILINE)
    return match.group(1).strip() if match else ""


@dataclass(frozen=True)
class KnownDevice:
    """Metadata y última regla de un dispositivo configurado."""

    id: str
    name: str
    vendor: str
    model: str
    vendor_id: str
    product_id: str
    bus: str
    serial: str
    input_names: tuple[str, ...]
    action: str
    filename: str
    content: str
    sha256: str
    active: bool
    updated_at: str

    @property
    def identifier(self) -> str:
        if self.vendor_id and self.product_id:
            return f"{self.vendor_id}:{self.product_id}"
        return tr("VID/PID desconocido")

    @property
    def bus_label(self) -> str:
        return bus_label(self.bus)

    @property
    def action_label(self) -> str:
        return RuleAction(self.action).label

    def to_joystick(self) -> Joystick:
        return Joystick(
            key=self.id,
            name=self.name,
            vendor=self.vendor,
            model=self.model,
            vendor_id=self.vendor_id,
            product_id=self.product_id,
            serial=self.serial,
            bus=self.bus,
            devpaths=(),
            event_devices=(),
            js_devices=(),
            input_names=self.input_names,
            properties={},
        )

    def build_spec(self) -> RuleSpec:
        """Regenera la regla con el formato actual de la app.

        Cuando hay metadata suficiente se usa el nombre de archivo actual, de
        modo que una regla antigua se migre al activarla de nuevo.
        """
        action = RuleAction(self.action)
        if self.vendor_id and self.product_id and self.name:
            try:
                return build_rule(self.to_joystick(), action)
            except ValueError:
                pass
        trigger = "add" if 'ATTR{authorized}="0"' in self.content else "change"
        return RuleSpec(
            filename=self.filename,
            content=self.content,
            action=action,
            title=self.name,
            trigger=trigger,
        )

    def update_from_spec(self, spec: RuleSpec) -> KnownDevice:
        content = _strip_transient_comments(spec.content)
        return replace(
            self,
            action=spec.action.value,
            filename=spec.filename,
            content=content,
            sha256=_sha256(content),
            active=True,
            updated_at=_now(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "vendor": self.vendor,
            "model": self.model,
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "bus": self.bus,
            "serial": self.serial,
            "input_names": list(self.input_names),
            "action": self.action,
            "filename": self.filename,
            "content": self.content,
            "sha256": self.sha256,
            "active": self.active,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> KnownDevice:
        raw_names = data.get("input_names", [])
        if not isinstance(raw_names, (list, tuple)):
            raw_names = []
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", tr("Dispositivo"))),
            vendor=str(data.get("vendor", "")),
            model=str(data.get("model", "")),
            vendor_id=str(data.get("vendor_id", "")),
            product_id=str(data.get("product_id", "")),
            bus=str(data.get("bus", "")),
            serial=str(data.get("serial", "")),
            input_names=tuple(str(name) for name in raw_names),
            action="ignore" if data.get("action") == "ignore" else "allow",
            filename=str(data.get("filename", "")),
            content=str(data.get("content", "")),
            sha256=str(data.get("sha256", "")),
            active=bool(data.get("active", False)),
            updated_at=str(data.get("updated_at", "")),
        )

    @classmethod
    def from_joystick(cls, device: Joystick, spec: RuleSpec) -> KnownDevice:
        content = _strip_transient_comments(spec.content)
        return cls(
            id=device_identity(device),
            name=device.display_name,
            vendor=device.vendor,
            model=device.model,
            vendor_id=device.vendor_id,
            product_id=device.product_id,
            bus=device.bus,
            serial=device.serial,
            input_names=device.input_names,
            action=spec.action.value,
            filename=spec.filename,
            content=content,
            sha256=_sha256(content),
            active=True,
            updated_at=_now(),
        )

    @classmethod
    def from_installed(cls, rule: InstalledRule) -> KnownDevice:
        content = _strip_transient_comments(rule.content)
        vendor_id = _first(
            content, r'(?:ATTRS|ATTR)\{idVendor\}=="([0-9a-fA-F]{4})"'
        ).lower()
        product_id = _first(
            content, r'(?:ATTRS|ATTR)\{idProduct\}=="([0-9a-fA-F]{4})"'
        ).lower()
        kernel_ids = re.search(
            r'KERNELS=="\*([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\*"', content
        )
        if not vendor_id or not product_id:
            if kernel_ids:
                vendor_id = vendor_id or kernel_ids.group(1).lower()
                product_id = product_id or kernel_ids.group(2).lower()
        if not vendor_id or not product_id:
            header_ids = re.search(
                r"^# Bus: .*ID: ([0-9a-fA-F]{4}):([0-9a-fA-F]{4})",
                content,
                re.MULTILINE,
            )
            if header_ids:
                vendor_id = vendor_id or header_ids.group(1).lower()
                product_id = product_id or header_ids.group(2).lower()
        input_name = _first(
            content, r'(?:ATTRS|ATTR)\{name\}=="([^"]*)"'
        )
        header_name = _first(content, r"^# (?:Dispositivo|Device): (.+)$")
        name = input_name or header_name or rule.title
        bus_text = _first(content, r"^# Bus: (.+)$").lower()
        if "bluetooth" in bus_text:
            bus = "bluetooth"
        elif "usb" in bus_text:
            bus = "usb"
        elif "i2c" in bus_text:
            bus = "i2c"
        elif "pci" in bus_text:
            bus = "pci"
        elif "platform" in bus_text:
            bus = "platform"
        elif 'SUBSYSTEM=="usb"' in content or 'ATTR{authorized}="0"' in content:
            bus = "usb"
        elif kernel_ids or 'KERNELS=="*' in content:
            # Las reglas nuevas no escriben el bus; un KERNELS con VID:PID
            # corresponde a un mando Bluetooth o a otro bus no USB.
            bus = "bluetooth"
        else:
            bus = ""
        serial = _first(content, r"^# Serial: (.+)$")
        action = (
            "ignore"
            if rule.filename.startswith(
                ("99-ignore-", "99-udev-rule-generator-ignore-")
            )
            or 'TAG-="uaccess"' in content
            else "allow"
        )
        if vendor_id and product_id:
            identity = "|".join((vendor_id, product_id, name, serial))
        else:
            identity = f"installed:{rule.filename}"
        return cls(
            id=identity,
            name=name,
            vendor="",
            model="",
            vendor_id=vendor_id,
            product_id=product_id,
            bus=bus,
            serial=serial,
            input_names=(input_name,) if input_name else (),
            action=action,
            filename=rule.filename,
            content=content,
            sha256=_sha256(content),
            active=True,
            updated_at=_now(),
        )


class KnownDevices:
    """Registro persistente de dispositivos configurados."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_path()
        self._devices: dict[str, KnownDevice] = {}
        self._lock = threading.RLock()
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._devices = {}
                return
            devices = raw.get("devices", {}) if isinstance(raw, dict) else {}
            if not isinstance(devices, dict):
                self._devices = {}
                return
            loaded: dict[str, KnownDevice] = {}
            for key, value in devices.items():
                if not isinstance(value, dict):
                    continue
                record = KnownDevice.from_dict(value)
                loaded[record.id or key] = record
            self._devices = loaded

    def save(self) -> None:
        with self._lock:
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

    def record_rule(self, device: Joystick, spec: RuleSpec) -> KnownDevice:
        with self._lock:
            record = KnownDevice.from_joystick(device, spec)
            for key, existing in list(self._devices.items()):
                if existing.filename == record.filename and key != record.id:
                    del self._devices[key]
            self._devices[record.id] = record
            self.save()
            return record

    def update(self, record: KnownDevice) -> KnownDevice:
        self.update_many([record])
        return record

    def update_many(self, records: list[KnownDevice]) -> None:
        with self._lock:
            if not records:
                return
            for record in records:
                self._devices[record.id] = record
            self.save()

    def mark_inactive_by_filename(self, filename: str) -> bool:
        return self.mark_inactive_by_filenames([filename])

    def mark_inactive_by_filenames(self, filenames: list[str]) -> bool:
        with self._lock:
            wanted = set(filenames)
            if not wanted:
                return False
            changed = False
            for key, record in list(self._devices.items()):
                if record.filename in wanted and record.active:
                    self._devices[key] = replace(
                        record, active=False, updated_at=_now()
                    )
                    changed = True
            if changed:
                self.save()
            return changed

    def reconcile(self, installed: list[InstalledRule]) -> None:
        """Sincroniza el registro con lo que hay realmente en /etc."""
        with self._lock:
            by_filename = {
                rule.filename: rule
                for rule in installed
                if rule.kind == "generated"
            }
            changed = False

            for key, record in list(self._devices.items()):
                active = record.filename in by_filename
                if record.active != active:
                    self._devices[key] = replace(
                        record, active=active, updated_at=_now()
                    )
                    changed = True

            known_filenames = {
                record.filename for record in self._devices.values()
            }
            for filename, rule in by_filename.items():
                if filename in known_filenames:
                    continue
                record = KnownDevice.from_installed(rule)
                identity = record.id
                if identity in self._devices:
                    identity = f"{identity}|{filename}"
                    record = replace(record, id=identity)
                self._devices[identity] = record
                known_filenames.add(filename)
                changed = True

            if changed:
                self.save()

    def get(self, device_id: str) -> KnownDevice | None:
        with self._lock:
            return self._devices.get(device_id)

    def devices(self) -> list[KnownDevice]:
        with self._lock:
            return sorted(
                self._devices.values(),
                key=lambda device: (device.name.casefold(), device.id),
            )

    def remove(self, device_id: str) -> KnownDevice | None:
        with self._lock:
            record = self._devices.pop(device_id, None)
            if record is not None:
                self.save()
            return record

    def __len__(self) -> int:
        with self._lock:
            return len(self._devices)
