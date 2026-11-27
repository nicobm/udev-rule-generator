"""Encendido y apagado lógico de dispositivos USB.

Linux expone el atributo ``authorized`` en cada dispositivo USB. Escribir
``0`` lo saca del bus (el equivalente práctico a apagarlo) y escribir ``1``
lo vuelve a enumerar. La lectura del estado no necesita privilegios; el
cambio se hace como root o mediante ``pkexec``, igual que las reglas udev.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .host import CommandResult, Host, HostError
from .i18n import tr

USB_DEVICES_DIR = "/sys/bus/usb/devices"

_USB_SYSNAME = re.compile(r"^[0-9]+-[0-9.]+$")
_USB_DEVICE_IN_DEVPATH = re.compile(
    r"(?:^|/)([0-9]+-[0-9.]+):[0-9]+\.[0-9]+(?:/|$)"
)
_HEX4 = re.compile(r"^[0-9a-f]{4}$")

_POLKIT_CANCELLED = 126
_POLKIT_NOT_AUTHORIZED = 127
_POLKIT_ERROR = 125


@dataclass(frozen=True)
class UsbPowerDevice:
    """Un dispositivo USB y su estado de autorización en el bus."""

    sysname: str
    vendor_id: str
    product_id: str
    serial: str
    product: str
    authorized: bool

    @property
    def identifier(self) -> str:
        if self.vendor_id and self.product_id:
            return f"{self.vendor_id}:{self.product_id}"
        return tr("VID/PID desconocido")

    @property
    def label(self) -> str:
        return self.product or self.identifier


def usb_sysname_from_devpaths(devpaths: Sequence[str]) -> str:
    """Extrae el nombre sysfs del dispositivo USB desde un ``DEVPATH``.

    Un nodo de entrada cuelga de una interfaz USB, por ejemplo
    ``/devices/.../usb1/1-2/1-2:1.0/input/input20/event18``.  El dispositivo
    que se puede apagar es ``1-2``, no la interfaz ``1-2:1.0``.
    """
    for path in devpaths:
        match = _USB_DEVICE_IN_DEVPATH.search(path)
        if match:
            return match.group(1)
    return ""


def _read_attr(host: Host, path: Path) -> str:
    try:
        return host.read_text(path).strip()
    except HostError:
        return ""


def _scan_with_reads(
    host: Host,
    directory: str,
) -> list[UsbPowerDevice]:
    """Respaldo para hosts que no pueden ejecutar el script por lotes."""
    devices: list[UsbPowerDevice] = []
    try:
        entries = host.list_dir(directory)
    except HostError:
        return devices
    for sysname in entries:
        if not _USB_SYSNAME.fullmatch(sysname):
            continue
        base = Path(directory) / sysname
        vendor_id = _read_attr(host, base / "idVendor").lower()
        product_id = _read_attr(host, base / "idProduct").lower()
        if not (
            _HEX4.fullmatch(vendor_id)
            and _HEX4.fullmatch(product_id)
        ):
            continue
        authorized = _read_attr(host, base / "authorized")
        if authorized not in {"0", "1"}:
            continue
        devices.append(
            UsbPowerDevice(
                sysname=sysname,
                vendor_id=vendor_id,
                product_id=product_id,
                serial=_read_attr(host, base / "serial"),
                product=_read_attr(host, base / "product"),
                authorized=authorized == "1",
            )
        )
    return sorted(devices, key=lambda device: device.sysname)


# Una sola invocación evita decenas de procesos cuando la app corre en un
# Flatpak y cada lectura de /sys requiere flatpak-spawn --host.
_USB_SCAN_SCRIPT = """
for dev in "$1"/*; do
  [ -d "$dev" ] || continue
  name=${dev##*/}
  case "$name" in
    *:*) continue ;;
    usb*) continue ;;
  esac
  [ -r "$dev/idVendor" ] || continue
  [ -r "$dev/idProduct" ] || continue
  [ -r "$dev/authorized" ] || continue
  vendor=$(cat "$dev/idVendor" 2>/dev/null || true)
  product=$(cat "$dev/idProduct" 2>/dev/null || true)
  authorized=$(cat "$dev/authorized" 2>/dev/null || true)
  serial=$(cat "$dev/serial" 2>/dev/null || true)
  product_name=$(cat "$dev/product" 2>/dev/null || true)
  printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \
    "$name" "$vendor" "$product" "$authorized" "$serial" "$product_name"
