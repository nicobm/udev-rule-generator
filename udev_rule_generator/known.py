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
from .power import usb_sysname_from_devpaths
from .rules import RuleAction, RuleSpec, build_rule
from .userconfig import bus_label, default_config_dir, device_identity


def default_path() -> Path:
    return default_config_dir() / "devices.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _is_legacy_ignore(content: str) -> bool:
    """Detecta reglas antiguas de ignorar que ya no se admiten."""
    return any(
        marker in content
        for marker in (
            'ATTR{authorized}="0"',
            'TAG-="uaccess"',
            'MODE="0000"',
        )
    )


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
    hidden: bool = False
    ignorable: bool = False
    ignored: bool = False
    hid_driver: str = ""
    usb_path: str = ""

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
        return RuleAction.ALLOW.label

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
        action = RuleAction.ALLOW
        if self.vendor_id and self.product_id and self.name:
            try:
                return build_rule(self.to_joystick(), action)
            except ValueError:
                pass
        if _is_legacy_ignore(self.content):
            raise ValueError(
                tr(
                    "Esta regla guardada es de una versión anterior que "
                    "ignoraba el dispositivo y ya no se puede reactivar."
                )
            )
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
            "hidden": self.hidden,
            "ignorable": self.ignorable,
            "ignored": self.ignored,
            "hid_driver": self.hid_driver,
            "usb_path": self.usb_path,
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
            action="allow",
            filename=str(data.get("filename", "")),
            content=str(data.get("content", "")),
            sha256=str(data.get("sha256", "")),
            active=bool(data.get("active", False)),
            updated_at=str(data.get("updated_at", "")),
            hidden=bool(data.get("hidden", False)),
            ignorable=bool(data.get("ignorable", False)),
            ignored=bool(data.get("ignored", False)),
            hid_driver=str(data.get("hid_driver", "")),
            usb_path=str(data.get("usb_path", "")),
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
            ignorable=device.is_ignorable,
            usb_path=usb_sysname_from_devpaths(device.devpaths),
        )

    @classmethod
    def from_ignored(
        cls,
        device: Joystick,
        *,
        driver: str = "",
        ignored: bool = True,
    ) -> KnownDevice:
        """Registro para un dispositivo deshabilitado por unbind del HID.

        No tiene regla udev: el estado se representa desvinculando el driver
        HID del dispositivo.  ``hid_driver`` guarda el driver que hay que
        volver a enlazar cuando se reactive.
        """
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
            action="allow",
            filename="",
            content="",
            sha256="",
            active=False,
            updated_at=_now(),
            ignorable=True,
            ignored=ignored,
            hid_driver=driver,
            usb_path=usb_sysname_from_devpaths(device.devpaths),
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
        action = "allow"
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
        self._aliases: dict[str, str] = {}
        self._icons: dict[str, str] = {}
        self._colors: dict[str, str] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._devices = {}
                self._aliases = {}
                self._icons = {}
                self._colors = {}
                self._order = []
                return
            devices = raw.get("devices", {}) if isinstance(raw, dict) else {}
            if not isinstance(devices, dict):
                self._devices = {}
                self._aliases = {}
                self._icons = {}
                self._colors = {}
                self._order = []
                return
            raw_aliases = raw.get("aliases", {}) if isinstance(raw, dict) else {}
            self._aliases = (
                {
                    str(key): value.strip()
                    for key, value in raw_aliases.items()
                    if isinstance(value, str) and value.strip()
                }
                if isinstance(raw_aliases, dict)
                else {}
            )
            raw_icons = raw.get("icons", {}) if isinstance(raw, dict) else {}
            self._icons = (
                {
                    str(key): value.strip()
                    for key, value in raw_icons.items()
                    if isinstance(value, str) and value.strip()
                }
                if isinstance(raw_icons, dict)
                else {}
            )
            raw_colors = raw.get("colors", {}) if isinstance(raw, dict) else {}
            self._colors = (
                {
                    str(key): value.strip()
                    for key, value in raw_colors.items()
                    if isinstance(value, str) and value.strip()
                }
                if isinstance(raw_colors, dict)
                else {}
            )
            raw_order = raw.get("order", []) if isinstance(raw, dict) else []
            self._order = (
                [str(item) for item in raw_order if isinstance(item, str) and item]
                if isinstance(raw_order, list)
                else []
            )
            loaded: dict[str, KnownDevice] = {}
            for key, value in devices.items():
                if not isinstance(value, dict):
                    continue
                if value.get("action") == "ignore":
                    continue
                record = KnownDevice.from_dict(value)
                if _is_legacy_ignore(record.content):
                    continue
                loaded[record.id or key] = record
            self._devices = loaded

    def snapshot(self) -> dict[str, object]:
        """Devuelve los datos actuales en el mismo formato que ``devices.json``."""
        with self._lock:
            return {
                "version": 1,
                "devices": {
                    key: device.to_dict()
                    for key, device in self._devices.items()
                },
                "aliases": dict(self._aliases),
                "icons": dict(self._icons),
                "colors": dict(self._colors),
                "order": list(self._order),
            }

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = self.snapshot()
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.chmod(temporary, 0o644)
            os.replace(temporary, self.path)

    def merge_snapshot(
        self,
        raw: object,
        *,
        active: bool | None = None,
    ) -> tuple[int, int]:
        """Fusiona un ``devices.json`` importado sin borrar datos locales.

        ``active`` permite forzar el estado de los dispositivos importados.
        Devuelve la cantidad de dispositivos y alias importados.
        """
        if not isinstance(raw, dict):
            raise ValueError(tr("El archivo de dispositivos no es válido."))
        devices = raw.get("devices", {})
        aliases = raw.get("aliases", {})
        icons = raw.get("icons", {})
        colors = raw.get("colors", {})
        if (
            not isinstance(devices, dict)
            or not isinstance(aliases, dict)
            or not isinstance(icons, dict)
            or not isinstance(colors, dict)
        ):
            raise ValueError(tr("El archivo de dispositivos no es válido."))

        imported_devices = 0
        imported_aliases = 0
        with self._lock:
            for key, value in devices.items():
                if not isinstance(value, dict):
                    continue
                if value.get("action") == "ignore":
                    continue
                record = KnownDevice.from_dict(value)
                if _is_legacy_ignore(record.content):
                    continue
                if active is not None:
                    record = replace(record, active=active)
                identity = record.id or str(key)
                if not identity:
                    continue
                self._devices[identity] = record
                imported_devices += 1
            for key, value in aliases.items():
                if not isinstance(value, str) or not value.strip():
                    continue
                self._aliases[str(key)] = value.strip()
                imported_aliases += 1
            for key, value in icons.items():
                if isinstance(value, str) and value.strip():
                    self._icons[str(key)] = value.strip()
            for key, value in colors.items():
                if isinstance(value, str) and value.strip():
                    self._colors[str(key)] = value.strip()
            raw_order = raw.get("order", [])
            if isinstance(raw_order, list):
                imported_order = [
                    str(item)
                    for item in raw_order
                    if isinstance(item, str) and item
                ]
                if imported_order:
                    imported_set = set(imported_order)
                    self._order = imported_order + [
                        item for item in self._order
                        if item not in imported_set
                    ]
            if (
                imported_devices
                or imported_aliases
                or icons
                or colors
                or self._order
            ):
                self.save()
        return imported_devices, imported_aliases

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

    def alias_for(self, device_id: str) -> str:
        with self._lock:
            return self._aliases.get(device_id, "")

    def set_alias(self, device_id: str, alias: str) -> None:
        alias = alias.strip()
        with self._lock:
            if alias:
                self._aliases[device_id] = alias
            else:
                self._aliases.pop(device_id, None)
            self.save()

    def clear_alias(self, device_id: str) -> None:
        with self._lock:
            if self._aliases.pop(device_id, None) is not None:
                self.save()

    def icon_for(self, device_id: str) -> str:
        with self._lock:
            return self._icons.get(device_id, "")

    def set_icon(self, device_id: str, icon: str) -> None:
        icon = icon.strip()
        with self._lock:
            if icon:
                self._icons[device_id] = icon
            else:
                self._icons.pop(device_id, None)
            self.save()

    def color_for(self, device_id: str) -> str:
        with self._lock:
            return self._colors.get(device_id, "")

    def set_color(self, device_id: str, color: str) -> None:
        color = color.strip()
        with self._lock:
            if color:
                self._colors[device_id] = color
            else:
                self._colors.pop(device_id, None)
            self.save()

    def order_index(self, device_id: str) -> int | None:
        with self._lock:
            try:
                return self._order.index(device_id)
            except ValueError:
                return None

    def has_order(self) -> bool:
        with self._lock:
            return bool(self._order)

    def set_order(self, device_ids: list[str]) -> None:
        cleaned: list[str] = []
        for device_id in device_ids:
            if device_id and device_id not in cleaned:
                cleaned.append(device_id)
        with self._lock:
            if self._order == cleaned:
                return
            self._order = cleaned
            self.save()

    def clear_all(self) -> None:
        """Elimina todos los dispositivos, alias, iconos y estados guardados."""
        with self._lock:
            self._devices.clear()
            self._aliases.clear()
            self._icons.clear()
            self._colors.clear()
            self._order.clear()
            self.save()

    def set_usb_path(self, device_id: str, usb_path: str) -> KnownDevice | None:
        """Guarda el nombre sysfs del USB para poder reconectarlo después."""
        if not usb_path:
            return None
        with self._lock:
            record = self._devices.get(device_id)
            if record is None or record.usb_path == usb_path:
                return record
            updated = replace(record, usb_path=usb_path)
            self._devices[device_id] = updated
            self.save()
            return updated

    def set_hidden(self, device_id: str, hidden: bool) -> KnownDevice | None:
        with self._lock:
            record = self._devices.get(device_id)
            if record is None:
                return None
            if record.hidden == hidden:
                return record
            updated = replace(record, hidden=hidden, updated_at=_now())
            self._devices[device_id] = updated
            self.save()
            return updated

    def set_ignored(
        self,
        device_id: str,
        ignored: bool,
        *,
        device: Joystick | None = None,
        driver: str = "",
    ) -> KnownDevice | None:
        """Marca o desmarca un dispositivo como ignorado (HID desvinculado)."""
        with self._lock:
            record = self._devices.get(device_id)
            if record is None:
                if device is None:
                    return None
                record = KnownDevice.from_ignored(
                    device,
                    driver=driver,
                    ignored=ignored,
                )
            updated = replace(
                record,
                ignored=ignored,
                ignorable=True,
                hid_driver=driver or record.hid_driver,
                updated_at=_now(),
            )
            self._devices[device_id] = updated
            self.save()
            return updated

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
                if _is_legacy_ignore(rule.content):
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
            order = {
                device_id: index
                for index, device_id in enumerate(self._order)
            }
            fallback = len(order)
            return sorted(
                self._devices.values(),
                key=lambda device: (
                    order.get(device.id, fallback),
                    device.name.casefold(),
                    device.id,
                ),
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
