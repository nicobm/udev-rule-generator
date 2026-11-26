"""udev-rule-generator: reglas udev para joysticks y gamepads.

El paquete no depende de bibliotecas externas: toda la detección se hace con
``udevadm`` y los archivos de ``/proc``/``/sys``, y la instalación usa
``pkexec`` para mostrar el diálogo de polkit de GNOME.
"""

from __future__ import annotations

__version__ = "1.1.4"

APP_ID = "io.github.nicobm.UdevRuleGenerator"
APP_NAME = "udev-rule-generator"
APP_SUMMARY = "Habilita joysticks y gamepads con reglas udev"
PROJECT_URL = "https://github.com/nicobm/udev-rule-generator"
ISSUE_URL = f"{PROJECT_URL}/issues"
STEAM_DEVICES_URL = "https://github.com/ValveSoftware/steam-devices"
GAME_DEVICES_URL = "https://codeberg.org/fabiscafe/game-devices-udev"
RULES_DIR = "/etc/udev/rules.d"


def version_string() -> str:
    """Devuelve la versión con el nombre de la aplicación."""
    from .i18n import tr

    return f"{tr(APP_NAME)} {__version__}"
