"""Copias de seguridad de dispositivos y reglas generadas."""

from __future__ import annotations

import io
import json
import tarfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath

from . import __version__
from .host import Host, HostError
from .i18n import tr
from .installed import _parse_header, list_installed_rules
from .known import KnownDevices
from .rules import validate_rule_filename

BACKUP_FORMAT = "udev-rule-generator-backup"
BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
DEVICES_NAME = "devices.json"
RULES_PREFIX = "rules/"

_MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
_MAX_MEMBER_BYTES = 8 * 1024 * 1024
_MAX_MEMBERS = 256


class BackupError(RuntimeError):
    """Error de validación o de lectura de una copia de seguridad."""


@dataclass(frozen=True)
class BackupInfo:
    """Resumen de una copia exportada."""

    devices: int
    aliases: int
    rules: tuple[str, ...]
    created_at: str


@dataclass(frozen=True)
class ImportResult:
    """Resumen de una copia importada."""

    devices: int
    aliases: int
    rules: int


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def _add_bytes(
    archive: tarfile.TarFile,
    name: str,
    content: bytes,
    *,
    mtime: int,
) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    info.mode = 0o644
    info.mtime = mtime
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(content))


def create_backup(
    host: Host,
    store: KnownDevices,
) -> tuple[bytes, BackupInfo]:
    """Crea un ``.tar.gz`` con ``devices.json`` y las reglas propias.

    Las reglas de los paquetes externos (steam-devices y
    game-devices-udev) no se incluyen.
    """
    installed = list_installed_rules(host)
    try:
        store.reconcile(installed)
    except OSError:
        # El registro es auxiliar; se exporta lo que haya en memoria.
        pass

    generated = sorted(
        (
            rule
            for rule in installed
            if rule.kind == "generated"
            and rule.filename.startswith("10-")
        ),
        key=lambda rule: rule.filename,
    )
    snapshot = store.snapshot()
    devices = snapshot.get("devices", {})
    aliases = snapshot.get("aliases", {})
    device_count = len(devices) if isinstance(devices, dict) else 0
    alias_count = len(aliases) if isinstance(aliases, dict) else 0
    if not device_count and not alias_count and not generated:
        raise BackupError(
            tr("No hay dispositivos guardados ni reglas para exportar.")
        )

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": created_at,
        "app_version": __version__,
        "devices": device_count,
        "aliases": alias_count,
        "rules": [rule.filename for rule in generated],
    }

    buffer = io.BytesIO()
    mtime = int(time.time())
    with tarfile.open(
        fileobj=buffer,
        mode="w:gz",
        format=tarfile.PAX_FORMAT,
    ) as archive:
        _add_bytes(
            archive,
            MANIFEST_NAME,
            _json_bytes(manifest),
            mtime=mtime,
        )
        _add_bytes(
            archive,
            DEVICES_NAME,
            _json_bytes(snapshot),
            mtime=mtime,
        )
        for rule in generated:
            _add_bytes(
                archive,
                f"{RULES_PREFIX}{rule.filename}",
                rule.content.encode("utf-8"),
                mtime=mtime,
            )

    info = BackupInfo(
        devices=device_count,
        aliases=alias_count,
        rules=tuple(rule.filename for rule in generated),
        created_at=created_at,
    )
    return buffer.getvalue(), info


def _decode_member(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
    *,
    total: int,
) -> tuple[str, int]:
    if member.size > _MAX_MEMBER_BYTES:
        raise BackupError(
            tr("El archivo de copia de seguridad contiene un archivo "
               "demasiado grande.")
        )
    total += member.size
    if total > _MAX_ARCHIVE_BYTES:
        raise BackupError(
            tr("El archivo de copia de seguridad es demasiado grande.")
        )
    handle = archive.extractfile(member)
    if handle is None:
        raise BackupError(
            tr("El archivo de copia de seguridad no es válido.")
        )
    try:
        return handle.read().decode("utf-8"), total
    except UnicodeDecodeError as exc:
        raise BackupError(
            tr("El archivo de copia de seguridad no es válido.")
        ) from exc


