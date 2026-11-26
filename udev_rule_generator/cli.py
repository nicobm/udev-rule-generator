"""Interfaz de terminal del generador de reglas udev."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Callable, Iterable, Sequence

from . import ISSUE_URL, PROJECT_URL, __version__, version_string
from .devices import Joystick, detect_joysticks, find_joystick
from .host import CommandNotAvailable, Host, HostError
from .i18n import tr
from .installed import list_installed_rules
from .known import KnownDevice, KnownDevices
from .presets import (
    STEAM,
    Preset,
    preset_files,
    presets_trigger,
    select_presets,
)
from .privileged import InstallResult, install_rule_files, remove_rule_files
from .rules import RuleAction, RuleSpec, build_rule, validate_rule_filename


class Colors:
    """Colores ANSI opcionales."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def blue(self, text: str) -> str:
        return self._wrap("34", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)


def _colors() -> Colors:
    return Colors(sys.stdout.isatty() and "NO_COLOR" not in os.environ)


def _ask(prompt: str, default: str = "") -> str:
    try:
        answer = input(prompt)
    except EOFError as exc:
        raise KeyboardInterrupt from exc
    return answer.strip() or default


def _confirm(prompt: str, *, default: bool = False) -> bool:
    suffix = " [S/n] " if default else " [s/N] "
    answer = _ask(prompt + suffix).casefold()
    if not answer:
        return default
    return answer in {"s", "si", "sí", "y", "yes"}


def _print_banner(colors: Colors) -> None:
    print()
    print(colors.bold(version_string()))
    print(colors.dim(tr("Reglas udev para permitir o ignorar joysticks y gamepads")))
    print(colors.dim(PROJECT_URL))
    print()


def _print_devices(devices: Iterable[Joystick], colors: Colors) -> None:
    items = list(devices)
    if not items:
        print(colors.yellow(tr("No se detectaron joysticks conectados.")))
        print(
            colors.dim(
                tr(
                    "Conectá un mando por USB o Bluetooth y volvé a intentarlo. "
                    "Si ya está conectado, revisá que udev lo vea con: "
                    "udevadm info --export-db"
                )
            )
        )
        return
    for index, device in enumerate(items, start=1):
        print(f"  {colors.bold(str(index).rjust(2))}) {colors.bold(device.display_name)}")
        serial = f" · serial {device.serial}" if device.serial else ""
        print(f"      {colors.cyan(device.bus_label)} · {device.identifier}{serial}")
        print(f"      {colors.dim(device.nodes_label)}")
        if device.input_names and device.input_names[0] != device.display_name:
            print(
                f"      {colors.dim(tr('nombre de entrada: ') + device.input_names[0])}"
            )


def _print_rule_preview(spec: RuleSpec, colors: Colors) -> None:
    print()
    print(
        colors.bold(
            tr(
                "Vista previa: /etc/udev/rules.d/{filename}",
                filename=spec.filename,
            )
        )
    )
    print(colors.dim("─" * 72))
    for line in spec.content.rstrip().splitlines():
        if line.startswith("#"):
            print(colors.dim(line))
        else:
            print(line)
    print(colors.dim("─" * 72))


def _print_install_result(result: InstallResult, colors: Colors) -> None:
    for filename in result.filenames:
        print(
            colors.green(
                tr(
                    "✓ Instalada: {path}/{filename}",
                    path=result.target_dir,
                    filename=filename,
                )
            )
        )
    if result.used_pkexec:
        print(colors.dim(tr("  Instalada con autenticación de polkit.")))
    if result.reloaded:
        print(colors.dim(tr("  Reglas recargadas con udevadm.")))
    elif result.warning:
        print(colors.yellow(f"  {result.warning}"))


def _resolve_action(value: str | None, device: Joystick) -> RuleAction:
    if value:
        return RuleAction(value)
    return RuleAction.ALLOW


def _save_known_device(
    device: Joystick, spec: RuleSpec, colors: Colors
) -> None:
    try:
        KnownDevices().record_rule(device, spec)
    except OSError as exc:
        print(
            colors.yellow(
                tr(
                    "La regla se instaló, pero no se pudo guardar en "
                    "Dispositivos guardados: {error}",
                    error=exc,
                )
            ),
            file=sys.stderr,
        )