done
"""


def scan_usb_power(
    host: Host,
    *,
    directory: str = USB_DEVICES_DIR,
) -> list[UsbPowerDevice]:
    """Lee los dispositivos USB y su estado de autorización.

    Solo se incluyen dispositivos con VID/PID completos; un dispositivo sin
    identificadores no se puede controlar de forma segura.
    """
    try:
        result = host.run(
            ["sh", "-c", _USB_SCAN_SCRIPT, "udev-rule-generator", directory],
            timeout=20,
        )
    except HostError:
        return _scan_with_reads(host, directory)
    if not result.ok:
        return _scan_with_reads(host, directory)

    devices: list[UsbPowerDevice] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 5)
        if len(parts) != 6:
            continue
        sysname, vendor_id, product_id, authorized, serial, product = parts
        sysname = sysname.strip()
        vendor_id = vendor_id.strip().lower()
        product_id = product_id.strip().lower()
        authorized = authorized.strip()
        if not _USB_SYSNAME.fullmatch(sysname):
            continue
        if not (
            _HEX4.fullmatch(vendor_id)
            and _HEX4.fullmatch(product_id)
        ):
            continue
        if authorized not in {"0", "1"}:
            continue
        devices.append(
            UsbPowerDevice(
                sysname=sysname,
                vendor_id=vendor_id,
                product_id=product_id,
                serial=serial.strip(),
                product=product.strip(),
                authorized=authorized == "1",
            )
        )
    return sorted(devices, key=lambda device: device.sysname)



def find_usb_power(
    devices: Sequence[UsbPowerDevice],
    *,
    vendor_id: str,
    product_id: str,
    serial: str = "",
    sysname: str = "",
    trust_sysname: bool = False,
) -> UsbPowerDevice | None:
    """Busca el dispositivo USB que corresponde a un mando.

    El ``sysname`` de un mando conectado es la forma más fiable. Si no existe,
    se comparan VID, PID y serial. Si hay varios candidatos idénticos no se
    elige ninguno: apagar el mando equivocado sería peor que no mostrar el
    botón.
    """
    if sysname:
        for device in devices:
            if device.sysname != sysname:
                continue
            if vendor_id and device.vendor_id != vendor_id.lower():
                continue
            if product_id and device.product_id != product_id.lower():
                continue
            if (
                not trust_sysname
                and serial
                and device.serial != serial
            ):
                continue
            return device
    vendor_id = (vendor_id or "").lower()
    product_id = (product_id or "").lower()
    candidates = [
        device
        for device in devices
        if device.vendor_id == vendor_id
        and device.product_id == product_id
    ]
    if serial:
        with_serial = [
            device for device in candidates if device.serial == serial
        ]
        if with_serial:
            candidates = with_serial
    return candidates[0] if len(candidates) == 1 else None


def _parent_hub_sysname(sysname: str) -> str:
    if not _USB_SYSNAME.fullmatch(sysname):
        return ""
    if "." in sysname:
        parent, _port = sysname.rsplit(".", 1)
        return parent
    bus, _port = sysname.split("-", 1)
    return f"usb{bus}"


def hub_port_power_switching(
    host: Host,
    sysname: str,
    *,
    directory: str = USB_DEVICES_DIR,
) -> bool | None:
    """Indica si el hub del dispositivo soporta apagado por puerto.

    ``lsusb -v`` muestra ``Per-port power switching`` en los hubs que pueden
    cortar VBUS por puerto. En los que no lo soportan, ``port/disable`` puede
    desconectar el dispositivo pero no volver a enumerarlo, así que no se debe
    usar como apagado normal.
    """
    parent = _parent_hub_sysname(sysname)
    if not parent:
        return None
    base = Path(directory) / parent
    bus = _read_attr(host, base / "busnum")
    address = _read_attr(host, base / "devnum")
    if not bus.isdigit() or not address.isdigit():
        return None
    try:
        result = host.run(
            ["lsusb", "-v", "-s", f"{bus}:{address}"],
            timeout=20,
        )
    except HostError:
        return None
    if not result.ok:
        return None
    output = result.stdout
    if "Per-port power switching" in output:
        return True
    if (
        "No power switching" in output
        or "Ganged power switching" in output
    ):
        return False
    return None


def usb_port_disable_path(
    sysname: str,
    *,
    directory: str = USB_DEVICES_DIR,
) -> str:
    """Devuelve el ``disable`` del puerto USB que contiene al dispositivo.

    Linux 6.0 y posteriores exponen un atributo ``disable`` por puerto. Al
    escribir ``1`` se desconecta el hijo y se apaga el puerto (si el hub
    soporta conmutación de alimentación); al escribir ``0`` se vuelve a
    encender y el dispositivo se reenumera.
    """
    if not _USB_SYSNAME.fullmatch(sysname):
        return ""
    if "." in sysname:
        parent, port = sysname.rsplit(".", 1)
        interface = f"{parent}:1.0"
        port_name = f"{parent}-port{port}"
    else:
        bus, port = sysname.split("-", 1)
        parent = f"usb{bus}"
        interface = f"{bus}-0:1.0"
        port_name = f"{parent}-port{port}"
    if not port.isdigit():
        return ""
    return f"{directory}/{parent}/{interface}/{port_name}/disable"


def read_usb_port_disabled(
    host: Host,
    sysname: str,
    *,
    directory: str = USB_DEVICES_DIR,
) -> bool | None:
    """Indica si el puerto está apagado, o ``None`` si no se puede consultar."""
    path = usb_port_disable_path(sysname, directory=directory)
    if not path:
        return None
    value = _read_attr(host, Path(path))
    if value not in {"0", "1"}:
        return None
    return value == "1"


def read_usb_power(
    host: Host,
    sysname: str,
    *,
    vendor_id: str = "",
    product_id: str = "",
    serial: str = "",
    directory: str = USB_DEVICES_DIR,
) -> UsbPowerDevice | None:
    """Lee un dispositivo USB puntual, sin depender del escaneo por lotes."""
    if not _USB_SYSNAME.fullmatch(sysname):
        return None
    base = Path(directory) / sysname
    found_vendor = _read_attr(host, base / "idVendor").lower()
    found_product = _read_attr(host, base / "idProduct").lower()
    authorized = _read_attr(host, base / "authorized")
    if not (
        _HEX4.fullmatch(found_vendor)
        and _HEX4.fullmatch(found_product)
    ):
        return None
    if authorized not in {"0", "1"}:
        return None
    if vendor_id and found_vendor != vendor_id.lower():
        return None
    if product_id and found_product != product_id.lower():
        return None
    found_serial = _read_attr(host, base / "serial")
    if serial and found_serial != serial:
        return None
    return UsbPowerDevice(
        sysname=sysname,
        vendor_id=found_vendor,
        product_id=found_product,
        serial=found_serial,
        product=_read_attr(host, base / "product"),
        authorized=authorized == "1",
    )


def _pkexec_error_detail(result: CommandResult) -> str:
    detail = (result.stderr or result.stdout).strip()
    if result.returncode == _POLKIT_CANCELLED:
        return tr("Autenticación cancelada. No se cambió el estado.")
    if result.returncode == _POLKIT_NOT_AUTHORIZED:
        message = tr(
            "polkit no autorizó el cambio de estado del dispositivo USB."
        )
    elif result.returncode == _POLKIT_ERROR:
        message = tr("pkexec no pudo iniciar la autenticación.")
    else:
        message = tr(
            "No se pudo cambiar el estado del dispositivo USB "
            "(código {code}).",
            code=result.returncode,
        )
    return f"{message}\n{detail}" if detail else message


def _write_sysfs(host: Host, target: str, value: str) -> None:
    if os.geteuid() == 0 and not host.in_flatpak:
        try:
            Path(target).write_text(value, encoding="ascii")
        except OSError as exc:
            raise HostError(
                tr(
                    "No se pudo escribir {path}: {error}",
                    path=target,
                    error=exc,
                )
            ) from exc
        return

    pkexec = host.which("pkexec")
    if not pkexec:
        raise HostError(
            tr(
                "No se encontró pkexec. Instalá polkit o ejecutá la "
                "aplicación como root."
            )
        )
    result = host.run(
        [
            pkexec,
            "sh",
            "-c",
            'printf "%s\\n" "$1" > "$2"',
            "udev-rule-generator",
            value,
            target,
        ],
        timeout=120,
    )
    if not result.ok:
        raise HostError(_pkexec_error_detail(result))


def _run_privileged_script(
    host: Host,
    script: str,
    *args: str,
    timeout: float = 120,
) -> None:
    if os.geteuid() == 0 and not host.in_flatpak:
        result = host.run(
            ["sh", "-c", script, "udev-rule-generator", *args],
            timeout=timeout,
        )
        if result.ok:
            return
        detail = (result.stderr or result.stdout).strip()
        raise HostError(
            tr("No se pudo reinicializar el dispositivo USB.")
            + (f"\n{detail}" if detail else "")
        )

    pkexec = host.which("pkexec")
    if not pkexec:
        raise HostError(
            tr(
                "No se encontró pkexec. Instalá polkit o ejecutá la "
                "aplicación como root."
            )
        )
    result = host.run(
        [pkexec, "sh", "-c", script, "udev-rule-generator", *args],
        timeout=timeout,
    )
    if not result.ok:
        raise HostError(_pkexec_error_detail(result))


_CONNECT_USB_SCRIPT = r"""
root="$2"
sysname="$1"
target="$3"
value="$4"
printf "%s\n" "$value" > "$target" 2>/dev/null || true
i=0
auth=""
while [ "$i" -lt 25 ]; do
  auth=$(cat "$root/$sysname/authorized" 2>/dev/null || true)
  [ "$auth" = "1" ] && break
  sleep 0.2
  i=$((i + 1))