def _read_archive(
    data: bytes,
) -> tuple[dict[str, object], dict[str, object], dict[str, str]]:
    if len(data) > _MAX_ARCHIVE_BYTES:
        raise BackupError(
            tr("El archivo de copia de seguridad es demasiado grande.")
        )
    files: dict[str, str] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > _MAX_MEMBERS:
                raise BackupError(
                    tr("El archivo de copia de seguridad no es válido.")
                )
            total = 0
            for member in members:
                name = member.name
                while name.startswith("./"):
                    name = name[2:]
                is_directory = member.isdir()
                if is_directory and name.endswith("/"):
                    name = name[:-1]
                path = PurePosixPath(name)
                if (
                    not name
                    or path.is_absolute()
                    or "\\" in name
                    or any(
                        part in {"", ".", ".."}
                        for part in name.split("/")
                    )
                ):
                    raise BackupError(
                        tr(
                            "El archivo de copia de seguridad contiene una "
                            "ruta no válida."
                        )
                    )
                if is_directory:
                    continue
                if not member.isfile():
                    raise BackupError(
                        tr("El archivo de copia de seguridad no es válido.")
                    )
                if name in files:
                    raise BackupError(
                        tr("El archivo de copia de seguridad no es válido.")
                    )
                content, total = _decode_member(
                    archive,
                    member,
                    total=total,
                )
                files[name] = content
    except tarfile.TarError as exc:
        raise BackupError(
            tr("El archivo de copia de seguridad no es válido.")
        ) from exc

    if DEVICES_NAME not in files:
        raise BackupError(
            tr(
                "El archivo de copia de seguridad no contiene "
                "dispositivos guardados."
            )
        )

    manifest: dict[str, object] = {}
    if MANIFEST_NAME in files:
        try:
            raw_manifest = json.loads(files[MANIFEST_NAME])
        except ValueError as exc:
            raise BackupError(
                tr("El archivo de copia de seguridad no es válido.")
            ) from exc
        if not isinstance(raw_manifest, dict):
            raise BackupError(
                tr("El archivo de copia de seguridad no es válido.")
            )
        if raw_manifest.get("format") != BACKUP_FORMAT:
            raise BackupError(
                tr("El archivo de copia de seguridad no es válido.")
            )
        version = raw_manifest.get("version", BACKUP_VERSION)
        if not isinstance(version, int) or version > BACKUP_VERSION:
            raise BackupError(
                tr("La versión de la copia de seguridad no es compatible.")
            )
        manifest = raw_manifest

    try:
        raw_devices = json.loads(files[DEVICES_NAME])
    except ValueError as exc:
        raise BackupError(
            tr("El archivo de copia de seguridad no es válido.")
        ) from exc
    if not isinstance(raw_devices, dict):
        raise BackupError(
            tr("El archivo de copia de seguridad no es válido.")
        )

    rules: dict[str, str] = {}
    for name, content in files.items():
        if not name.startswith(RULES_PREFIX):
            continue
        filename = name[len(RULES_PREFIX):]
        try:
            validate_rule_filename(filename)
        except ValueError as exc:
            raise BackupError(
                tr("El archivo de copia de seguridad no es válido.")
            ) from exc
        if not filename.startswith("10-"):
            raise BackupError(
                tr(
                    "La regla {filename} no es una regla generada por esta "
                    "aplicación.",
                    filename=filename,
                )
            )
        parsed = _parse_header(filename, content)
        if parsed is None or parsed.kind != "generated":
            raise BackupError(
                tr(
                    "La regla {filename} no es una regla generada por esta "
                    "aplicación.",
                    filename=filename,
                )
            )
        rules[filename] = content

    unexpected = [
        name
        for name in files
        if name not in {MANIFEST_NAME, DEVICES_NAME}
        and not name.startswith(RULES_PREFIX)
    ]
    if unexpected:
        raise BackupError(
            tr("El archivo de copia de seguridad contiene archivos no válidos.")
        )
    return manifest, raw_devices, rules


def import_backup(
    host: Host,
    store: KnownDevices,
    data: bytes,
) -> ImportResult:
    """Importa una copia creada por :func:`create_backup`.

    Solo restaura los datos de los dispositivos y sus alias.  Las reglas
    incluidas no se instalan ni se activan: el usuario puede activarlas
    después desde la ventana principal.
    """
    _manifest, raw_devices, rules = _read_archive(data)
    try:
        imported_devices, imported_aliases = store.merge_snapshot(
            raw_devices,
            active=False,
        )
    except (OSError, ValueError) as exc:
        raise BackupError(str(exc)) from exc

    try:
        store.reconcile(list_installed_rules(host))
    except (HostError, OSError):
        # La copia ya se aplicó; el siguiente refresco reconciliará el estado.
        pass

    return ImportResult(
        devices=imported_devices,
        aliases=imported_aliases,
        rules=len(rules),
    )