def _mark_known_inactive(
    store: KnownDevices, filename: str, colors: Colors
) -> None:
    try:
        store.mark_inactive_by_filename(filename)
    except OSError as exc:
        print(
            colors.yellow(
                tr(
                    "La regla se eliminó, pero no se pudo actualizar "
                    "Dispositivos guardados: {error}",
                    error=exc,
                )
            ),
            file=sys.stderr,
        )


def _confirm_and_install(
    host: Host,
    files: dict[str, str],
    *,
    trigger: str,
    colors: Colors,
    assume_yes: bool,
    dry_run: bool,
    on_installed: Callable[[InstallResult], None] | None = None,
) -> int:
    if dry_run:
        for filename, content in files.items():
            print()
            print(colors.bold(f"--- {filename} ---"))
            print(content.rstrip())
        print()
        print(colors.dim(tr("Modo --dry-run: no se escribió nada.")))
        return 0

    if not assume_yes:
        if not sys.stdin.isatty():
            print()
            print(
                colors.yellow(
                    tr(
                        "Se generó la regla, pero no se instaló porque la entrada no es "
                        "interactiva. Usá --yes para instalarla."
                    )
                )
            )
            for filename, content in files.items():
                print()
                print(colors.bold(f"--- {filename} ---"))
                print(content.rstrip())
            return 0
        if not _confirm(
            tr("¿Instalar en /etc/udev/rules.d con permisos de administrador?")
        ):
            print(colors.dim(tr("No se instaló nada.")))
            return 0

    print(
        colors.dim(
            tr("Se abrirá el diálogo de autenticación de polkit/GNOME...")
        )
    )
    result = install_rule_files(host, files, trigger=trigger)
    _print_install_result(result, colors)
    if on_installed is not None:
        on_installed(result)
    return 0