done
[ "$auth" = "1" ] || exit 0
bus=$(cat "$root/$sysname/busnum" 2>/dev/null || true)
dev=$(cat "$root/$sysname/devnum" 2>/dev/null || true)
[ -n "$bus" ] && [ -n "$dev" ] || exit 0
node=$(printf "/dev/bus/usb/%03d/%03d" "$bus" "$dev")
i=0
while [ ! -e "$node" ] && [ "$i" -lt 10 ]; do
  sleep 0.2
  i=$((i + 1))
done
[ -e "$node" ] || exit 0
if command -v python3 >/dev/null 2>&1; then
  python3 - "$node" <<'PY'
import fcntl
import os
import sys

try:
    fd = os.open(sys.argv[1], os.O_WRONLY)
except OSError:
    sys.exit(0)
try:
    fcntl.ioctl(fd, 0x5514)  # USBDEVFS_RESET
except OSError:
    pass
finally:
    os.close(fd)
PY
elif command -v usbreset >/dev/null 2>&1; then
  usbreset "$bus/$dev" >/dev/null 2>&1 || true
fi
sleep 1
"""


def _run_privileged_python(
    host: Host,
    script: str,
    *args: str,
    timeout: float = 120,
) -> None:
    python3 = host.which("python3")
    if not python3:
        raise HostError(
            tr("No se encontró python3 en el host.")
        )
    if os.geteuid() == 0 and not host.in_flatpak:
        result = host.run(
            [python3, "-c", script, *args],
            timeout=timeout,
        )
    else:
        pkexec = host.which("pkexec")
        if not pkexec:
            raise HostError(
                tr(
                    "No se encontró pkexec. Instalá polkit o ejecutá la "
                    "aplicación como root."
                )
            )
        result = host.run(
            [pkexec, python3, "-c", script, *args],
            timeout=timeout,
        )
    if result.ok:
        return
    detail = (result.stderr or result.stdout).strip()
    raise HostError(
        tr("No se pudo reinicializar el dispositivo USB.")
        + (f"\n{detail}" if detail else "")
    )


_CONNECT_GIP_SCRIPT = r"""
import ctypes
import ctypes.util
import fcntl
import os
import sys
import time
from pathlib import Path

