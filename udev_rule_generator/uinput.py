"""Estado del módulo uinput del kernel."""

from __future__ import annotations

import os

from .host import Host, HostError


def uinput_available(host: Host) -> bool:
    """Devuelve si uinput está cargado o compilado en el kernel.

    ``TEST_UINPUT_OFF=1`` permite probar la interfaz como si el módulo no
    estuviera disponible sin descargarlo en el sistema real.
    """
    if os.environ.get("TEST_UINPUT_OFF", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return False

    try:
        if "uinput" in host.list_dir("/sys/module"):
            return True
    except HostError:
        pass

    try:
        modules = host.read_text("/proc/modules")
    except HostError:
        return True
    return any(
        line.split(maxsplit=1)[0] == "uinput"
        for line in modules.splitlines()
        if line.strip()
    )