def _cmd_list(host: Host, *, as_json: bool, colors: Colors) -> int:
    devices = detect_joysticks(host)
    if as_json:
        print(
            json.dumps(
                [device.to_dict() for device in devices],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    _print_devices(devices, colors)
    return 0


def _cmd_installed(
    host: Host,
    *,
    as_json: bool,
    remove: Sequence[str],
    assume_yes: bool,
    colors: Colors,
) -> int:
    rules = list_installed_rules(host)
    if remove:
        available = {rule.filename for rule in rules}
        missing = [filename for filename in remove if filename not in available]
        if missing:
            raise ValueError(
                tr(
                    "No se encontraron reglas administradas por esta aplicación: "
                    "{names}",
                    names=", ".join(missing),
                )
            )
        for filename in remove:
            validate_rule_filename(filename)
        if not assume_yes:
            if not sys.stdin.isatty():
                raise ValueError(
                    tr("Para eliminar reglas sin interacción usá --yes.")
                )
            if not _confirm(
                tr("¿Eliminar {names}?", names=", ".join(remove))
            ):
                print(colors.dim(tr("No se eliminó nada.")))
                return 0
        print(
            colors.dim(
                tr("Se abrirá el diálogo de autenticación de polkit/GNOME...")
            )
        )
        result = remove_rule_files(host, list(remove))
        known_store = KnownDevices()
        for filename in result.filenames:
            _mark_known_inactive(known_store, filename, colors)
            print(
                colors.green(
                    tr(
                        "✓ Eliminada: {path}/{filename}",
                        path=result.target_dir,
                        filename=filename,
                    )
                )
            )
        if result.reloaded:
            print(colors.dim(tr("  Reglas recargadas con udevadm.")))
        return 0

    if as_json:
        print(json.dumps([rule.to_dict() for rule in rules], ensure_ascii=False, indent=2))
        return 0
    if not rules:
        print(
            colors.dim(
                tr("No hay reglas administradas por esta aplicación.")
            )
        )
        return 0
    for rule in rules:
        kind = tr("generada") if rule.kind == "generated" else tr("preconfigurada")
        print(f"  {colors.bold(rule.filename)}")
        print(f"      {rule.title} · {colors.dim(kind)}")
        if rule.source:
            print(f"      {colors.dim(rule.source)}")
    return 0


def _find_known_device(
    store: KnownDevices, selector: str
) -> KnownDevice | None:
    selector = selector.strip()
    if not selector:
        return None
    if selector.isdigit():
        index = int(selector) - 1
        devices = store.devices()
        if 0 <= index < len(devices):
            return devices[index]
        return None
    exact = [
        device
        for device in store.devices()
        if selector in {device.id, device.filename}
    ]
    if exact:
        return exact[0]
    lowered = selector.casefold()
    matches = [
        device
        for device in store.devices()
        if lowered in device.name.casefold()
        or lowered in device.id.casefold()
        or lowered in device.filename.casefold()
        or lowered in device.identifier.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _cmd_known(
    host: Host,
    *,
    as_json: bool,
    enable: str | None,
    disable: str | None,
    assume_yes: bool,
    dry_run: bool,
    colors: Colors,
) -> int:
    store = KnownDevices()
    try:
        store.reconcile(list_installed_rules(host))
    except (HostError, OSError):
        # La lista de reglas es auxiliar; el registro todavía se puede usar.
        pass
    selector = enable or disable
    if selector:
        device = _find_known_device(store, selector)
        if device is None:
            raise ValueError(
                tr(
                    "No se encontró un único dispositivo guardado que coincida "
                    "con {selector!r}.  Usá --known para ver la lista.",
                    selector=selector,
                )
            )
        active = enable is not None
        if device.active == active:
            state = tr("activa") if active else tr("desactivada")
            print(
                colors.dim(
                    tr(
                        "La regla de {name} ya está {state}.",
                        name=device.name,
                        state=state,
                    )
                )
            )
            return 0
        if dry_run:
            if active:
                spec = device.build_spec()
                _print_rule_preview(spec, colors)
            else:
                print(
                    colors.bold(
                        tr(
                            "Se eliminaría /etc/udev/rules.d/{filename}",
                            filename=device.filename,
                        )
                    )
                )
            print(colors.dim(tr("Modo --dry-run: no se escribió nada.")))
            return 0
        if not assume_yes:
            if not sys.stdin.isatty():
                raise ValueError(
                    tr(
                        "Para activar o desactivar sin interacción usá --yes."
                    )
                )
            question = (
                tr("¿Activar la regla guardada de {name}?", name=device.name)
                if active
                else tr(
                    "¿Desactivar la regla guardada de {name}?", name=device.name
                )
            )
            if not _confirm(question):
                print(colors.dim(tr("No se modificó nada.")))
                return 0
        if active:
            spec = device.build_spec()
            result = install_rule_files(
                host,
                {spec.filename: spec.content},
                trigger=spec.trigger,
            )
            try:
                store.update(device.update_from_spec(spec))
            except OSError as exc:
                print(
                    colors.yellow(
                        tr(
                            "La regla se instaló, pero no se pudo guardar en "
                            "Dispositivos guardados: {error}",
                            error=exc,
                        )
                    ),
                    file=sys.stderr,
                )
            _print_install_result(result, colors)
        else:
            result = remove_rule_files(host, [device.filename])
            _mark_known_inactive(store, device.filename, colors)
            for filename in result.filenames:
                print(
                    colors.green(
                        tr(
                            "✓ Eliminada: {path}/{filename}",
                            path=result.target_dir,
                            filename=filename,
                        )
                    )
                )
            if result.reloaded:
                print(colors.dim(tr("  Reglas recargadas con udevadm.")))
        return 0

    devices = store.devices()
    if as_json:
        print(
            json.dumps(
                [device.to_dict() for device in devices],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not devices:
        print(
            colors.dim(
                tr(
                    "No hay dispositivos guardados.  Instalá una regla para "
                    "un mando y va a aparecer acá."
                )
            )
        )
        return 0
    for index, device in enumerate(devices, start=1):
        state = tr("Activa") if device.active else tr("Desactivada")
        print(f"  {colors.bold(str(index).rjust(2))}) {colors.bold(device.name)}")
        print(
            f"      {colors.cyan(device.bus_label)} · {device.identifier} · "
            f"{device.action_label} · {state}"
        )
        print(f"      {colors.dim(device.filename)}")
        print(f"      {colors.dim(device.id)}")
    return 0


def _install_presets(
    host: Host,
    presets: Sequence[Preset],
    *,
    assume_yes: bool,
    dry_run: bool,
    colors: Colors,
) -> int:
    if not presets:
        print(colors.yellow(tr("No se seleccionó ninguna regla.")))
        return 0
    files = preset_files(presets)
    print()
    print(colors.bold(tr("Se instalarán:")))
    for preset in presets:
        print(f"  · {preset.install_name}  ({preset.title})")
    return _confirm_and_install(
        host,
        files,
        trigger=presets_trigger(presets),
        colors=colors,
        assume_yes=assume_yes,
        dry_run=dry_run,
    )


def _cmd_presets(
    host: Host,
    selection: str,
    *,
    assume_yes: bool,
    dry_run: bool,
    colors: Colors,
) -> int:
    if selection in {"menu", "interactive"}:
        selection = "steam"
    presets = select_presets(selection)
    return _install_presets(
        host,
        presets,
        assume_yes=assume_yes,
        dry_run=dry_run,
        colors=colors,
    )


def _cmd_device(
    host: Host,
    selector: str,
    action_value: str | None,
    *,
    assume_yes: bool,
    dry_run: bool,
    colors: Colors,
) -> int:
    devices = detect_joysticks(host)
    device = find_joystick(devices, selector)
    if device is None:
        if not devices:
            raise ValueError(tr("No se detectaron joysticks conectados."))
        raise ValueError(
            tr(
                "No se encontró un único joystick que coincida con {selector!r}. "
                "Usá --list para ver los disponibles.",
                selector=selector,
            )
        )
    action = _resolve_action(action_value, device)
    spec = build_rule(device, action)
    print(colors.bold(device.display_name))
    print(colors.dim(device.hardware_label))
    _print_rule_preview(spec, colors)
    if action is RuleAction.IGNORE and device.is_bluetooth:
        print(
            colors.yellow(
                tr(
                    "Aviso: en Bluetooth el ignorar es best effort; se deniega el "
                    "acceso a los nodos de entrada, pero el dispositivo puede seguir "
                    "existiendo para root."
                )
            )
        )
    if dry_run:
        print(colors.dim(tr("Modo --dry-run: no se escribió nada.")))
        return 0
    return _confirm_and_install(
        host,
        {spec.filename: spec.content},
        trigger=spec.trigger,
        colors=colors,
        assume_yes=assume_yes,
        dry_run=False,
        on_installed=lambda _result: _save_known_device(device, spec, colors),
    )


def _interactive_device(host: Host, args: argparse.Namespace, colors: Colors) -> None:
    while True:
        devices = detect_joysticks(host)
        print()
        print(colors.bold(tr("Joysticks detectados")))
        _print_devices(devices, colors)
        if not devices:
            print(
                colors.dim(
                    tr(
                        "\nVolvé al menú y actualizá después de conectar el mando."
                    )
                )
            )
            return
        print()
        print(
            colors.dim(
                tr("  r) Actualizar   p) Instalar Steam   q) Volver")
            )
        )
        selection = _ask(tr("\nElegí un número: ")).casefold()
        if selection in {"q", "volver", ""}:
            return
        if selection == "r":
            continue
        if selection == "p":
            _interactive_presets(host, args, colors)
            continue
        device = find_joystick(devices, selection)
        if device is None:
            print(colors.red(tr("Selección no válida.")))
            continue

        print()
        print(colors.bold(device.display_name))
        print(colors.dim(device.hardware_label))
        if device.input_names:
            print(
                colors.dim(
                    tr(
                        "Nombres de entrada: {names}",
                        names=", ".join(device.input_names),
                    )
                )
            )
        print()
        print(colors.bold(tr("¿Qué querés hacer con este dispositivo?")))
        print(
            f"  1) {colors.green(tr('Habilitar (predeterminado)'))}  "
            f"({RuleAction.ALLOW.description})"
        )
        print(
            f"  2) {colors.yellow(tr('Ignorar'))}            "
            f"({RuleAction.IGNORE.description})"
        )
        print(tr("  3) Volver"))
        choice = _ask(tr("\nAcción: "))
        if choice in {"3", "q", ""}:
            return
        if choice not in {"1", "2"}:
            print(colors.red(tr("Acción no válida.")))
            continue
        action = RuleAction.ALLOW if choice == "1" else RuleAction.IGNORE
        try:
            spec = build_rule(device, action)
        except ValueError as exc:
            print(
                colors.red(
                    tr("No se pudo generar la regla: {error}", error=exc)
                )
            )
            return
        _print_rule_preview(spec, colors)
        if action is RuleAction.IGNORE and device.is_bluetooth:
            print(
                colors.yellow(
                    tr(
                        "Aviso: en Bluetooth no se puede desautorizar el USB. La regla "
                        "deniega el acceso a los nodos de entrada; es un ignorar "
                        "'best effort'."
                    )
                )
            )
        if _confirm(
            tr("¿Instalar en /etc/udev/rules.d con permisos de administrador?"),
            default=False,
        ):
            print(
                colors.dim(
                    tr("Se abrirá el diálogo de autenticación de polkit/GNOME...")
                )
            )
            try:
                result = install_rule_files(
                    host, {spec.filename: spec.content}, trigger=spec.trigger
                )
            except (HostError, CommandNotAvailable) as exc:
                print(colors.red(tr("Error: {error}", error=exc)))
                return
            _print_install_result(result, colors)
            _save_known_device(device, spec, colors)
        else:
            print(colors.dim(tr("No se instaló nada.")))
        return


def _interactive_presets(host: Host, args: argparse.Namespace, colors: Colors) -> None:
    _cmd_presets(
        host,
        "menu",
        assume_yes=args.yes,
        dry_run=args.dry_run,
        colors=colors,
    )


def _interactive_installed(host: Host, colors: Colors) -> None:
    rules = list_installed_rules(host)
    print()
    print(colors.bold(tr("Reglas instaladas por esta aplicación")))
    if not rules:
        print(colors.dim(tr("No hay reglas administradas.")))
        return
    for index, rule in enumerate(rules, start=1):
        kind = tr("generada") if rule.kind == "generated" else tr("preconfigurada")
        print(f"  {colors.bold(str(index).rjust(2))}) {rule.filename}")
        print(f"      {rule.title} · {colors.dim(kind)}")
        if rule.source:
            print(f"      {colors.dim(rule.source)}")
    print()
    if not _confirm(tr("¿Eliminar alguna regla?"), default=False):
        return
    raw = _ask(tr("Números separados por coma: "))
    indexes = {
        int(part.strip()) for part in raw.split(",") if part.strip().isdigit()
    }
    selected = [
        rule for index, rule in enumerate(rules, start=1) if index in indexes
    ]
    if not selected:
        print(colors.dim(tr("No se seleccionó ninguna regla.")))
        return
    if not _confirm(
        tr(
            "¿Eliminar {names}?",
            names=", ".join(rule.filename for rule in selected),
        )
    ):
        print(colors.dim(tr("No se eliminó nada.")))
        return
    try:
        result = remove_rule_files(host, [rule.filename for rule in selected])
    except (HostError, CommandNotAvailable) as exc:
        print(colors.red(tr("Error: {error}", error=exc)))
        return
    known_store = KnownDevices()
    for filename in result.filenames:
        _mark_known_inactive(known_store, filename, colors)
        print(
            colors.green(
                tr(
                    "✓ Eliminada: {path}/{filename}",
                    path=result.target_dir,
                    filename=filename,
                )
            )
        )


def _interactive(host: Host, args: argparse.Namespace) -> int:
    colors = _colors()
    _print_banner(colors)
    while True:
        print(colors.bold(tr("Menú principal")))
        print(tr("  1) Listar y configurar un joystick"))
        print(tr("  2) Instalar reglas de Steam"))
        print(tr("  3) Ver o eliminar reglas instaladas"))
        print(tr("  4) Salir"))
        choice = _ask(tr("\nOpción: ")).casefold()
        if choice in {"4", "q", "salir", "exit"}:
            print(colors.dim(tr("Hasta luego.")))
            return 0
        if choice in {"1", "j", "joystick"}:
            _interactive_device(host, args, colors)
        elif choice in {"2", "p", "presets"}:
            _interactive_presets(host, args, colors)
        elif choice in {"3", "r", "reglas"}:
            _interactive_installed(host, colors)
        else:
            print(colors.red(tr("Opción no válida.")))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="udev-rule-generator",
        description=tr(
            "Crea reglas udev para permitir o ignorar joysticks.  Sin argumentos "
            "abre el menú interactivo; con --gui abre la interfaz gráfica."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=tr(
            "Ejemplos:\n"
            "  udev-rule-generator --gui\n"
            "  udev-rule-generator --list\n"
            "  udev-rule-generator --device 1 --action allow\n"
            "  udev-rule-generator --device 045e:02fd --action ignore --dry-run\n"
            "  udev-rule-generator --presets steam\n"
            "  udev-rule-generator --installed\n"
            "  udev-rule-generator --known\n"
            "  udev-rule-generator --disable-known 045e:02fd --yes\n\n"
            "Proyecto: {project}\n"
            "Problemas: {issues}",
            project=PROJECT_URL,
            issues=ISSUE_URL,
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help=tr("abre la interfaz gráfica GTK4/libadwaita"),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help=tr("lista los joysticks detectados y sale"),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=tr("salida JSON para --list, --installed o --known"),
    )
    parser.add_argument(
        "--device",
        metavar="ID",
        help=tr("índice, VID:PID o parte del nombre del joystick"),
    )
    parser.add_argument(
        "--action",
        choices=[action.value for action in RuleAction],
        help=tr("acción a aplicar con --device"),
    )
    parser.add_argument(
        "--presets",
        nargs="?",
        const="steam",
        metavar=tr("SELECCIÓN"),
        help=tr("instala steam-devices (Valve)"),
    )
    parser.add_argument(
        "--installed",
        action="store_true",
        help=tr("lista las reglas instaladas por esta aplicación"),
    )
    parser.add_argument(
        "--known",
        action="store_true",
        help=tr("lista los dispositivos guardados"),
    )
    parser.add_argument(
        "--enable-known",
        metavar="ID",
        help=tr("activa la regla guardada de un dispositivo"),
    )
    parser.add_argument(
        "--disable-known",
        metavar="ID",
        help=tr("desactiva la regla guardada de un dispositivo"),
    )
    parser.add_argument(
        "--remove",
        action="append",
        default=[],
        metavar=tr("ARCHIVO.rules"),
        help=tr("elimina una regla administrada (se puede repetir)"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=tr("muestra las reglas sin instalarlas"),
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help=tr("no pide confirmación antes de llamar a pkexec"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    colors = _colors()
    host = Host()

    try:
        if args.gui:
            conflicting = any(
                (
                    args.list,
                    args.device,
                    args.action,
                    args.presets is not None,
                    args.installed,
                    args.known,
                    args.enable_known,
                    args.disable_known,
                    args.remove,
                    args.json,
                    args.dry_run,
                    args.yes,
                )
            )
            if conflicting:
                parser.error(
                    tr("--gui no se puede combinar con otras opciones.")
                )
            try:
                from gui.main import main as gui_main
            except ImportError as exc:
                print(
                    tr("error: no se pudo cargar la GUI: {error}", error=exc),
                    file=sys.stderr,
                )
                return 1
            return gui_main([sys.argv[0]])

        if args.list:
            return _cmd_list(host, as_json=args.json, colors=colors)
        if args.enable_known and args.disable_known:
            parser.error(
                tr("--enable-known y --disable-known no se pueden combinar.")
            )
        if args.known or args.enable_known or args.disable_known:
            return _cmd_known(
                host,
                as_json=args.json,
                enable=args.enable_known,
                disable=args.disable_known,
                assume_yes=args.yes,
                dry_run=args.dry_run,
                colors=colors,
            )
        if args.installed or args.remove:
            return _cmd_installed(
                host,
                as_json=args.json,
                remove=args.remove,
                assume_yes=args.yes,
                colors=colors,
            )
        if args.presets is not None:
            return _cmd_presets(
                host,
                args.presets,
                assume_yes=args.yes,
                dry_run=args.dry_run,
                colors=colors,
            )
        if args.device:
            return _cmd_device(
                host,
                args.device,
                args.action,
                assume_yes=args.yes,
                dry_run=args.dry_run,
                colors=colors,
            )
        if args.action:
            parser.error(tr("--action requiere --device."))
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            parser.print_help()
            return 2
        return _interactive(host, args)
    except KeyboardInterrupt:
        print(tr("\nCancelado."), file=sys.stderr)
        return 130
    except (HostError, CommandNotAvailable, ValueError, KeyError) as exc:
        print(tr("error: {error}", error=exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
