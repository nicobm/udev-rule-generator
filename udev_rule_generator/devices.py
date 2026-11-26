"""Detección de joysticks y gamepads conectados.

La fuente principal es ``udevadm info --export-db``, que no necesita permisos
especiales y trae los datos que usan las reglas udev (VID, PID, bus, serial y
``ID_INPUT_JOYSTICK``).  Los nombres reales y las capacidades evdev (``KEY`` y
``ABS``) se obtienen de ``/proc/bus/input/devices`` y, si los nombres fallan,
de ``udevadm info --attribute-walk``.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Mapping

from .host import CommandNotAvailable, Host, HostError
from .i18n import tr

_HEX_RE = re.compile(r"^[0-9a-fA-F]{4}$")
_BITS_PER_WORD = struct.calcsize("P") * 8


# Botones que un joystick/gamepad real suele declarar.  BTN_SELECT,
# BTN_START y BTN_MODE quedan fuera a propósito: los controladores LED falsos
# también los declaran.  Incluye BTN_TRIGGER/BTN_THUMB, botones de volante y
# los botones frontales de gamepad.
_GAMEPAD_BUTTONS = (
    frozenset(range(0x120, 0x13A))
    | {0x13D, 0x13E, 0x150, 0x151}
    | frozenset(range(0x220, 0x224))
    | frozenset(range(0x2C0, 0x2E8))
)


def is_probable_fake_joystick(device: "Joystick") -> bool:
    """Detecta joysticks declarados por error usando sus capacidades evdev.

    Un dispositivo que declara ejes y botones puede hacer que el kernel cree
    un ``js`` aunque no sea un mando.  Un mando real suele declarar botones
    frontales/gatillos; un LED/RGB suele declarar teclas de teclado y ejes
    pero no esos botones.  La comprobación es genérica y no depende del
    nombre ni de un VID:PID concreto.
    """
    if not device.abs_codes or not device.key_codes:
        return False
    return not bool(device.key_codes & _GAMEPAD_BUTTONS)


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
    key_codes: frozenset[int] = field(default_factory=frozenset)
    abs_codes: frozenset[int] = field(default_factory=frozenset)

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
            "key_codes": sorted(self.key_codes),
            "abs_codes": sorted(self.abs_codes),
            "probable_fake": is_probable_fake_joystick(self),
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
    key_codes: frozenset[int] = field(default_factory=frozenset)
    abs_codes: frozenset[int] = field(default_factory=frozenset)


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


def _parse_bitmap(value: str) -> frozenset[int]:
    """Convierte un mapa de bits de ``/proc`` en códigos evdev.

    El kernel escribe los mapas como palabras hexadecimales de ``unsigned
    long``, de mayor a menor: la primera palabra contiene el bloque más alto y
    la última los códigos 0 a ``_BITS_PER_WORD - 1``.
    """
    words = value.split()
    codes: set[int] = set()
    for word_index, word in enumerate(words):
        try:
            bits = int(word, 16)
        except ValueError:
            continue
        block = len(words) - 1 - word_index
        for bit in range(_BITS_PER_WORD):
            if bits & (1 << bit):
                codes.add(block * _BITS_PER_WORD + bit)
    return frozenset(codes)


def parse_proc_blocks(text: str) -> list[ProcInput]:
    """Convierte ``/proc/bus/input/devices`` en una lista de dispositivos."""
    blocks: list[ProcInput] = []
    if not text.strip():
        return blocks
    for block in re.split(r"\n\s*\n", text.strip()):
        name = phys = sysfs = uniq = ""
        handlers: tuple[str, ...] = ()
        vendor_id = product_id = ""
        key_codes: frozenset[int] = frozenset()
        abs_codes: frozenset[int] = frozenset()
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
            elif line.startswith("B: KEY="):
                key_codes = _parse_bitmap(_field(line, "B: KEY="))
            elif line.startswith("B: ABS="):
                abs_codes = _parse_bitmap(_field(line, "B: ABS="))
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
                    key_codes=key_codes,
                    abs_codes=abs_codes,
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


def _is_joystick(properties: Mapping[str, str]) -> bool:
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


def _proc_inputs_for_handlers(
    host: Host, handlers: Iterable[str]
) -> dict[str, ProcInput]:
    try:
        text = host.read_text("/proc/bus/input/devices")
    except HostError:
        return {}
    index = parse_proc_input(text)
    return {
        handler: info
        for handler in handlers
        if (info := index.get(handler)) is not None
    }


def _capabilities_from_sysfs(
    host: Host, event_devices: Iterable[str]
) -> tuple[frozenset[int], frozenset[int]]:
    """Lee ``KEY``/``ABS`` desde ``/sys`` si ``/proc`` no estaba disponible."""
    key_codes: frozenset[int] = frozenset()
    abs_codes: frozenset[int] = frozenset()
    for device in sorted(event_devices):
        handler = Path(device).name
        for kind in ("key", "abs"):
            path = f"/sys/class/input/{handler}/device/capabilities/{kind}"
            try:
                text = host.read_text(path)
            except HostError:
                continue
            codes = _parse_bitmap(text)
            if kind == "key":
                key_codes |= codes
            else:
                abs_codes |= codes
    return key_codes, abs_codes


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
    inputs: Mapping[str, ProcInput],
    host: Host,
    fallback_names: Iterable[str] = (),
) -> Joystick:
    def name_for(device: str) -> str:
        return names.get(Path(device).name) or names.get(device) or ""

    input_infos = [
        inputs[Path(device).name]
        for device in [*sorted(js_devices), *sorted(event_devices)]
        if Path(device).name in inputs
    ]
    key_codes = frozenset().union(*(info.key_codes for info in input_infos))
    abs_codes = frozenset().union(*(info.abs_codes for info in input_infos))
    if not key_codes or not abs_codes:
        sysfs_key, sysfs_abs = _capabilities_from_sysfs(host, event_devices)
        key_codes |= sysfs_key
        abs_codes |= sysfs_abs

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
        key_codes=key_codes,
        abs_codes=abs_codes,
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
    inputs = _proc_inputs_for_handlers(host, handlers)
    names = {
        handler: info.name for handler, info in inputs.items() if info.name
    }

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
            inputs=inputs,
            host=host,
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
        key_codes = info.key_codes
        abs_codes = info.abs_codes
        if not key_codes or not abs_codes:
            sysfs_key, sysfs_abs = _capabilities_from_sysfs(
                host, event_devices
            )
            key_codes |= sysfs_key
            abs_codes |= sysfs_abs
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
                key_codes=key_codes,
                abs_codes=abs_codes,
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


def _device_nodes(device: Joystick) -> set[str]:
    return {*device.event_devices, *device.js_devices}


def _merge_capabilities(device: Joystick, other: Joystick) -> Joystick:
    """Completa las capacidades de ``udevadm`` con las de ``/proc``."""
    key_codes = device.key_codes | other.key_codes
    abs_codes = device.abs_codes | other.abs_codes
    if key_codes == device.key_codes and abs_codes == device.abs_codes:
        return device
    return replace(device, key_codes=key_codes, abs_codes=abs_codes)


def detect_joysticks(host: Host | None = None) -> list[Joystick]:
    """Detecta los joysticks conectados.

    Se intenta primero ``udevadm``.  Si no está instalado o no devuelve nada,
    se usa el fallback de ``/proc``/``/sys``.  Los dispositivos que solo
    aparecen en ``/proc`` se agregan al resultado de udevadm: algunos
    controladores LED tienen un nodo ``js`` pero no llevan
    ``ID_INPUT_JOYSTICK``.
    """
    host = host or Host()
    try:
        result = host.run(["udevadm", "info", "--export-db"], timeout=40)
    except CommandNotAvailable:
        result = None
    except HostError:
        result = None

    udev_devices = (
        joysticks_from_export_db(result.stdout, host)
        if result is not None and result.ok
        else []
    )
    proc_devices = joysticks_from_proc(host)
    if not udev_devices:
        return _deduplicate_and_sort(proc_devices)

    merged = list(udev_devices)
    udev_nodes: dict[str, int] = {}
    for index, device in enumerate(merged):
        for node in _device_nodes(device):
            udev_nodes[node] = index

    for device in proc_devices:
        indexes = {
            udev_nodes[node]
            for node in _device_nodes(device)
            if node in udev_nodes
        }
        if indexes:
            for index in indexes:
                merged[index] = _merge_capabilities(merged[index], device)
        else:
            merged.append(device)

    return _deduplicate_and_sort(merged)


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