sysname, root, target, value = sys.argv[1:5]

try:
    Path(target).write_text(value, encoding="ascii")
except OSError:
    pass

auth = ""
for _ in range(25):
    try:
        auth = (Path(root) / sysname / "authorized").read_text().strip()
    except OSError:
        auth = ""
    if auth == "1":
        break
    time.sleep(0.2)
if auth != "1":
    sys.exit(0)

try:
    bus = int((Path(root) / sysname / "busnum").read_text().strip())
    address = int((Path(root) / sysname / "devnum").read_text().strip())
except (OSError, ValueError):
    sys.exit(0)

node = f"/dev/bus/usb/{bus:03d}/{address:03d}"

endpoint = 0x02
interface_path = Path(root) / f"{sysname}:1.0"
for entry in sorted(interface_path.glob("ep_*")):
    try:
        endpoint_address = int(entry.name[3:], 16)
    except ValueError:
        continue
    if not endpoint_address & 0x80:
        endpoint = endpoint_address
        break


def send_gip():
    try:
        name = ctypes.util.find_library("usb-1.0") or "libusb-1.0.so.0"
        lib = ctypes.CDLL(name)
    except OSError:
        return False

    c_void_p = ctypes.c_void_p
    lib.libusb_init.argtypes = [ctypes.POINTER(c_void_p)]
    lib.libusb_init.restype = ctypes.c_int
    lib.libusb_get_device_list.argtypes = [
        c_void_p,
        ctypes.POINTER(ctypes.POINTER(c_void_p)),
    ]
    lib.libusb_get_device_list.restype = ctypes.c_ssize_t
    lib.libusb_get_bus_number.argtypes = [c_void_p]
    lib.libusb_get_bus_number.restype = ctypes.c_uint8
    lib.libusb_get_device_address.argtypes = [c_void_p]
    lib.libusb_get_device_address.restype = ctypes.c_uint8
    lib.libusb_open.argtypes = [c_void_p, ctypes.POINTER(c_void_p)]
    lib.libusb_open.restype = ctypes.c_int
    lib.libusb_close.argtypes = [c_void_p]
    lib.libusb_detach_kernel_driver.argtypes = [c_void_p, ctypes.c_int]
    lib.libusb_detach_kernel_driver.restype = ctypes.c_int
    lib.libusb_attach_kernel_driver.argtypes = [c_void_p, ctypes.c_int]
    lib.libusb_attach_kernel_driver.restype = ctypes.c_int
    lib.libusb_claim_interface.argtypes = [c_void_p, ctypes.c_int]
    lib.libusb_claim_interface.restype = ctypes.c_int
    lib.libusb_release_interface.argtypes = [c_void_p, ctypes.c_int]
    lib.libusb_release_interface.restype = ctypes.c_int
    lib.libusb_interrupt_transfer.argtypes = [
        c_void_p,
        ctypes.c_ubyte,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_uint,
    ]
    lib.libusb_interrupt_transfer.restype = ctypes.c_int
    lib.libusb_free_device_list.argtypes = [
        ctypes.POINTER(c_void_p),
        ctypes.c_int,
    ]
    lib.libusb_exit.argtypes = [c_void_p]

    context = c_void_p()
    if lib.libusb_init(ctypes.byref(context)) != 0:
        return False
    devices = ctypes.POINTER(c_void_p)()
    count = lib.libusb_get_device_list(context, ctypes.byref(devices))
    target_device = None
    for index in range(count):
        device = devices[index]
        if (
            lib.libusb_get_bus_number(device) == bus
            and lib.libusb_get_device_address(device) == address
        ):
            target_device = device
            break
    if target_device is None:
        lib.libusb_free_device_list(devices, 1)
        lib.libusb_exit(context)
        return False

    handle = c_void_p()
    if lib.libusb_open(target_device, ctypes.byref(handle)) != 0:
        lib.libusb_free_device_list(devices, 1)
        lib.libusb_exit(context)
        return False

    detached = False
    auto_detached = False
    auto_detach = getattr(
        lib, "libusb_set_auto_detach_kernel_driver", None
    )
    if auto_detach is not None:
        auto_detach.argtypes = [c_void_p, ctypes.c_int]
        auto_detach.restype = ctypes.c_int
        try:
            if auto_detach(handle, 1) == 0:
                detached = True
                auto_detached = True
        except Exception:
            pass
    if not detached:
        try:
            if lib.libusb_detach_kernel_driver(handle, 0) == 0:
                detached = True
        except Exception:
            pass

    if lib.libusb_claim_interface(handle, 0) != 0:
        if detached and not auto_detached:
            try:
                lib.libusb_attach_kernel_driver(handle, 0)
            except Exception:
                pass
        lib.libusb_close(handle)
        lib.libusb_free_device_list(devices, 1)
        lib.libusb_exit(context)
        return False

    packets = [
        bytearray(b"\x05\x20\x00\x01\x00"),
        bytearray(b"\x0a\x20\x00\x03\x00\x01\x14"),
        bytearray(b"\x06\x20\x00\x02\x01\x00"),
    ]
    sent_power = False
    sent_led = False
    for sequence, packet in enumerate(packets):
        packet[2] = sequence
        buffer = ctypes.create_string_buffer(bytes(packet), len(packet))
        transferred = ctypes.c_int()
        result = lib.libusb_interrupt_transfer(
            handle,
            endpoint,
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
            len(packet),
            ctypes.byref(transferred),
            1000,
        )
        if result != 0:
            break
        if sequence == 0:
            sent_power = True
        elif sequence == 1:
            sent_led = True
        time.sleep(0.05)

    lib.libusb_release_interface(handle, 0)
    if detached and not auto_detached:
        try:
            lib.libusb_attach_kernel_driver(handle, 0)
        except Exception:
            pass
    lib.libusb_close(handle)
    lib.libusb_free_device_list(devices, 1)
    lib.libusb_exit(context)
    return sent_power and sent_led


