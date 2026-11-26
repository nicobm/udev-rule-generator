"""Ejecución de comandos en el host, también desde un Flatpak.

La aplicación está pensada para correr tanto instalada de forma nativa como
dentro de un Flatpak.  Dentro de un Flatpak no se puede leer ``/sys`` ni
``/proc`` del host, ni ejecutar ``udevadm`` o ``pkexec`` directamente; para eso
se usa ``flatpak-spawn --host``, que el manifiesto habilita con el permiso
``org.freedesktop.Flatpak``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


class HostError(RuntimeError):
    """Error al ejecutar un comando en el host."""


class CommandNotAvailable(HostError):
    """El comando necesario no está instalado."""


@dataclass(frozen=True)
class CommandResult:
    """Resultado de un comando."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return self.stdout.strip() or self.stderr.strip()


def _safe_filename(name: str) -> str:
    """Comprueba que un nombre de archivo temporal no contenga rutas."""
    if not name or name in {".", ".."} or Path(name).name != name:
        raise ValueError(f"Nombre de archivo no válido: {name!r}")
    return name


class Host:
    """Pequeña capa sobre ``subprocess`` consciente de Flatpak."""

    def __init__(self, *, in_flatpak: bool | None = None) -> None:
        self.in_flatpak = Path("/.flatpak-info").exists() if in_flatpak is None else in_flatpak
        self._flatpak_spawn = shutil.which("flatpak-spawn") if self.in_flatpak else None

    @property
    def uses_flatpak_spawn(self) -> bool:
        return self.in_flatpak

    def _wrap(self, argv: Sequence[str]) -> list[str]:
        args = [str(arg) for arg in argv]
        if not self.in_flatpak:
            return args
        if not self._flatpak_spawn:
            raise HostError(
                "La aplicación se está ejecutando dentro de un Flatpak, pero no "
                "se encontró flatpak-spawn. Revisá la instalación de Flatpak."
            )
        return [self._flatpak_spawn, "--host", *args]

    def run(
        self,
        argv: Sequence[str],
        *,
        input: str | None = None,
        timeout: float = 60,
        check: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        """Ejecuta un comando y devuelve su salida.

        ``input`` se envía por stdin.  El comando se ejecuta en el host cuando
        la aplicación corre dentro de un Flatpak.
        """
        args = [str(arg) for arg in argv]
        command = self._wrap(args)
        try:
            process = subprocess.run(
                command,
                input=input,
                text=True,
                capture_output=True,
                timeout=timeout,
                env=None if env is None else dict(env),
            )
        except FileNotFoundError as exc:
            raise CommandNotAvailable(f"No se encontró el comando {args[0]!r}.") from exc
        except subprocess.TimeoutExpired as exc:
            raise HostError(
                f"El comando {' '.join(args)!r} tardó más de {timeout:g} segundos."
            ) from exc
        except OSError as exc:
            raise HostError(f"No se pudo ejecutar {args[0]!r}: {exc}") from exc

        result = CommandResult(
            argv=tuple(args),
            returncode=process.returncode,
            stdout=process.stdout or "",
            stderr=process.stderr or "",
        )
        if check and not result.ok:
            raise HostError(self._format_error(result))
        return result

    def popen(
        self,
        argv: Sequence[str],
        *,
        stdout: int | None = subprocess.PIPE,
        stderr: int | None = subprocess.STDOUT,
    ) -> subprocess.Popen[str]:
        """Lanza un proceso de larga duración (por ejemplo, ``udevadm monitor``).

        El proceso se ejecuta en el host cuando la app corre dentro de un
        Flatpak.  El llamador es responsable de leer/terminar el proceso.
        """
        args = [str(arg) for arg in argv]
        command = self._wrap(args)
        try:
            return subprocess.Popen(
                command,
                stdout=stdout,
                stderr=stderr,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise CommandNotAvailable(f"No se encontró el comando {args[0]!r}.") from exc
        except OSError as exc:
            raise HostError(f"No se pudo ejecutar {args[0]!r}: {exc}") from exc

    @staticmethod
    def _format_error(result: CommandResult) -> str:
        detail = (result.stderr or result.stdout).strip()
        message = f"El comando {result.argv[0]!r} falló (código {result.returncode})."
        if detail:
            message = f"{message}\n{detail}"
        return message

    def which(self, program: str) -> str | None:
        """Devuelve la ruta de un ejecutable, mirando también el host."""
        if self.in_flatpak:
            result = self.run(
                ["sh", "-c", 'command -v "$1"', "sh", program],
                timeout=15,
            )
            if result.ok and result.stdout.strip():
                return result.stdout.strip()
            return None
        return shutil.which(program)

    def read_text(self, path: str | Path, *, timeout: float = 30) -> str:
        """Lee un archivo de texto del host."""
        if self.in_flatpak:
            result = self.run(["cat", str(path)], timeout=timeout)
            if not result.ok:
                raise HostError(
                    f"No se pudo leer {path!s} en el host.\n"
                    f"{(result.stderr or result.stdout).strip()}"
                )
            return result.stdout
        try:
            return Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise HostError(f"No se pudo leer {path!s}: {exc}") from exc

    def list_dir(self, path: str | Path) -> list[str]:
        """Lista un directorio del host sin lanzar excepción si no existe."""
        if self.in_flatpak:
            result = self.run(["ls", "-1", "--", str(path)], timeout=20)
            if not result.ok:
                return []
            return [line for line in result.stdout.splitlines() if line]
        directory = Path(path)
        if not directory.is_dir():
            return []
        try:
            return sorted(entry.name for entry in directory.iterdir())
        except OSError:
            return []

    def stage_files(self, files: Mapping[str, str]) -> Path:
        """Crea un directorio temporal con archivos para instalar.

        En un Flatpak el directorio se crea en el ``/tmp`` del host, porque los
        archivos se pasan a ``pkexec`` que también corre en el host.
        """
        if not files:
            raise ValueError("No hay archivos para preparar.")
        for name in files:
            _safe_filename(name)

        if self.in_flatpak:
            result = self.run(
                ["mktemp", "-d", "-t", "udev-rule-generator.XXXXXXXX"],
                timeout=20,
                check=True,
            )
            directory = Path(result.stdout.strip())
            for name, content in files.items():
                self.run(
                    ["tee", str(directory / name)],
                    input=content,
                    timeout=30,
                    check=True,
                )
            return directory

        directory = Path(tempfile.mkdtemp(prefix="udev-rule-generator."))
        for name, content in files.items():
            path = directory / name
            path.write_text(content, encoding="utf-8")
            path.chmod(0o644)
        return directory

    def cleanup_stage(self, directory: Path) -> None:
        """Elimina el directorio temporal creado por :meth:`stage_files`."""
        if self.in_flatpak:
            self.run(["rm", "-rf", "--", str(directory)], timeout=20, check=False)
            return
        shutil.rmtree(directory, ignore_errors=True)
