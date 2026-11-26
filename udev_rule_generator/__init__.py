"""Generador de reglas udev para joysticks y gamepads.

El paquete no depende de bibliotecas externas: toda la detección se hace con
``udevadm`` y los archivos de ``/proc``/``/sys``, y la instalación usa
``pkexec`` para mostrar el diálogo de polkit de GNOME.
"""

from __future__ import annotations

__version__ = "0.4.0"

APP_ID = "io.github.nicobm.UdevRuleGenerator"
APP_NAME = "Generador de reglas udev"
APP_SUMMARY = "Crea reglas udev para permitir o ignorar joysticks y gamepads"
PROJECT_URL = "https://github.com/nicobm/udev-rule-generator"
ISSUE_URL = f"{PROJECT_URL}/issues"
PRESETS_URL = "https://codeberg.org/fabiscafe/game-devices-udev"
PRESETS_GITHUB_URL = "https://github.com/fabiscafe/game-devices-udev"
STEAM_DEVICES_URL = "https://github.com/ValveSoftware/steam-devices"
RULES_DIR = "/etc/udev/rules.d"


def version_string() -> str:
    """Devuelve la versión con el nombre de la aplicación."""
    return f"{APP_NAME} {__version__}"