gip_ok = False
try:
    gip_ok = send_gip()
except Exception:
    gip_ok = False

if not gip_ok:
    try:
        descriptor = os.open(node, os.O_WRONLY)
    except OSError:
        descriptor = -1
    if descriptor >= 0:
        try:
            fcntl.ioctl(descriptor, 0x5514)  # USBDEVFS_RESET
        except OSError:
            pass
        finally:
            os.close(descriptor)

time.sleep(1)
"""


def connect_usb_device(
    host: Host,
    sysname: str,
    *,
    directory: str = USB_DEVICES_DIR,
) -> None:
    """Reconecta el USB y envía el encendido GIP al mando.

    Varios mandos Xbox quedan enumerados pero apagados tras un corte lógico
    del USB.  Se envían los paquetes GIP de power-on y LED por libusb; si eso
    no está disponible, se hace un ``USBDEVFS_RESET`` equivalente a
    desenchufar y volver a enchufar el cable.  Todo ocurre en una sola
    ejecución privilegiada.
    """
    if not _USB_SYSNAME.fullmatch(sysname):
        raise ValueError(
            tr("Dispositivo USB no válido: {value!r}", value=sysname)
        )

    port_path = usb_port_disable_path(sysname, directory=directory)
    target = f"{directory}/{sysname}/authorized"
    value = "1"
    if port_path and _read_attr(host, Path(port_path)) == "1":
        target = port_path
        value = "0"

    if host.which("python3"):
        _run_privileged_python(
            host,
            _CONNECT_GIP_SCRIPT,
            sysname,
            directory,
            target,
            value,
        )
        return

    _run_privileged_script(
        host,
        _CONNECT_USB_SCRIPT,
        sysname,
        directory,
        target,
        value,
    )


def set_usb_power(
    host: Host,
    sysname: str,
    powered: bool,
    *,
    directory: str = USB_DEVICES_DIR,
) -> None:
    """Apaga o enciende el puerto USB que contiene al dispositivo.

    Se prefiere el ``disable`` del puerto, que desconecta el hijo y apaga la
    alimentación si el hub lo soporta. Si el kernel no expone esa interfaz, se
    cae al ``authorized`` del dispositivo.
    """
    if not _USB_SYSNAME.fullmatch(sysname):
        raise ValueError(
            tr("Dispositivo USB no válido: {value!r}", value=sysname)
        )

    port_path = usb_port_disable_path(sysname, directory=directory)
    port_disabled: bool | None = None
    if port_path:
        value = _read_attr(host, Path(port_path))
        if value in {"0", "1"}:
            port_disabled = value == "1"

    if not powered:
        if port_path and hub_port_power_switching(
            host, sysname, directory=directory
        ):
            _write_sysfs(host, port_path, "1")
            return
        target = f"{directory}/{sysname}/authorized"
        _write_sysfs(host, target, "0")
        return

    if port_disabled:
        _write_sysfs(host, port_path, "0")
        return
    # El dispositivo está presente pero fue desautorizado con el método
    # anterior, o ya estaba encendido: asegurar authorized=1.
    target = f"{directory}/{sysname}/authorized"
    _write_sysfs(host, target, "1")
