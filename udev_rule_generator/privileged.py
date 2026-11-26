"""Instalación y eliminación de reglas con polkit/pkexec.

Cuando la aplicación corre como usuario normal, ``pkexec`` pide la
autenticación al agente de polkit de la sesión (en GNOME, el diálogo del
sistema).  Si ya se es root, se escribe directamente y no se muestra diálogo.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence

from . import RULES_DIR
from .host import Host, HostError
from .i18n import tr
from .rules import validate_rule_filename

_POLKIT_CANCELLED = 126
_POLKIT_NOT_AUTHORIZED = 127
_POLKIT_ERROR = 125
_HEX4 = re.compile(r"^[0-9a-f]{4}$")
_DRIVER_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class HidBindingChange:
    """Unbind/bind de un dispositivo HID para la sección Ignorados."""

    vendor_id: str
    product_id: str
    bound: bool
    driver: str = ""

    def validate(self) -> None:
        if not _HEX4.fullmatch(self.vendor_id):
            raise ValueError(
                tr("VID no válido: {value!r}", value=self.vendor_id)
            )
        if not _HEX4.fullmatch(self.product_id):
            raise ValueError(
                tr("PID no válido: {value!r}", value=self.product_id)
            )
        if self.driver and not _DRIVER_NAME.fullmatch(self.driver):
            raise ValueError(
                tr("Driver HID no válido: {value!r}", value=self.driver)
            )


def _hid_binding_script(changes: Sequence[HidBindingChange]) -> list[str]:
    """Líneas POSIX sh para desvincular/revincular drivers HID."""
    lines: list[str] = []
    for change in changes:
        change.validate()
        vendor = change.vendor_id.upper()
        product = change.product_id.upper()
        if change.bound:
            driver = change.driver or "hid-generic"
            if not _DRIVER_NAME.fullmatch(driver):
                raise ValueError(
                    tr("Driver HID no válido: {value!r}", value=driver)
                )
            lines.extend(
                [
                    f'for dev in /sys/bus/hid/devices/*{vendor}:{product}*; do',
                    '  [ -e "$dev" ] || continue',
                    "  if [ ! -e \"$dev/driver\" ] && "
                    f'[ -d "/sys/bus/hid/drivers/{driver}" ]; then',
                    '    name=$(basename "$dev")',
                    f'    echo "$name" > "/sys/bus/hid/drivers/{driver}/bind"'
                    " || true",
                    "  fi",
                    "done",
                ]
            )
        else:
            lines.extend(
                [
                    f'for dev in /sys/bus/hid/devices/*{vendor}:{product}*; do',
                    '  [ -e "$dev" ] || continue',
                    '  [ -e "$dev/driver" ] || continue',
                    '  name=$(basename "$dev")',
                    '  driver=$(basename "$(readlink -f "$dev/driver")")',
                    '  [ -n "$driver" ] || continue',
                    '  echo "$name" > "/sys/bus/hid/drivers/$driver/unbind"'
                    " || true",
                    "done",
                ]
            )
    return lines



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
        raise HostError(
            tr(
                "No se pudo escribir en {directory}: {error}",
                directory=RULES_DIR,
                error=exc,
            )
        ) from exc
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
    warning = None if reloaded else tr(
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
            tr(
                "No se encontró pkexec. Instalá polkit (en Fedora: sudo dnf install "
                "polkit) o ejecutá la aplicación como root."
            )
        )

    try:
        stage = host.stage_files(files)
    except OSError as exc:
        raise HostError(
            tr("No se pudo preparar el archivo temporal: {error}", error=exc)
        ) from exc
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
                raise HostError(
                    tr("Autenticación cancelada. No se instaló nada.")
                )
            if result.returncode == _POLKIT_NOT_AUTHORIZED:
                raise HostError(
                    tr("polkit no autorizó la operación. No se instaló nada.")
                    + (f"\n{detail}" if detail else "")
                )
            if result.returncode == _POLKIT_ERROR:
                raise HostError(
                    tr("pkexec no pudo iniciar la autenticación.")
                    + (f"\n{detail}" if detail else "")
                )
            raise HostError(
                tr(
                    "La instalación falló (código {code}).",
                    code=result.returncode,
                )
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
            else tr(
                "La regla se instaló, pero no se encontró udevadm para recargarla."
            ),
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
        raise ValueError(tr("No hay reglas para instalar."))
    if trigger not in {"change", "add"}:
        raise ValueError(
            tr("Trigger de udev no válido: {trigger!r}", trigger=trigger)
        )
    for filename in files:
        validate_rule_filename(filename)

    if os.geteuid() == 0 and not host.in_flatpak:
        return _install_as_root(files, trigger)
    return _install_with_pkexec(host, files, trigger)


def _apply_as_root(
    install_files: dict[str, str],
    remove_filenames: list[str],
    hid_changes: Sequence[HidBindingChange],
    trigger: str,
) -> InstallResult:
    installed: list[str] = []
    try:
        os.makedirs(RULES_DIR, exist_ok=True)
        for filename in remove_filenames:
            validate_rule_filename(filename)
            try:
                os.unlink(os.path.join(RULES_DIR, filename))
            except FileNotFoundError:
                pass
        for filename, content in install_files.items():
            validate_rule_filename(filename)
            target = os.path.join(RULES_DIR, filename)
            temporary = os.path.join(RULES_DIR, f".{filename}.tmp")
            with open(temporary, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
            installed.append(filename)
    except OSError as exc:
        raise HostError(
            tr(
                "No se pudo escribir en {directory}: {error}",
                directory=RULES_DIR,
                error=exc,
            )
        ) from exc
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
    hid_lines = _hid_binding_script(hid_changes)
    if hid_lines:
        try:
            subprocess.run(
                ["sh", "-c", "\n".join(hid_lines)],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HostError(
                tr(
                    "No se pudo cambiar el estado del dispositivo HID: {error}",
                    error=exc,
                )
            ) from exc
    reloaded = _run_udevadm_local(trigger)
    return InstallResult(
        filenames=tuple(installed),
        used_pkexec=False,
        reloaded=reloaded,
        trigger=trigger,
        warning=None
        if reloaded
        else tr("La regla se instaló, pero no se pudo ejecutar udevadm para recargarla."),
    )


def _apply_with_pkexec(
    host: Host,
    install_files: dict[str, str],
    remove_filenames: list[str],
    hid_changes: Sequence[HidBindingChange],
    trigger: str,
) -> InstallResult:
    pkexec = host.which("pkexec")
    if not pkexec:
        raise HostError(
            tr(
                "No se encontró pkexec. Instalá polkit o ejecutá la aplicación como root."
            )
        )

    stage = None
    try:
        script_lines = ["set -eu", "install -d -m 0755 /etc/udev/rules.d"]
        if remove_filenames:
            targets = " ".join(
                f"/etc/udev/rules.d/{filename}" for filename in remove_filenames
            )
            script_lines.append(f"rm -f -- {targets}")
        if install_files:
            try:
                stage = host.stage_files(install_files)
            except OSError as exc:
                raise HostError(
                    tr(
                        "No se pudo preparar el archivo temporal: {error}",
                        error=exc,
                    )
                ) from exc
            script_lines.append('install -m 0644 -- "$@" /etc/udev/rules.d/')
        script_lines.extend(
            [
                "if command -v restorecon >/dev/null 2>&1; then "
                "restorecon -F /etc/udev/rules.d/ >/dev/null 2>&1 || true; fi",
                *_hid_binding_script(hid_changes),
                *_udev_reload_script(trigger),
            ]
        )
        sources = (
            [str(stage / filename) for filename in install_files]
            if stage is not None
            else []
        )
        result = host.run(
            [
                pkexec,
                "sh",
                "-c",
                "\n".join(script_lines),
                "udev-rule-generator",
                *sources,
            ],
            timeout=600,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            if result.returncode == _POLKIT_CANCELLED:
                raise HostError(
                    tr("Autenticación cancelada. No se cambió nada.")
                )
            if result.returncode == _POLKIT_NOT_AUTHORIZED:
                raise HostError(
                    tr("polkit no autorizó la operación. No se cambió nada.")
                    + (f"\n{detail}" if detail else "")
                )
            if result.returncode == _POLKIT_ERROR:
                raise HostError(
                    tr("pkexec no pudo iniciar la autenticación.")
                    + (f"\n{detail}" if detail else "")
                )
            raise HostError(
                tr(
                    "No se pudieron aplicar los cambios (código {code}).",
                    code=result.returncode,
                )
                + (f"\n{detail}" if detail else "")
            )
        reloaded = host.which("udevadm") is not None
        return InstallResult(
            filenames=tuple(install_files),
            used_pkexec=True,
            reloaded=reloaded,
            trigger=trigger,
            warning=None
            if reloaded
            else tr(
                "La regla se instaló, pero no se encontró udevadm para recargarla."
            ),
        )
    finally:
        if stage is not None:
            host.cleanup_stage(stage)


def apply_rule_changes(
    host: Host,
    install_files: dict[str, str],
    remove_filenames: list[str],
    *,
    hid_changes: Sequence[HidBindingChange] = (),
    trigger: str = "change",
) -> InstallResult:
    """Aplica reglas y cambios de binding HID en una sola autenticación."""
    if not install_files and not remove_filenames and not hid_changes:
        raise ValueError(tr("No hay cambios para aplicar."))
    if trigger not in {"change", "add"}:
        raise ValueError(
            tr("Trigger de udev no válido: {trigger!r}", trigger=trigger)
        )
    for filename in install_files:
        validate_rule_filename(filename)
    for filename in remove_filenames:
        validate_rule_filename(filename)
    for change in hid_changes:
        change.validate()

    if os.geteuid() == 0 and not host.in_flatpak:
        return _apply_as_root(
            install_files,
            remove_filenames,
            hid_changes,
            trigger,
        )
    return _apply_with_pkexec(
        host,
        install_files,
        remove_filenames,
        hid_changes,
        trigger,
    )


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
            raise HostError(
                tr(
                    "No se pudo eliminar {path}: {error}",
                    path=target,
                    error=exc,
                )
            ) from exc
    reloaded = _run_udevadm_local("change")
    return InstallResult(
        filenames=tuple(removed),
        used_pkexec=False,
        reloaded=reloaded,
        warning=None if reloaded else tr("No se pudo ejecutar udevadm."),
    )


def _remove_with_pkexec(host: Host, filenames: list[str]) -> InstallResult:
    pkexec = host.which("pkexec")
    if not pkexec:
        raise HostError(
            tr(
                "No se encontró pkexec. Instalá polkit o ejecutá la aplicación como root."
            )
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
            raise HostError(
                tr("Autenticación cancelada. No se eliminó nada.")
            )
        raise HostError(
            tr(
                "No se pudieron eliminar las reglas (código {code}).",
                code=result.returncode,
            )
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
        raise ValueError(tr("No hay reglas para eliminar."))
    for filename in filenames:
        validate_rule_filename(filename)
    if os.geteuid() == 0 and not host.in_flatpak:
        return _remove_as_root(filenames)
    return _remove_with_pkexec(host, filenames)
