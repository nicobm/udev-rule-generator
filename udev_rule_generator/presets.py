"""Paquetes opcionales de reglas udev incluidas en la aplicación.

Las reglas provienen de ``steam-devices`` de Valve y de
``game-devices-udev`` de Fabian Bornschein (fabiscafe), ambos bajo licencia
MIT, y de ``udev-joystick-blacklist`` de Denilson Figueiredo de Sá, de
dominio público.  No se instalan automáticamente: solo se copian si el
usuario activa el interruptor correspondiente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from typing import Iterable

from . import (
    GAME_DEVICES_URL,
    JOYSTICK_BLACKLIST_URL,
    STEAM_DEVICES_URL,
    __version__,
)
from .i18n import tr

_PACKAGE = "udev_rule_generator"

# Valve's Steam rules need one well-known command.  Everything else that could
# execute a program from a compromised upstream repository is rejected.
_ALLOWED_RUN_LINES = frozenset(
    {
        (
            'KERNEL=="input*", ATTRS{name}=="Lic Pro Controller", '
            'RUN{program}+="/bin/sh -c \'udevadm test-builtin uaccess '
            '/sys/%p/../../hidraw/hidraw*\'"'
        ),
        (
            'ACTION!="remove", KERNEL=="input*", '
            'ATTRS{name}=="Lic Pro Controller", '
            'RUN{program}+="/bin/sh -c \'udevadm test-builtin uaccess '
            '/sys/%p/../../hidraw/hidraw*\'"'
        ),
    }
)
_EXECUTABLE_RULE_KEY = re.compile(
    r"(?:^|,\s*)(?:RUN(?:\{[^}]*\})?|PROGRAM|IMPORT(?:\{[^}]*\})?)"
    r"\s*\+?="
)


def validate_rule_text(text: str, *, filename: str = "") -> str:
    """Reject rules that can execute unexpected commands through udev."""
    if "\x00" in text:
        raise ValueError(
            tr(
                "La regla {filename!r} contiene datos binarios no permitidos.",
                filename=filename,
            )
        )
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in _ALLOWED_RUN_LINES:
            continue
        if _EXECUTABLE_RULE_KEY.search(stripped):
            raise ValueError(
                tr(
                    "La regla {filename!r} contiene una directiva ejecutable "
                    "no permitida en la línea {line}.",
                    filename=filename,
                    line=line_number,
                )
            )
    return text


@dataclass(frozen=True)
class Preset:
    """Una regla preconfigurada instalable."""

    id: str
    title: str
    description: str
    source: str
    install_name: str
    category: str = "steam"
    trigger: str = "change"
    license: str = "MIT"
    upstream: str = STEAM_DEVICES_URL


STEAM: tuple[Preset, ...] = (
    Preset(
        id="steam-input",
        title="Steam Input (Valve)",
        description=tr(
            "Permisos de Valve para Steam Controller, DualShock/DualSense, "
            "mandos de Nintendo y otros dispositivos compatibles con Steam."
        ),
        source="60-steam-input.rules",
        install_name="71-steam-input.rules",
    ),
    Preset(
        id="steam-vr",
        title="SteamVR (Valve)",
        description=tr(
            "Permisos de Valve para visores y controladores de SteamVR: "
            "Vive, Valve Index, Bigscreen Beyond y otros."
        ),
        source="60-steam-vr.rules",
        install_name="71-steam-vr.rules",
    ),
)

_GAME_DEVICE_RULES = (
    "8bitdo-gdu.rules",
    "alpha_imaging_technology_co-gdu.rules",
    "astro_gaming-gdu.rules",
    "betop-gdu.rules",
    "bigscreen-gdu.rules",
    "cypress_semiconductor_corp-gdu.rules",
    "google-gdu.rules",
    "hori-gdu.rules",
    "htc-gdu.rules",
    "logitech-gdu.rules",
    "mad_catz-gdu.rules",
    "microsoft-gdu.rules",
    "nacon-gdu.rules",
    "nintendo-gdu.rules",
    "nvidia-gdu.rules",
    "pdp-gdu.rules",
    "personal_communication_systems_inc-gdu.rules",
    "pid_codes-gdu.rules",
    "powera-gdu.rules",
    "raspberry_pi_ltd-gdu.rules",
    "razer-gdu.rules",
    "saitek-gdu.rules",
    "sony-gdu.rules",
    "thrustmaster-gdu.rules",
    "uinput-dev-early-creation.rules",
    "valve-gdu.rules",
    "vkb_sim-gdu.rules",
    "zeroplus_technology_corporation-gdu.rules",
)

GAME_DEVICES: tuple[Preset, ...] = tuple(
    Preset(
        id=source.removesuffix("-gdu.rules").removesuffix(".rules"),
        title=source.removesuffix("-gdu.rules").removesuffix(".rules")
        .replace("_", " ")
        .title(),
        description="",
        source=source,
        install_name=f"71-{source}",
        category="game-devices",
        trigger="add",
        upstream=GAME_DEVICES_URL,
    )
    for source in _GAME_DEVICE_RULES
)

JOYSTICK_BLACKLIST: tuple[Preset, ...] = (
    Preset(
        id="joystick-blacklist",
        title="udev-joystick-blacklist",
        description=tr(
            "Evita que teclados, ratones, tabletas y controladores de LED "
            "que el kernel expone como joysticks aparezcan como mandos."
        ),
        source="51-these-are-not-joysticks-after-kernel-4.9.rules",
        install_name="65-these-are-not-joysticks.rules",
        category="joystick-blacklist",
        trigger="change",
        license="Public domain",
        upstream=JOYSTICK_BLACKLIST_URL,
    ),
)

PRESETS: tuple[Preset, ...] = STEAM + GAME_DEVICES + JOYSTICK_BLACKLIST


def get_preset(preset_id: str) -> Preset:
    """Busca una regla por id; lanza ``KeyError`` si no existe."""
    for preset in PRESETS:
        if preset.id == preset_id:
            return preset
    raise KeyError(
        tr("No existe la regla preconfigurada {id!r}.", id=preset_id)
    )


def select_presets(selection: str) -> list[Preset]:
    """Resuelve paquetes y alias de reglas preconfiguradas."""
    selection = selection.strip()
    result: list[Preset] = []
    for item in selection.split(","):
        item = item.strip().casefold()
        if not item:
            continue
        if item in {"steam", "valve", "steam-devices"}:
            selected = STEAM
        elif item in {
            "game-devices-udev",
            "game-devices",
            "fabiscafe",
            "gdu",
        }:
            selected = GAME_DEVICES
        elif item in {
            "joystick-blacklist",
            "udev-joystick-blacklist",
            "blacklist",
            "denilsonsa",
        }:
            selected = JOYSTICK_BLACKLIST
        elif item == "all":
            selected = PRESETS
        else:
            raise ValueError(
                tr(
                    "Selección no válida: {selection!r}. Usá steam, "
                    "game-devices-udev, udev-joystick-blacklist o all.",
                    selection=item,
                )
            )
        for preset in selected:
            if preset not in result:
                result.append(preset)
    if not result:
        raise ValueError(
            tr("No se seleccionó ninguna regla preconfigurada.")
        )
    return result


def _preset_dir():
    return (
        resources.files(_PACKAGE)
        .joinpath("data")
        .joinpath("presets")
    )


def read_preset_text(preset: Preset) -> str:
    """Devuelve el contenido original de una regla preconfigurada."""
    path = _preset_dir().joinpath(preset.source)
    return validate_rule_text(
        path.read_text(encoding="utf-8"),
        filename=preset.source,
    )


def build_preset_content(preset: Preset) -> str:
    """Añade una cabecera de procedencia y devuelve el archivo final."""
    header = [
        tr("# Instalado por udev-rule-generator {version}", version=__version__),
        tr("# Preconfigurada: {title}", title=preset.title),
        tr(
            "# Origen: {source} ({license})",
            source=preset.upstream,
            license=preset.license,
        ),
        tr("# Archivo original: {source}", source=preset.source),
        "",
    ]
    return "\n".join(header) + read_preset_text(preset).lstrip("\n")


def preset_files(presets: Iterable[Preset]) -> dict[str, str]:
    """Convierte una selección de presets en ``nombre -> contenido``."""
    files: dict[str, str] = {}
    for preset in presets:
        files[preset.install_name] = build_preset_content(preset)
    return files


def presets_trigger(presets: Iterable[Preset]) -> str:
    """``add`` si alguna regla necesita reautorizar USB; ``change`` si no."""
    return "add" if any(preset.trigger == "add" for preset in presets) else "change"
