"""Monitor de eventos udev para detectar mandos al conectarlos.

Se usa ``udevadm monitor --udev --property --subsystem-match=input`` en un
proceso de larga duración.  La GUI sigue teniendo un sondeo periódico como
respaldo por si el monitor no está disponible o el host lo corta.
"""

from __future__ import annotations

import threading
from typing import Callable, Iterable, Iterator

from .host import Host, HostError


def parse_monitor_stream(lines: Iterable[str]) -> Iterator[dict[str, str]]:
    """Convierte la salida de ``udevadm monitor --property`` en eventos.

    Cada evento es un diccionario con propiedades como ``ACTION``,
    ``SUBSYSTEM`` y ``DEVPATH``.  Se emite al encontrar una línea vacía o el
    encabezado del evento siguiente.
    """
    event: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line:
            if event:
                yield event
                event = {}
            continue
        if line.startswith(("UDEV  [", "KERNEL[", "UDEV [")):
            if event:
                yield event
                event = {}
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            event[key] = value
    if event:
        yield event


class UdevMonitor:
    """Proceso udevadm monitor con callbacks en un hilo aparte."""

    def __init__(
        self,
        host: Host,
        on_event: Callable[[dict[str, str]], None],
        on_failure: Callable[[], None] | None = None,
    ) -> None:
        self.host = host
        self.on_event = on_event
        self.on_failure = on_failure
        self._process = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        """Arranca el monitor.  Devuelve ``False`` si no se puede."""
        if self.running:
            return True
        try:
            if self.host.which("udevadm") is None:
                return False
        except HostError:
            return False

        args = [
            "udevadm",
            "monitor",
            "--udev",
            "--property",
            "--subsystem-match=input",
        ]
        try:
            stdbuf = self.host.which("stdbuf")
        except HostError:
            stdbuf = None
        if stdbuf:
            # Sin line-buffering, un proceso con stdout conectado a un pipe
            # puede tardar en entregar los eventos.
            args = [stdbuf, "-oL", "-eL", *args]

        try:
            self._process = self.host.popen(args)
        except (HostError, OSError):
            return False

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._reader,
            name="udev-rule-generator-monitor",
            daemon=True,
        )
        self._thread.start()
        return True

    def _reader(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            for event in parse_monitor_stream(process.stdout):
                if self._stop.is_set():
                    break
                if event.get("ACTION") in {"add", "remove"}:
                    try:
                        self.on_event(event)
                    except Exception:
                        # Un callback de la GUI nunca debe matar el hilo.
                        pass
        except (OSError, ValueError):
            pass
        finally:
            if not self._stop.is_set() and self.on_failure is not None:
                try:
                    self.on_failure()
                except Exception:
                    pass

    def stop(self) -> None:
        """Termina el proceso y el hilo del monitor."""
        self._stop.set()
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
