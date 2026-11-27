"""Detección de Steam en el host, tanto nativo como Flatpak."""

from __future__ import annotations

from .host import Host, HostError

_FLATPAK_STEAM = "com.valvesoftware.Steam"
_STEAM_PROCESSES = ("steam", "steamwebhelper")


def steam_running(host: Host) -> bool:
    """Indica si Steam está corriendo de forma nativa o dentro de Flatpak.

    Primero se buscan los procesos normales de Steam.  Si no aparecen, se
    consulta ``flatpak ps`` para cubrir el caso de Steam instalado como
    Flatpak.  Cualquier error de host se trata como "no está corriendo" para no
    romper las notificaciones de la aplicación.
    """
    for process in _STEAM_PROCESSES:
        try:
            result = host.run(["pgrep", "-x", process], timeout=10)
        except HostError:
            continue
        if result.ok and result.stdout.strip():
            return True

    try:
        result = host.run(["flatpak", "ps"], timeout=20)
    except HostError:
        return False
    if result.ok and _FLATPAK_STEAM.lower() in result.stdout.lower():
        return True
    return False
