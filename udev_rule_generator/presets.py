"""Reglas preconfiguradas incluidas en la aplicación.

Las reglas de fabricantes vienen de ``game-devices-udev`` de Fabian
Bornschein (fabiscafe), publicado bajo licencia MIT.  Las reglas de Steam y
SteamVR vienen de ``steam-devices`` de Valve, también MIT.  Ninguna de estas
fuentes se instala por defecto: Steam y SteamVR solo se instalan si el usuario
las elige, y ``all`` se refiere únicamente a la biblioteca de fabiscafe.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Iterable

from . import (
    PRESETS_GITHUB_URL,
    PRESETS_URL,
    STEAM_DEVICES_URL,
    __version__,
)
from .i18n import tr

_PACKAGE = "udev_rule_generator"

# Título legible para cada archivo del repositorio upstream.
_UPSTREAM_TITLES: dict[str, str] = {
    "8bitdo-gdu.rules": "8BitDo",
    "alpha_imaging_technology_co-gdu.rules": "Alpha Imaging Technology",
    "astro_gaming-gdu.rules": "Astro Gaming",
    "betop-gdu.rules": "Betop",
    "bigscreen-gdu.rules": "Bigscreen",
    "cypress_semiconductor_corp-gdu.rules": "Cypress Semiconductor",
    "google-gdu.rules": "Google (Stadia)",
    "hori-gdu.rules": "Hori",
    "htc-gdu.rules": "HTC (Vive)",
    "logitech-gdu.rules": "Logitech",
    "mad_catz-gdu.rules": "Mad Catz",
    "microsoft-gdu.rules": "Microsoft Xbox",
    "nacon-gdu.rules": "Nacon",
    "nintendo-gdu.rules": "Nintendo",
    "nvidia-gdu.rules": "NVIDIA Shield",
    "pdp-gdu.rules": "PDP",
    "personal_communication_systems_inc-gdu.rules": "PCS (Performance Designed Products)",
    "pid_codes-gdu.rules": "PID Codes",
    "powera-gdu.rules": "PowerA",
    "raspberry_pi_ltd-gdu.rules": "Raspberry Pi",
    "razer-gdu.rules": "Razer",
    "sony-gdu.rules": "Sony PlayStation",
    "thrustmaster-gdu.rules": "Thrustmaster",
    "uinput-dev-early-creation.rules": "uinput (creación temprana)",
    "valve-gdu.rules": "Valve (Steam Controller / Steam Deck)",
    "vkb_sim-gdu.rules": "VKBsim",
    "zeroplus_technology_corporation-gdu.rules": "Zeroplus",
}

_UPSTREAM_ORDER = list(_UPSTREAM_TITLES)


@dataclass(frozen=True)
class Preset:
    """Una regla preconfigurada instalable."""

    id: str
    title: str
    description: str
    source: str
    install_name: str
    category: str
    trigger: str = "change"
    license: str = "MIT"
    upstream: str = PRESETS_URL

    @property
    def is_upstream(self) -> bool:
        return self.category == "upstream"

    @property
    def is_recommended(self) -> bool:
        return self.category == "recommended"

    @property
    def is_steam(self) -> bool:
        return self.category == "steam"


_PRESETS: list[Preset] = [
    Preset(
        id="microsoft-xbox",
        title="Microsoft Xbox",
        description=tr(
            "Permisos para mandos Xbox 360, Xbox One, Xbox Series S|X y "
            "receptores inalámbricos, por USB y Bluetooth."
        ),
        source="microsoft-gdu.rules",
        install_name="71-microsoft-gdu.rules",
        category="recommended",
    ),
    Preset(
        id="steam-input",
        title="Steam Input (Valve)",
        description=tr(
            "Permisos de Valve para Steam Controller, DualShock/DualSense, "
            "mandos de Nintendo y otros dispositivos compatibles con Steam."
        ),
        source="60-steam-input.rules",
        install_name="71-steam-input.rules",
        category="steam",
        license="MIT",
        upstream=STEAM_DEVICES_URL,
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
        category="steam",
        license="MIT",
        upstream=STEAM_DEVICES_URL,
    ),
]

for _source in _UPSTREAM_ORDER:
    _title = _UPSTREAM_TITLES[_source]
    _PRESETS.append(
        Preset(
            id=_source.removesuffix(".rules").removesuffix("-gdu"),
            title=tr(_title),
            description=tr(
                "Reglas de permisos para dispositivos {name} de "
                "game-devices-udev (fabiscafe).",
                name=tr(_title),
            ),
            source=_source,
            install_name=f"71-{_source}",
            category="upstream",
        )
    )

# Recomendadas primero, luego Steam y por último la biblioteca de fabiscafe.
# Se deduplica por el nombre con el que se instala: Microsoft aparece como
# recomendada y también dentro del archivo upstream, pero solo debe instalarse
# una vez.
RECOMMENDED: tuple[Preset, ...] = tuple(
    preset for preset in _PRESETS if preset.is_recommended
)
STEAM: tuple[Preset, ...] = tuple(
    preset for preset in _PRESETS if preset.is_steam
)
UPSTREAM: tuple[Preset, ...] = tuple(
    preset for preset in _PRESETS if preset.is_upstream
)

_ordered: list[Preset] = []
_seen_install_names: set[str] = set()
for _preset in [*RECOMMENDED, *STEAM, *UPSTREAM]:
    if _preset.install_name in _seen_install_names:
        continue
    _seen_install_names.add(_preset.install_name)
    _ordered.append(_preset)
PRESETS: tuple[Preset, ...] = tuple(_ordered)

# "all" significa toda la biblioteca de fabricantes de fabiscafe (incluido
# Microsoft).  No incluye las reglas de Steam/SteamVR: esa es una fuente
# separada y solo se instala si el usuario la elige.
ALL_PRESETS: tuple[Preset, ...] = tuple(
    preset for preset in PRESETS if not preset.is_steam
)


def get_preset(preset_id: str) -> Preset:
    """Busca una regla por id; lanza ``KeyError`` si no existe."""
    for preset in PRESETS:
        if preset.id == preset_id:
            return preset
    raise KeyError(
        tr("No existe la regla preconfigurada {id!r}.", id=preset_id)
    )


_GROUPS: dict[str, tuple[Preset, ...]] = {
    "recommended": RECOMMENDED,
    "recomendadas": RECOMMENDED,
    "recomendado": RECOMMENDED,
    "steam": STEAM,
    "valve": STEAM,
    "steam-devices": STEAM,
    "fabiscafe": ALL_PRESETS,
    "game-devices-udev": ALL_PRESETS,
    "gdu": ALL_PRESETS,
    "all": ALL_PRESETS,
    "todas": ALL_PRESETS,
    "todo": ALL_PRESETS,
}


def select_presets(selection: str) -> list[Preset]:
    """Resuelve grupos y/o ids separados por coma.

    Ejemplos: ``recommended``, ``steam``, ``all``, ``recommended,steam``.
    """
    selection = selection.strip()
    result: list[Preset] = []
    for item in selection.split(","):
        item = item.strip()
        if not item:
            continue
        group = _GROUPS.get(item)
        if group is not None:
            for preset in group:
                if preset not in result:
                    result.append(preset)
            continue
        preset = get_preset(item)
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
    return path.read_text(encoding="utf-8")


def read_license_text() -> str:
    """Texto de la licencia MIT de game-devices-udev."""
    return _preset_dir().joinpath("LICENSE.game-devices-udev").read_text(
        encoding="utf-8"
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
    ]
    if preset.upstream == PRESETS_URL:
        header.append(tr("# Espejo: {url}", url=PRESETS_GITHUB_URL))
    header.append("")
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
