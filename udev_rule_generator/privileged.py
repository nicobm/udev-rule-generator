"""Instalación y eliminación de reglas con polkit/pkexec.

Cuando la aplicación corre como usuario normal, ``pkexec`` pide la
autenticación al agente de polkit de la sesión (en GNOME, el diálogo del
sistema).  Si ya se es root, se escribe directamente y no se muestra diálogo.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from . import RULES_DIR
from .host import Host, HostError
from .rules import validate_rule_filename

_POLKIT_CANCELLED = 126
_POLKIT_NOT_AUTHORIZED = 127
_POLKIT_ERROR = 125


@dataclass(frozen=True)
class InstallResult:
    """Resultado de una instalación o eliminación."""

    filenames: tuple[str, ...]
    target_dir: str = RULES_DIR
    used_pkexec: bool = False
    reloaded: bool = False
    trigger: str = "change"
    warning: str | None = None


def _udev_reload_script(trigger: str) -> list[str]:
    """Líneas de shell que recargan udev, sin abortar si falla."""
    lines = [
        "if command -v udevadm >/dev/null 2>&1; then",
        "  udevadm control --reload-rules || true",
    ]
    if trigger == "add":
        lines.append(
            "  udevadm trigger --action=add --subsystem-match=usb --settle || true"
        )
        lines.append(
            "  udevadm trigger --action=change --settle "
            "--subsystem-match=input --subsystem-match=hidraw || true"
        )
    else:
        lines.append("  udevadm trigger --action=change --settle || true")
    lines.append("fi")
    return lines


def _run_udevadm_local(trigger: str) -> bool:
    if not shutil.which("udevadm"):
        return False
    try:
        subprocess.run(
            ["udevadm", "control", "--reload-rules"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if trigger == "add":
            subprocess.run(
                [
                    "udevadm",
                    "trigger",
                    "--action=add",
                    "--subsystem-match=usb",
                    "--settle",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            subprocess.run(
                [
                    "udevadm",
                    "trigger",
                    "--action=change",
                    "--settle",
                    "--subsystem-match=input",
                    "--subsystem-match=hidraw",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        else:
            subprocess.run(
                ["udevadm", "trigger", "--action=change", "--settle"],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def _install_as_root(files: dict[str, str], trigger: str) -> InstallResult:
    installed: list[str] = []
    try:
        os.makedirs(RULES_DIR, exist_ok=True)
        for filename, content in files.items():
            validate_rule_filename(filename)
            target = os.path.join(RULES_DIR, filename)
            temporary = os.path.join(RULES_DIR, f".{filename}.tmp")
            with open(temporary, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
            installed.append(filename)
    except OSError as exc:
        raise HostError(f"No se pudo escribir en {RULES_DIR}: {exc}") from exc
    if shutil.which("restorecon"):
        try:
            subprocess.run(
                ["restorecon", "-F", RULES_DIR],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    reloaded = _run_udevadm_local(trigger)
    warning = None if reloaded else (
        "La regla se instaló, pero no se pudo ejecutar udevadm para recargarla."
    )
    return InstallResult(
        filenames=tuple(installed),
        used_pkexec=False,
        reloaded=reloaded,
        trigger=trigger,
        warning=warning,
    )


def _install_with_pkexec(
    host: Host, files: dict[str, str], trigger: str
) -> InstallResult:
    pkexec = host.which("pkexec")
    if not pkexec:
        raise HostError(
            "No se encontró pkexec. Instalá polkit (en Fedora: sudo dnf install "
            "polkit) o ejecutá la aplicación como root."
        )

    try:
        stage = host.stage_files(files)
    except OSError as exc:
        raise HostError(f"No se pudo preparar el archivo temporal: {exc}") from exc
    try:
        script_lines = [
            "set -eu",
            "install -d -m 0755 /etc/udev/rules.d",
            'install -m 0644 -- "$@" /etc/udev/rules.d/',
            "if command -v restorecon >/dev/null 2>&1; then "
            "restorecon -F /etc/udev/rules.d/ >/dev/null 2>&1 || true; fi",
            *_udev_reload_script(trigger),
        ]
        script = "\n".join(script_lines)
        sources = [str(stage / filename) for filename in files]
        result = host.run(
            [pkexec, "sh", "-c", script, "udev-rule-generator", *sources],
            timeout=600,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            if result.returncode == _POLKIT_CANCELLED:
                raise HostError("Autenticación cancelada. No se instaló nada.")
            if result.returncode == _POLKIT_NOT_AUTHORIZED:
                raise HostError(
                    "polkit no autorizó la operación. No se instaló nada."
                    + (f"\n{detail}" if detail else "")
                )
            if result.returncode == _POLKIT_ERROR:
                raise HostError(
                    "pkexec no pudo iniciar la autenticación."
                    + (f"\n{detail}" if detail else "")
                )
            raise HostError(
                f"La instalación falló (código {result.returncode})."
                + (f"\n{detail}" if detail else "")
            )
        reloaded = host.which("udevadm") is not None
        return InstallResult(
            filenames=tuple(files),
            used_pkexec=True,
            reloaded=reloaded,
            trigger=trigger,
            warning=None
            if reloaded
            else "La regla se instaló, pero no se encontró udevadm para recargarla.",
        )
    finally:
        host.cleanup_stage(stage)


def install_rule_files(
    host: Host,
    files: dict[str, str],
    *,
    trigger: str = "change",
) -> InstallResult:
    """Instala uno o más archivos en ``/etc/udev/rules.d``.

    ``files`` es un diccionario ``nombre_de_archivo -> contenido``.  Los
    nombres se validan antes de pasarlos a root.
    """
    if not files:
        raise ValueError("No hay reglas para instalar.")
    if trigger not in {"change", "add"}:
        raise ValueError(f"Trigger de udev no válido: {trigger!r}")
    for filename in files:
        validate_rule_filename(filename)

    if os.geteuid() == 0 and not host.in_flatpak:
        return _install_as_root(files, trigger)
    return _install_with_pkexec(host, files, trigger)


def _remove_as_root(filenames: list[str]) -> InstallResult:
    removed: list[str] = []
    for filename in filenames:
        validate_rule_filename(filename)
        target = os.path.join(RULES_DIR, filename)
        try:
            os.unlink(target)
            removed.append(filename)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise HostError(f"No se pudo eliminar {target}: {exc}") from exc
    reloaded = _run_udevadm_local("change")
    return InstallResult(
        filenames=tuple(removed),
        used_pkexec=False,
        reloaded=reloaded,
        warning=None if reloaded else "No se pudo ejecutar udevadm.",
    )


def _remove_with_pkexec(host: Host, filenames: list[str]) -> InstallResult:
    pkexec = host.which("pkexec")
    if not pkexec:
        raise HostError(
            "No se encontró pkexec. Instalá polkit o ejecutá la aplicación como root."
        )
    script_lines = [
        "set -eu",
        'rm -f -- "$@"',
        *_udev_reload_script("change"),
    ]
    target_paths = [f"{RULES_DIR}/{filename}" for filename in filenames]
    result = host.run(
        [pkexec, "sh", "-c", "\n".join(script_lines), "udev-rule-generator", *target_paths],
        timeout=600,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        if result.returncode == _POLKIT_CANCELLED:
            raise HostError("Autenticación cancelada. No se eliminó nada.")
        raise HostError(
            f"No se pudieron eliminar las reglas (código {result.returncode})."
            + (f"\n{detail}" if detail else "")
        )
    return InstallResult(
        filenames=tuple(filenames),
        used_pkexec=True,
        reloaded=host.which("udevadm") is not None,
        trigger="change",
    )


def remove_rule_files(host: Host, filenames: list[str]) -> InstallResult:
    """Elimina reglas de ``/etc/udev/rules.d`` y recarga udev."""
    if not filenames:
        raise ValueError("No hay reglas para eliminar.")
    for filename in filenames:
        validate_rule_filename(filename)
    if os.geteuid() == 0 and not host.in_flatpak:
        return _remove_as_root(filenames)
    return _remove_with_pkexec(host, filenames)
