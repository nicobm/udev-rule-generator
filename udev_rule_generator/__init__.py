"""udev-rule-generator: reglas udev para joysticks y gamepads.

El paquete no depende de bibliotecas externas: toda la detección se hace con
``udevadm`` y los archivos de ``/proc``/``/sys``, y la instalación usa
``pkexec`` para mostrar el diálogo de polkit de GNOME.
"""

from __future__ import annotations

__version__ = "0.18.0"

APP_ID = "io.github.nicobm.UdevRuleGenerator"
APP_NAME = "udev-rule-generator"
APP_SUMMARY = "Crea reglas udev para permitir o ignorar joysticks y gamepads"
PROJECT_URL = "https://github.com/nicobm/udev-rule-generator"
ISSUE_URL = f"{PROJECT_URL}/issues"
STEAM_DEVICES_URL = "https://github.com/ValveSoftware/steam-devices"
RULES_DIR = "/etc/udev/rules.d"


def version_string() -> str:
    """Devuelve la versión con el nombre de la aplicación."""
    from .i18n import tr

    return f"{tr(APP_NAME)} {__version__}"
