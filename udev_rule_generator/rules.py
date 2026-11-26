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
    """La única acción es habilitar el dispositivo."""

    ALLOW = "allow"

    @property
    def label(self) -> str:
        return tr("Habilitar")

    @property
    def description(self) -> str:
        return tr(
            "Da permisos de lectura/escritura al usuario de la sesión "
            "(MODE 0660 y TAG uaccess) y marca el dispositivo como joystick."
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
    del action  # La única acción válida es habilitar.
    if device.vendor_id and device.product_id:
        hardware = f"{device.vendor_id}-{device.product_id}"
    else:
        digest = hashlib.sha1(device.key.encode("utf-8")).hexdigest()[:8]
        hardware = digest
    return (
        f"10-udev-rule-generator-gamepad-{hardware}-"
        f"{slugify(device.display_name)}.rules"
    )


def rule_title(device: Joystick, action: RuleAction) -> str:
    del action
    return f"{tr('Habilitar')}: {device.display_name}"


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


def build_rule(device: Joystick, action: RuleAction) -> RuleSpec:
    """Construye la regla udev de habilitación para ``device``."""
    del action  # La única acción válida es habilitar.
    _require_ids(device)
    lines = _header(device)

    body: list[str] = []
    if (device.is_usb or not device.bus) and device.vendor_id and device.product_id:
        body.append(_allow_usb_line(device))
    body.append(_allow_input_line(device))
    hidraw = _allow_hidraw_line(device)
    if hidraw:
        body.append(hidraw)
    lines.extend(body)

    return RuleSpec(
        filename=rule_filename(device, RuleAction.ALLOW),
        content="\n".join(lines) + "\n",
        action=RuleAction.ALLOW,
        title=rule_title(device, RuleAction.ALLOW),
        trigger="change",
    )
