"""Generación y validación de reglas udev."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from . import __version__
from .devices import Joystick
from .i18n import tr

_HEX_RE = re.compile(r"^[0-9a-f]{4}$")
_FILENAME_RE = re.compile(r"^[0-9]{2}-[A-Za-z0-9._+-]+\.rules$")


class RuleAction(str, Enum):
    """Acción que se quiere aplicar al dispositivo."""

    ALLOW = "allow"
    IGNORE = "ignore"

    @property
    def label(self) -> str:
        return tr(
            {
                RuleAction.ALLOW: "Permitir / detectar",
                RuleAction.IGNORE: "Ignorar",
            }[self]
        )

    @property
    def description(self) -> str:
        return tr(
            {
                RuleAction.ALLOW: (
                    "Da permisos de lectura/escritura al usuario de la sesión "
                    "(MODE 0660 y TAG uaccess) y marca el dispositivo como joystick."
                ),
                RuleAction.IGNORE: (
                    "Impide que el dispositivo se use como joystick. En USB se "
                    "desautoriza el dispositivo; en Bluetooth se deniega el acceso "
                    "a los nodos de entrada."
                ),
            }[self]
        )


@dataclass(frozen=True)
class RuleSpec:
    """Una regla lista para previsualizar o instalar."""

    filename: str
    content: str
    action: RuleAction
    title: str
    trigger: str = "change"

    @property
    def target(self) -> str:
        return f"/etc/udev/rules.d/{self.filename}"


def validate_rule_filename(filename: str) -> None:
    """Valida el nombre de un archivo de reglas antes de escribir como root."""
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise ValueError(
            tr("Nombre de regla no válido: {filename!r}", filename=filename)
        )
    if not _FILENAME_RE.fullmatch(filename):
        raise ValueError(
            tr(
                "El nombre de regla debe tener la forma 10-nombre.rules: {filename!r}",
                filename=filename,
            )
        )


def slugify(text: str, max_length: int = 42) -> str:
    """Convierte un nombre de dispositivo en un fragmento de archivo seguro."""
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.casefold()).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "gamepad"


def rule_filename(device: Joystick, action: RuleAction) -> str:
    """Nombre estable y descriptivo para la regla generada."""
    if device.vendor_id and device.product_id:
        hardware = f"{device.vendor_id}-{device.product_id}"
    else:
        digest = hashlib.sha1(device.key.encode("utf-8")).hexdigest()[:8]
        hardware = digest
    kind = "gamepad" if action is RuleAction.ALLOW else "ignore"
    # Las reglas de permiso pueden ir temprano.  Las de ignorar van al final
    # (99-) para que TAG-="uaccess" y MODE="0000" no sean sobrescritos por
    # 70-uaccess.rules ni por las reglas de fabricante instaladas como 71-.
    prefix = "10" if action is RuleAction.ALLOW else "99"
    return f"{prefix}-{kind}-{hardware}-{slugify(device.display_name)}.rules"


def rule_title(device: Joystick, action: RuleAction) -> str:
    verb = tr("Permitir") if action is RuleAction.ALLOW else tr("Ignorar")
    return f"{verb}: {device.display_name}"


def _escape_rule_value(value: str) -> str:
    """Escapa un valor para una comparación ``ATTRS{name}=="..."``."""
    if "\n" in value or "\r" in value:
        raise ValueError(tr("El nombre del dispositivo contiene saltos de línea."))
    if '"' in value:
        # udev no tiene una forma inequívoca de escapar comillas dentro de un
        # valor entrecomillado; es mejor negarse que generar una regla rota.
        raise ValueError(
            tr(
                'El nombre del dispositivo contiene una comilla doble (") y no se '
                "puede escribir de forma segura en una regla udev."
            )
        )
    return value.replace("\\", "\\\\")


def _comment_value(value: str) -> str:
    """Evita que un nombre con saltos de línea inyecte reglas o comentarios."""
    return value.replace("\r", " ").replace("\n", " ")


def _require_ids(device: Joystick) -> None:
    for label, value in (
        ("VID", device.vendor_id),
        ("PID", device.product_id),
    ):
        if value and not _HEX_RE.fullmatch(value):
            raise ValueError(
                tr(
                    "El {label} detectado no es hexadecimal: {value!r}",
                    label=label,
                    value=value,
                )
            )


def _header(device: Joystick) -> list[str]:
    """Encabezado mínimo: origen, línea en blanco y nombre del dispositivo."""
    return [
        tr("# Generado por udev-rule-generator {version}", version=__version__),
        "",
        tr("# Dispositivo: {name}", name=_comment_value(device.display_name)),
    ]


def _allow_usb_line(device: Joystick) -> str:
    return (
        f'ACTION!="remove", SUBSYSTEM=="usb", '
        f'ATTRS{{idVendor}}=="{device.vendor_id}", '
        f'ATTRS{{idProduct}}=="{device.product_id}", '
        f'MODE="0660", TAG+="uaccess"'
    )


def _allow_input_line(device: Joystick) -> str:
    if device.primary_input_name:
        match = (
            f'SUBSYSTEMS=="input", '
            f'ATTRS{{name}}=="{_escape_rule_value(device.primary_input_name)}"'
        )
    elif device.vendor_id and device.product_id:
        if device.is_bluetooth:
            match = (
                f'SUBSYSTEMS=="input", '
                f'KERNELS=="*{device.vendor_id.upper()}:{device.product_id.upper()}*"'
            )
        else:
            match = (
                f'SUBSYSTEMS=="input", '
                f'ATTRS{{idVendor}}=="{device.vendor_id}", '
                f'ATTRS{{idProduct}}=="{device.product_id}"'
            )
    else:
        raise ValueError(
            tr(
                "No se pudo obtener el nombre del dispositivo ni su VID/PID; no se "
                "puede generar una regla de permiso fiable."
            )
        )
    return (
        f'ACTION!="remove", {match}, '
        f'ENV{{ID_INPUT_JOYSTICK}}="1", MODE="0660", TAG+="uaccess"'
    )


def _allow_hidraw_line(device: Joystick) -> str | None:
    if not (device.vendor_id and device.product_id):
        return None
    if device.is_usb or not device.bus:
        return (
            f'ACTION!="remove", SUBSYSTEM=="hidraw", '
            f'ATTRS{{idVendor}}=="{device.vendor_id}", '
            f'ATTRS{{idProduct}}=="{device.product_id}", '
            f'MODE="0660", TAG+="uaccess"'
        )
    return (
        f'ACTION!="remove", KERNEL=="hidraw*", SUBSYSTEM=="hidraw", '
        f'KERNELS=="*{device.vendor_id.upper()}:{device.product_id.upper()}*", '
        f'MODE="0660", TAG+="uaccess"'
    )


def _ignore_usb_line(device: Joystick) -> str:
    return (
        f'ACTION=="add", SUBSYSTEM=="usb", '
        f'ATTR{{idVendor}}=="{device.vendor_id}", '
        f'ATTR{{idProduct}}=="{device.product_id}", '
        f'ATTR{{authorized}}="0"'
    )


def _ignore_input_line(device: Joystick) -> str | None:
    if device.primary_input_name:
        match = (
            f'SUBSYSTEMS=="input", '
            f'ATTRS{{name}}=="{_escape_rule_value(device.primary_input_name)}"'
        )
    elif device.vendor_id and device.product_id:
        if device.is_bluetooth:
            match = (
                f'SUBSYSTEMS=="input", '
                f'KERNELS=="*{device.vendor_id.upper()}:{device.product_id.upper()}*"'
            )
        else:
            match = (
                f'SUBSYSTEMS=="input", '
                f'ATTRS{{idVendor}}=="{device.vendor_id}", '
                f'ATTRS{{idProduct}}=="{device.product_id}"'
            )
    else:
        return None
    return (
        f'ACTION!="remove", {match}, '
        f'ENV{{ID_INPUT_JOYSTICK}}="0", MODE="0000", TAG-="uaccess"'
    )


def _ignore_hidraw_line(device: Joystick) -> str | None:
    if not (device.vendor_id and device.product_id):
        return None
    if device.is_bluetooth or (not device.is_usb and device.bus):
        return (
            f'ACTION!="remove", KERNEL=="hidraw*", SUBSYSTEM=="hidraw", '
            f'KERNELS=="*{device.vendor_id.upper()}:{device.product_id.upper()}*", '
            f'MODE="0000", TAG-="uaccess"'
        )
    return (
        f'ACTION!="remove", SUBSYSTEM=="hidraw", '
        f'ATTRS{{idVendor}}=="{device.vendor_id}", '
        f'ATTRS{{idProduct}}=="{device.product_id}", '
        f'MODE="0000", TAG-="uaccess"'
    )


def build_rule(device: Joystick, action: RuleAction) -> RuleSpec:
    """Construye la regla udev para ``device`` y ``action``."""
    _require_ids(device)
    lines = _header(device)

    if action is RuleAction.ALLOW:
        body: list[str] = []
        if (device.is_usb or not device.bus) and device.vendor_id and device.product_id:
            body.append(_allow_usb_line(device))
        body.append(_allow_input_line(device))
        hidraw = _allow_hidraw_line(device)
        if hidraw:
            body.append(hidraw)
        lines.extend(body)
        trigger = "change"
    else:
        body = []
        if (device.is_usb or not device.bus) and device.vendor_id and device.product_id:
            body.append(_ignore_usb_line(device))
        input_line = _ignore_input_line(device)
        hidraw_line = _ignore_hidraw_line(device)
        if input_line:
            body.append(input_line)
        if hidraw_line:
            body.append(hidraw_line)
        if not body:
            raise ValueError(
                tr("No hay suficientes datos para generar una regla de ignorar.")
            )
        lines.extend(body)
        trigger = (
            "add"
            if (device.is_usb or not device.bus)
            and device.vendor_id
            and device.product_id
            else "change"
        )

    return RuleSpec(
        filename=rule_filename(device, action),
        content="\n".join(lines) + "\n",
        action=action,
        title=rule_title(device, action),
        trigger=trigger,
    )
