"""Detección de joysticks y gamepads conectados.

La fuente principal es ``udevadm info --export-db``, que no necesita permisos
especiales y trae los datos que usan las reglas udev (VID, PID, bus, serial y
``ID_INPUT_JOYSTICK``).  Los nombres reales de los dispositivos de entrada se
obtienen de ``/proc/bus/input/devices`` y, si eso falla, de
``udevadm info --attribute-walk``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from .host import CommandNotAvailable, Host, HostError
from .i18n import tr
from .power import UsbPowerDevice, scan_usb_power

_HEX_RE = re.compile(r"^[0-9a-fA-F]{4}$")


@dataclass(frozen=True)
class Joystick:
    """Un joystick/gamepad detectado, agrupado por dispositivo físico."""

    key: str
    name: str
    vendor: str
    model: str
    vendor_id: str
    product_id: str
    serial: str
    bus: str
    devpaths: tuple[str, ...]
    event_devices: tuple[str, ...]
    js_devices: tuple[str, ...]
    input_names: tuple[str, ...]
    properties: Mapping[str, str]

    @property
    def display_name(self) -> str:
        return self.name or self.model or tr("Dispositivo de entrada sin nombre")

    @property
    def identifier(self) -> str:
        if self.vendor_id and self.product_id:
            return f"{self.vendor_id}:{self.product_id}"
        return tr("VID/PID desconocido")

    @property
    def bus_label(self) -> str:
        return {
            "usb": "USB",
            "bluetooth": "Bluetooth",
            "i2c": "I2C",
            "pci": "PCI",
            "platform": "Platform",
        }.get(self.bus, self.bus.title() if self.bus else tr("Bus desconocido"))

    @property
    def is_usb(self) -> bool:
        return self.bus == "usb"

    @property
    def is_bluetooth(self) -> bool:
        return self.bus == "bluetooth"

    @property
    def is_ignorable(self) -> bool:
        """¿El kernel lo expone con ``js`` pero udev no lo ve como joystick?

        Es el caso de dispositivos como el LED Controller de ASRock: joydev
        les crea un nodo ``js`` por sus ejes, pero ``input_id`` no les pone
        ``ID_INPUT_JOYSTICK``.  No se comparan modelos ni nombres: el criterio
        sale de las propiedades udev del propio dispositivo.
        """
        if not self.js_devices:
            return False
        if not self.properties:
            # Sin propiedades udev no podemos distinguir un joystick real de
            # un falso positivo; no lo clasificamos por las dudas.
            return False
        value = (self.properties.get("ID_INPUT_JOYSTICK") or "").strip().lower()
        return value not in {"1", "true", "yes"}

    @property
    def nodes(self) -> tuple[str, ...]:
        return self.js_devices or self.event_devices

    @property
    def nodes_label(self) -> str:
        return ", ".join(self.nodes) if self.nodes else tr("sin nodos visibles")

    @property
    def primary_input_name(self) -> str:
        return self.input_names[0] if self.input_names else ""

    @property
    def hardware_label(self) -> str:
        bits = [self.bus_label, self.identifier]
        if self.vendor or self.model:
            bits.append(" ".join(part for part in (self.vendor, self.model) if part))
        return " · ".join(bits)

    def to_dict(self) -> dict[str, object]:
        """Representación serializable, usada por ``--json`` y la GUI."""
        return {
            "name": self.display_name,
            "vendor": self.vendor,
            "model": self.model,
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "identifier": self.identifier,
            "serial": self.serial,
            "bus": self.bus,
            "bus_label": self.bus_label,
            "devpaths": list(self.devpaths),
            "event_devices": list(self.event_devices),
            "js_devices": list(self.js_devices),
            "input_names": list(self.input_names),
            "is_usb": self.is_usb,
            "is_bluetooth": self.is_bluetooth,
        }


@dataclass(frozen=True)
class ProcInput:
    """Un bloque de ``/proc/bus/input/devices``."""

    name: str
    phys: str
    sysfs: str
    uniq: str
    handlers: tuple[str, ...]
    vendor_id: str
    product_id: str


def _decode_udev_encoding(value: str) -> str:
    """Decodifica valores como ``Microsoft\\x20Xbox`` que exporta udev."""

    def replace(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 16))

    return re.sub(r"\\x([0-9a-fA-F]{2})", replace, value)


def _unquote_proc_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _field(line: str, prefix: str) -> str:
    return line[len(prefix) :].strip() if line.startswith(prefix) else ""


def _normalize_hex_id(value: str | None) -> str:
    value = (value or "").strip().lower()
    return value if _HEX_RE.fullmatch(value) else ""


def _bus_from_properties(properties: Mapping[str, str]) -> str:
    bus = (properties.get("ID_BUS") or "").strip().lower()
    if bus:
        return bus
    path = (properties.get("ID_PATH") or properties.get("DEVPATH") or "").lower()
    if "/bluetooth/" in path:
        return "bluetooth"
    if "/usb" in path:
        return "usb"
    if "/i2c" in path:
        return "i2c"
    return ""


def _humanize_udev_name(value: str) -> str:
    value = _decode_udev_encoding(value or "")
    return value.replace("_", " ").strip()


def parse_export_db(text: str) -> list[tuple[str, dict[str, str]]]:
    """Convierte ``udevadm info --export-db`` en pares (devpath, propiedades)."""
    records: list[tuple[str, dict[str, str]]] = []
    if not text.strip():
        return records
    for block in re.split(r"\n\s*\n", text.strip()):
        properties: dict[str, str] = {}
        devpath = ""
        for line in block.splitlines():
            if line.startswith("P: "):
                devpath = line[3:].strip()
            elif line.startswith("E: "):
                key, separator, value = line[3:].partition("=")
                if separator:
                    properties[key.strip()] = value
        if properties:
            records.append((devpath, properties))
    return records


def parse_udev_properties(text: str) -> dict[str, str]:
    """Convierte ``udevadm info --query=property`` en un diccionario."""
    properties: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            properties[key.strip()] = value.strip()
    return properties


def parse_proc_blocks(text: str) -> list[ProcInput]:
    """Convierte ``/proc/bus/input/devices`` en una lista de dispositivos."""
    blocks: list[ProcInput] = []
    if not text.strip():
        return blocks
    for block in re.split(r"\n\s*\n", text.strip()):
        name = phys = sysfs = uniq = ""
        handlers: tuple[str, ...] = ()
        vendor_id = product_id = ""
        for line in block.splitlines():
            if line.startswith("N: Name="):
                name = _unquote_proc_value(_field(line, "N: Name="))
            elif line.startswith("P: Phys="):
                phys = _field(line, "P: Phys=")
            elif line.startswith("S: Sysfs="):
                sysfs = _field(line, "S: Sysfs=")
            elif line.startswith("U: Uniq="):
                uniq = _field(line, "U: Uniq=")
            elif line.startswith("H: Handlers="):
                handlers = tuple(_field(line, "H: Handlers=").split())
            elif line.startswith("I: Bus="):
                match = re.search(
                    r"Vendor=([0-9a-fA-F]{4}).*?Product=([0-9a-fA-F]{4})",
                    line,
                )
                if match:
                    vendor_id = match.group(1).lower()
                    product_id = match.group(2).lower()
        if name:
            blocks.append(
                ProcInput(
                    name=name,
                    phys=phys,
                    sysfs=sysfs,
                    uniq=uniq,
                    handlers=handlers,
                    vendor_id=vendor_id,
                    product_id=product_id,
                )
            )
    return blocks


def parse_proc_input(text: str) -> dict[str, ProcInput]:
    """Índice de ``/proc/bus/input/devices`` por handler (eventX, jsX)."""
    index: dict[str, ProcInput] = {}
    for info in parse_proc_blocks(text):
        for handler in info.handlers:
            if handler.startswith(("event", "js")):
                index[handler] = info
    return index


_AUXILIARY_INPUT_PROPERTIES = (
    "ID_INPUT_ACCELEROMETER",
    "ID_INPUT_GYROSCOPE",
    "ID_INPUT_MAGNETOMETER",
    "ID_INPUT_TOUCHPAD",
    "ID_INPUT_TOUCHSCREEN",
    "ID_INPUT_TABLET",
)
_AUXILIARY_NAME_HINTS = (
    "motion sensors",
    "motion sensor",
    "touchpad",
    "touch pad",
    "accelerometer",
    "gyroscope",
    "magnetometer",
)


def _truthy_property(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


def is_auxiliary_input(device: Joystick) -> bool:
    """Detecta interfaces auxiliares que no son el gamepad principal.

    Sony y otros mandos modernos exponen sensores de movimiento o touchpad
    como dispositivos de entrada separados.  Algunos incluso reciben un nodo
    ``js``.  Se filtran por propiedades udev y, como respaldo, por nombres
    genéricos de categoría; no por VID:PID ni por modelo concreto.
    """
    for key in _AUXILIARY_INPUT_PROPERTIES:
        if _truthy_property(device.properties.get(key)):
            return True
    text = " ".join((device.name, device.model)).casefold()
    return any(hint in text for hint in _AUXILIARY_NAME_HINTS)


def _is_input_interface(properties: Mapping[str, str]) -> bool:
    """Comprueba que la entrada udev sea una interfaz de entrada real.

    El nodo USB del mando también recibe ``ID_INPUT_JOYSTICK=1``, pero no es
    un dispositivo de entrada y no tiene ``eventX``/``jsX``.
    """
    if (properties.get("SUBSYSTEM") or "").strip().lower() == "input":
        return True
    if _truthy_property(properties.get("ID_INPUT")):
        return True
    devname = properties.get("DEVNAME", "")
    return Path(devname).name.startswith(("event", "js")) if devname else False


def _is_joystick(properties: Mapping[str, str]) -> bool:
    if not _is_input_interface(properties):
        return False
    value = (properties.get("ID_INPUT_JOYSTICK") or "").strip().lower()
    if value in {"1", "true", "yes"}:
        return True
    devname = properties.get("DEVNAME", "")
    return Path(devname).name.startswith("js") if devname else False


def _group_key(properties: Mapping[str, str], devpath: str) -> str:
    serial = properties.get("ID_SERIAL") or properties.get("ID_SERIAL_SHORT") or ""
    # eventX y jsX del mismo mando cuelgan del mismo input/inputN.  Es más
    # fiable que ID_PATH, que en algunos buses puede incluir la interfaz.
    path = devpath or properties.get("DEVPATH", "")
    parent = re.sub(r"/(?:event|js)\d+$", "", path)
    if not parent:
        parent = properties.get("ID_PATH") or path
    return f"{serial}|{parent}" if serial else parent or path


def _proc_names_for_handlers(
    host: Host, handlers: Iterable[str]
) -> dict[str, str]:
    try:
        text = host.read_text("/proc/bus/input/devices")
    except HostError:
        return {}
    index = parse_proc_input(text)
    names: dict[str, str] = {}
    for handler in handlers:
        info = index.get(handler)
        if info and info.name:
            names[handler] = info.name
    return names


def _names_from_attribute_walk(host: Host, event_devices: Iterable[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    for device in event_devices:
        result = host.run(
            ["udevadm", "info", "--attribute-walk", "--name", device],
            timeout=20,
        )
        if not result.ok:
            continue
        for line in result.stdout.splitlines():
            match = re.search(r'ATTRS\{name\}=="(.*)"', line)
            if match:
                name = match.group(1).replace('\\"', '"').replace("\\\\", "\\")
                if name:
                    names[Path(device).name] = name
                break
    return names


def _build_joystick(
    base_properties: Mapping[str, str],
    key: str,
    devpaths: set[str],
    event_devices: set[str],
    js_devices: set[str],
    names: Mapping[str, str],
    fallback_names: Iterable[str] = (),
) -> Joystick:
    def name_for(device: str) -> str:
        return names.get(Path(device).name) or names.get(device) or ""

    js_names = [
        name_for(device) for device in sorted(js_devices) if name_for(device)
    ]
    event_names = [
        name_for(device) for device in sorted(event_devices) if name_for(device)
    ]
    all_names: list[str] = []
    for name in [*js_names, *event_names, *fallback_names]:
        if name and name not in all_names:
            all_names.append(name)

    vendor = _humanize_udev_name(
        base_properties.get("ID_VENDOR_FROM_DATABASE")
        or base_properties.get("ID_VENDOR_ENC")
        or base_properties.get("ID_VENDOR")
        or ""
    )
    model = _humanize_udev_name(
        base_properties.get("ID_MODEL_FROM_DATABASE")
        or base_properties.get("ID_MODEL_ENC")
        or base_properties.get("ID_MODEL")
        or ""
    )
    name = all_names[0] if all_names else model
    serial = (
        base_properties.get("ID_SERIAL_SHORT")
        or base_properties.get("ID_SERIAL")
        or ""
    )
    bus = _bus_from_properties(base_properties)
    return Joystick(
        key=key,
        name=name,
        vendor=vendor,
        model=model,
        vendor_id=_normalize_hex_id(base_properties.get("ID_VENDOR_ID")),
        product_id=_normalize_hex_id(base_properties.get("ID_MODEL_ID")),
        serial=serial,
        bus=bus,
        devpaths=tuple(sorted(devpaths)),
        event_devices=tuple(sorted(event_devices)),
        js_devices=tuple(sorted(js_devices)),
        input_names=tuple(all_names),
        properties=dict(base_properties),
    )


def joysticks_from_export_db(text: str, host: Host) -> list[Joystick]:
    """Extrae los joysticks de la salida de ``udevadm info --export-db``."""
    groups: dict[str, dict[str, object]] = {}
    for devpath, properties in parse_export_db(text):
        if not _is_joystick(properties):
            continue
        key = _group_key(properties, devpath)
        group = groups.setdefault(
            key,
            {
                "props": properties,
                "props_are_event": False,
                "devpaths": set(),
                "events": set(),
                "js": set(),
            },
        )
        group["devpaths"].add(properties.get("DEVPATH") or devpath)
        devname = properties.get("DEVNAME", "")
        basename = Path(devname).name
        if basename.startswith("event"):
            group["events"].add(devname)
            if not group["props_are_event"]:
                group["props"] = properties
                group["props_are_event"] = True
        elif basename.startswith("js"):
            group["js"].add(devname)

    if not groups:
        return []

    handlers: set[str] = set()
    for group in groups.values():
        for device in [*group["events"], *group["js"]]:  # type: ignore[misc]
            handlers.add(Path(device).name)
    names = _proc_names_for_handlers(host, handlers)

    all_events = sorted(
        {
            device
            for group in groups.values()
            for device in group["events"]  # type: ignore[union-attr]
        }
    )
    if not names and all_events:
        names.update(_names_from_attribute_walk(host, all_events))

    joysticks = [
        _build_joystick(
            base_properties=group["props"],  # type: ignore[arg-type]
            key=key,
            devpaths=group["devpaths"],  # type: ignore[arg-type]
            event_devices=group["events"],  # type: ignore[arg-type]
            js_devices=group["js"],  # type: ignore[arg-type]
            names=names,
        )
        for key, group in groups.items()
    ]
    return _deduplicate_and_sort(joysticks)


def _infer_bus_from_sysfs(sysfs: str) -> str:
    lowered = sysfs.lower()
    if "/bluetooth/" in lowered:
        return "bluetooth"
    if "/usb" in lowered:
        return "usb"
    if "/i2c" in lowered:
        return "i2c"
    return ""


def joysticks_from_proc(host: Host) -> list[Joystick]:
    """Fallback para sistemas sin ``udevadm``: lee ``/proc`` y ``/sys``."""
    try:
        text = host.read_text("/proc/bus/input/devices")
    except HostError:
        return []

    joysticks: list[Joystick] = []
    for info in parse_proc_blocks(text):
        if not any(handler.startswith("js") for handler in info.handlers):
            continue
        event_devices = {
            f"/dev/input/{handler}"
            for handler in info.handlers
            if handler.startswith("event")
        }
        js_devices = {
            f"/dev/input/{handler}"
            for handler in info.handlers
            if handler.startswith("js")
        }
        bus = _infer_bus_from_sysfs(info.sysfs or info.phys)
        properties = {
            "ID_INPUT_JOYSTICK": "1",
            "ID_VENDOR_ID": info.vendor_id,
            "ID_MODEL_ID": info.product_id,
            "ID_BUS": bus,
            "ID_SERIAL": info.uniq,
            "DEVPATH": info.sysfs,
            "DEVNAME": next(iter(js_devices), ""),
        }
        name = info.name
        joysticks.append(
            Joystick(
                key=info.sysfs or f"{info.vendor_id}:{info.product_id}:{info.phys}",
                name=name,
                vendor="",
                model=name,
                vendor_id=info.vendor_id,
                product_id=info.product_id,
                serial=info.uniq,
                bus=bus,
                devpaths=(info.sysfs,) if info.sysfs else (),
                event_devices=tuple(sorted(event_devices)),
                js_devices=tuple(sorted(js_devices)),
                input_names=(name,) if name else (),
                properties=properties,
            )
        )
    return _deduplicate_and_sort(joysticks)


def _deduplicate_and_sort(joysticks: Iterable[Joystick]) -> list[Joystick]:
    seen: set[str] = set()
    result: list[Joystick] = []
    for joystick in joysticks:
        if joystick.key in seen:
            continue
        seen.add(joystick.key)
        result.append(joystick)
    return sorted(
        result,
        key=lambda item: (
            0 if item.is_usb else 1 if item.is_bluetooth else 2,
            item.display_name.casefold(),
        ),
    )


def _drop_jsless_duplicates(joysticks: Iterable[Joystick]) -> list[Joystick]:
    """Descarta interfaces sin ``js`` que duplican un gamepad con ``js``.

    Algunos mandos exponen una segunda interfaz de entrada con el mismo
    VID:PID y nombre, pero sin nodo ``js``.  No aporta un mando adicional y
    hacía que el mismo dispositivo apareciera dos veces.
    """
    devices = list(joysticks)
    with_js = {
        (
            device.vendor_id,
            device.product_id,
            device.bus,
            device.display_name.casefold(),
        )
        for device in devices
        if device.js_devices
    }
    return [
        device
        for device in devices
        if device.js_devices
        or (
            device.vendor_id,
            device.product_id,
            device.bus,
            device.display_name.casefold(),
        )
        not in with_js
    ]


@dataclass(frozen=True)
class HidDevice:
    """Un dispositivo del subsistema ``hid`` y su estado de binding.

    ``sysname`` es el nombre estable mientras el USB sigue conectado, por
    ejemplo ``0003:26CE:01A2.0006``.  ``driver`` queda vacío cuando el
    dispositivo está desvinculado (unbind).
    """

    identifier: str
    name: str
    sysname: str
    driver: str

    @property
    def bound(self) -> bool:
        return bool(self.driver)


@dataclass(frozen=True)
class Detection:
    """Resultado de una pasada de detección."""

    joysticks: list[Joystick]
    hid_devices: list[HidDevice]
    usb_devices: list[UsbPowerDevice] = field(default_factory=list)


def hid_devices_from_export_db(text: str) -> list[HidDevice]:
    """Extrae los dispositivos HID de ``udevadm info --export-db``."""
    devices: list[HidDevice] = []
    seen: set[str] = set()
    for devpath, properties in parse_export_db(text):
        if (properties.get("SUBSYSTEM") or "").strip().lower() != "hid":
            continue
        hid_id = (properties.get("HID_ID") or "").strip()
        parts = hid_id.split(":")
        if len(parts) != 3:
            continue
        vendor_id = parts[1].strip().lower()[-4:]
        product_id = parts[2].strip().lower()[-4:]
        if not (
            re.fullmatch(r"[0-9a-f]{4}", vendor_id)
            and re.fullmatch(r"[0-9a-f]{4}", product_id)
        ):
            continue
        sysname = Path(devpath).name
        if not sysname or sysname in seen:
            continue
        seen.add(sysname)
        devices.append(
            HidDevice(
                identifier=f"{vendor_id}:{product_id}",
                name=(properties.get("HID_NAME") or "").strip(),
                sysname=sysname,
                driver=(properties.get("DRIVER") or "").strip(),
            )
        )
    return devices


def detect_state(host: Host | None = None) -> Detection:
    """Detecta joysticks y dispositivos HID en una sola lectura de udev."""
    host = host or Host()
    usb_devices = scan_usb_power(host)
    try:
        result = host.run(["udevadm", "info", "--export-db"], timeout=40)
    except CommandNotAvailable:
        result = None
    except HostError:
        result = None

    if result is not None and result.ok:
        joysticks = joysticks_from_export_db(result.stdout, host)
        hid_devices = hid_devices_from_export_db(result.stdout)
        if joysticks:
            return Detection(
                joysticks=_drop_jsless_duplicates(
                    device
                    for device in joysticks
                    if not is_auxiliary_input(device)
                ),
                hid_devices=hid_devices,
                usb_devices=usb_devices,
            )
        return Detection(
            joysticks=_drop_jsless_duplicates(
                device
                for device in joysticks_from_proc(host)
                if not is_auxiliary_input(device)
            ),
            hid_devices=hid_devices,
            usb_devices=usb_devices,
        )

    return Detection(
        joysticks=_drop_jsless_duplicates(
            device
            for device in joysticks_from_proc(host)
            if not is_auxiliary_input(device)
        ),
        hid_devices=[],
        usb_devices=usb_devices,
    )


def detect_joysticks(host: Host | None = None) -> list[Joystick]:
    """Detecta los joysticks conectados.

    Se intenta primero ``udevadm``.  Si no está instalado o no devuelve nada,
    se usa el fallback de ``/proc``/``/sys``.
    """
    return detect_state(host).joysticks


def find_joystick(joysticks: Iterable[Joystick], selector: str) -> Joystick | None:
    """Busca un joystick por índice (1-based), ``VID:PID`` o nombre parcial."""
    selector = selector.strip()
    if not selector:
        return None
    items = list(joysticks)
    if selector.isdigit():
        index = int(selector) - 1
        if 0 <= index < len(items):
            return items[index]
        return None
    lowered = selector.casefold()
    exact = [
        item
        for item in items
        if lowered in {item.identifier.casefold(), item.display_name.casefold()}
    ]
    if exact:
        return exact[0]
    matches = [
        item
        for item in items
        if lowered in item.display_name.casefold()
        or lowered in item.identifier.casefold()
        or lowered in item.name.casefold()
    ]
    return matches[0] if len(matches) == 1 else None
