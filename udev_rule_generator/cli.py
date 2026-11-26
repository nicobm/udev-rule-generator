"""Interfaz de terminal del generador de reglas udev."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Iterable, Sequence

from . import APP_NAME, ISSUE_URL, PROJECT_URL, __version__, version_string
from .devices import Joystick, detect_joysticks, find_joystick
from .host import CommandNotAvailable, Host, HostError
from .installed import list_installed_rules
from .presets import (
    RECOMMENDED,
    UPSTREAM,
    Preset,
    get_preset,
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
    print(colors.dim("Reglas udev para permitir o ignorar joysticks y gamepads"))
    print(colors.dim(PROJECT_URL))
    print()


def _print_devices(devices: Iterable[Joystick], colors: Colors) -> None:
    items = list(devices)
    if not items:
        print(colors.yellow("No se detectaron joysticks conectados."))
        print(
            colors.dim(
                "Conectá un mando por USB o Bluetooth y volvé a intentarlo. "
                "Si ya está conectado, revisá que udev lo vea con: udevadm info --export-db"
            )
        )
        return
    for index, device in enumerate(items, start=1):
        print(f"  {colors.bold(str(index).rjust(2))}) {colors.bold(device.display_name)}")
        print(
            f"      {colors.cyan(device.bus_label)} · {device.identifier}"
            + (f" · serial {device.serial}" if device.serial else "")
        )
        print(f"      {colors.dim(device.nodes_label)}")
        if device.input_names and device.input_names[0] != device.display_name:
            print(f"      {colors.dim('nombre de entrada: ' + device.input_names[0])}")


def _print_rule_preview(spec: RuleSpec, colors: Colors) -> None:
    print()
    print(colors.bold(f"Vista previa: /etc/udev/rules.d/{spec.filename}"))
    print(colors.dim("─" * 72))
    for line in spec.content.rstrip().splitlines():
        if line.startswith("#"):
            print(colors.dim(line))
        else:
            print(line)
    print(colors.dim("─" * 72))


def _print_install_result(result: InstallResult, colors: Colors) -> None:
    for filename in result.filenames:
        print(colors.green(f"✓ Instalada: {result.target_dir}/{filename}"))
    if result.used_pkexec:
        print(colors.dim("  Instalada con autenticación de polkit."))
    if result.reloaded:
        print(colors.dim("  Reglas recargadas con udevadm."))
    elif result.warning:
        print(colors.yellow(f"  {result.warning}"))


def _resolve_action(value: str | None, device: Joystick) -> RuleAction:
    if value:
        return RuleAction(value)
    return RuleAction.ALLOW


def _confirm_and_install(
    host: Host,
    files: dict[str, str],
    *,
    trigger: str,
    colors: Colors,
    assume_yes: bool,
    dry_run: bool,
) -> int:
    if dry_run:
        for filename, content in files.items():
            print()
            print(colors.bold(f"--- {filename} ---"))
            print(content.rstrip())
        print()
        print(colors.dim("Modo --dry-run: no se escribió nada."))
        return 0

    if not assume_yes:
        if not sys.stdin.isatty():
            print()
            print(
                colors.yellow(
                    "Se generó la regla, pero no se instaló porque la entrada no es "
                    "interactiva. Usá --yes para instalarla."
                )
            )
            for filename, content in files.items():
                print()
                print(colors.bold(f"--- {filename} ---"))
                print(content.rstrip())
            return 0
        if not _confirm("¿Instalar en /etc/udev/rules.d con permisos de administrador?"):
            print(colors.dim("No se instaló nada."))
            return 0

    print(colors.dim("Se abrirá el diálogo de autenticación de polkit/GNOME..."))
    result = install_rule_files(host, files, trigger=trigger)
    _print_install_result(result, colors)
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
                "No se encontraron reglas administradas por esta aplicación: "
                + ", ".join(missing)
            )
        for filename in remove:
            validate_rule_filename(filename)
        if not assume_yes:
            if not sys.stdin.isatty():
                raise ValueError("Para eliminar reglas sin interacción usá --yes.")
            if not _confirm("¿Eliminar " + ", ".join(remove) + "?"):
                print(colors.dim("No se eliminó nada."))
                return 0
        print(colors.dim("Se abrirá el diálogo de autenticación de polkit/GNOME..."))
        result = remove_rule_files(host, list(remove))
        for filename in result.filenames:
            print(colors.green(f"✓ Eliminada: {result.target_dir}/{filename}"))
        if result.reloaded:
            print(colors.dim("  Reglas recargadas con udevadm."))
        return 0

    if as_json:
        print(json.dumps([rule.to_dict() for rule in rules], ensure_ascii=False, indent=2))
        return 0
    if not rules:
        print(colors.dim("No hay reglas administradas por esta aplicación."))
        return 0
    for rule in rules:
        kind = "generada" if rule.kind == "generated" else "preconfigurada"
        print(f"  {colors.bold(rule.filename)}")
        print(f"      {rule.title} · {colors.dim(kind)}")
        if rule.source:
            print(f"      {colors.dim(rule.source)}")
    return 0


def _print_presets(presets: Iterable[Preset], colors: Colors) -> None:
    for index, preset in enumerate(presets, start=1):
        print(f"  {colors.bold(str(index).rjust(2))}) {colors.bold(preset.title)}")
        print(f"      {preset.description}")
        print(
            "      "
            + colors.dim(
                f"instala /etc/udev/rules.d/{preset.install_name} · {preset.license}"
            )
        )


def _install_presets(
    host: Host,
    presets: Sequence[Preset],
    *,
    assume_yes: bool,
    dry_run: bool,
    colors: Colors,
) -> int:
    if not presets:
        print(colors.yellow("No se seleccionó ninguna regla."))
        return 0
    files = preset_files(presets)
    print()
    print(colors.bold("Se instalarán:"))
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
        if not sys.stdin.isatty():
            raise ValueError(
                "Elegí una selección: recommended, all o el id de una regla."
            )
        print()
        print(colors.bold("Reglas preconfiguradas"))
        print("  1) Recomendadas: ASRock LED (ignorar) + Microsoft Xbox")
        print("  2) Microsoft Xbox")
        print("  3) ASRock LED")
        print("  4) Todos los fabricantes de game-devices-udev")
        print("  5) Elegir fabricantes de la biblioteca")
        print("  6) Volver")
        choice = _ask("\nSelección: ")
        if choice in {"6", "q", ""}:
            return 0
        if choice == "1":
            presets = list(RECOMMENDED)
        elif choice == "2":
            presets = [get_preset("microsoft-xbox")]
        elif choice == "3":
            presets = [get_preset("asrock-led-disable")]
        elif choice == "4":
            presets = list(UPSTREAM)
        elif choice == "5":
            _print_presets(UPSTREAM, colors)
            raw = _ask(
                "\nNúmeros separados por coma (por ejemplo 1,3,7): "
            )
            try:
                indexes = {
                    int(part.strip())
                    for part in raw.split(",")
                    if part.strip().isdigit()
                }
            except ValueError:
                indexes = set()
            presets = [
                preset
                for index, preset in enumerate(UPSTREAM, start=1)
                if index in indexes
            ]
        else:
            print(colors.red("Selección no válida."))
            return 1
        return _install_presets(
            host,
            presets,
            assume_yes=assume_yes,
            dry_run=dry_run,
            colors=colors,
        )

    try:
        presets = select_presets(selection)
    except KeyError as exc:
        raise ValueError(str(exc)) from exc
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
            raise ValueError("No se detectaron joysticks conectados.")
        raise ValueError(
            f"No se encontró un único joystick que coincida con {selector!r}. "
            "Usá --list para ver los disponibles."
        )
    action = _resolve_action(action_value, device)
    spec = build_rule(device, action)
    print(colors.bold(device.display_name))
    print(colors.dim(device.hardware_label))
    _print_rule_preview(spec, colors)
    if action is RuleAction.IGNORE and device.is_bluetooth:
        print(
            colors.yellow(
                "Aviso: en Bluetooth el ignorar es best effort; se deniega el "
                "acceso a los nodos de entrada, pero el dispositivo puede seguir "
                "existiendo para root."
            )
        )
    if dry_run:
        print(colors.dim("Modo --dry-run: no se escribió nada."))
        return 0
    return _confirm_and_install(
        host,
        {spec.filename: spec.content},
        trigger=spec.trigger,
        colors=colors,
        assume_yes=assume_yes,
        dry_run=False,
    )


def _interactive_device(host: Host, args: argparse.Namespace, colors: Colors) -> None:
    while True:
        devices = detect_joysticks(host)
        print()
        print(colors.bold("Joysticks detectados"))
        _print_devices(devices, colors)
        if not devices:
            print(colors.dim("\nVolvé al menú y actualizá después de conectar el mando."))
            return
        print()
        print(colors.dim("  r) Actualizar   p) Reglas preconfiguradas   q) Volver"))
        selection = _ask("\nElegí un número: ").casefold()
        if selection in {"q", "volver", ""}:
            return
        if selection == "r":
            continue
        if selection == "p":
            _interactive_presets(host, args, colors)
            continue
        device = find_joystick(devices, selection)
        if device is None:
            print(colors.red("Selección no válida."))
            continue

        print()
        print(colors.bold(device.display_name))
        print(colors.dim(device.hardware_label))
        if device.input_names:
            print(colors.dim("Nombres de entrada: " + ", ".join(device.input_names)))
        print()
        print(colors.bold("¿Qué querés hacer con este dispositivo?"))
        print(f"  1) {colors.green('Permitir / detectar')}  ({RuleAction.ALLOW.description})")
        print(f"  2) {colors.yellow('Ignorar')}            ({RuleAction.IGNORE.description})")
        print("  3) Volver")
        choice = _ask("\nAcción: ")
        if choice in {"3", "q", ""}:
            return
        if choice not in {"1", "2"}:
            print(colors.red("Acción no válida."))
            continue
        action = RuleAction.ALLOW if choice == "1" else RuleAction.IGNORE
        try:
            spec = build_rule(device, action)
        except ValueError as exc:
            print(colors.red(f"No se pudo generar la regla: {exc}"))
            return
        _print_rule_preview(spec, colors)
        if action is RuleAction.IGNORE and device.is_bluetooth:
            print(
                colors.yellow(
                    "Aviso: en Bluetooth no se puede desautorizar el USB. La regla "
                    "deniega el acceso a los nodos de entrada; es un ignorar "
                    "'best effort'."
                )
            )
        if _confirm(
            "¿Instalar en /etc/udev/rules.d con permisos de administrador?",
            default=False,
        ):
            print(colors.dim("Se abrirá el diálogo de autenticación de polkit/GNOME..."))
            try:
                result = install_rule_files(
                    host, {spec.filename: spec.content}, trigger=spec.trigger
                )
            except (HostError, CommandNotAvailable) as exc:
                print(colors.red(f"Error: {exc}"))
                return
            _print_install_result(result, colors)
        else:
            print(colors.dim("No se instaló nada."))
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
    print(colors.bold("Reglas instaladas por esta aplicación"))
    if not rules:
        print(colors.dim("No hay reglas administradas."))
        return
    for index, rule in enumerate(rules, start=1):
        kind = "generada" if rule.kind == "generated" else "preconfigurada"
        print(f"  {colors.bold(str(index).rjust(2))}) {rule.filename}")
        print(f"      {rule.title} · {colors.dim(kind)}")
        if rule.source:
            print(f"      {colors.dim(rule.source)}")
    print()
    if not _confirm("¿Eliminar alguna regla?", default=False):
        return
    raw = _ask("Números separados por coma: ")
    indexes = {
        int(part.strip()) for part in raw.split(",") if part.strip().isdigit()
    }
    selected = [
        rule for index, rule in enumerate(rules, start=1) if index in indexes
    ]
    if not selected:
        print(colors.dim("No se seleccionó ninguna regla."))
        return
    if not _confirm("¿Eliminar " + ", ".join(rule.filename for rule in selected) + "?"):
        print(colors.dim("No se eliminó nada."))
        return
    try:
        result = remove_rule_files(host, [rule.filename for rule in selected])
    except (HostError, CommandNotAvailable) as exc:
        print(colors.red(f"Error: {exc}"))
        return
    for filename in result.filenames:
        print(colors.green(f"✓ Eliminada: {result.target_dir}/{filename}"))


def _interactive(host: Host, args: argparse.Namespace) -> int:
    colors = _colors()
    _print_banner(colors)
    while True:
        print(colors.bold("Menú principal"))
        print("  1) Listar y configurar un joystick")
        print("  2) Instalar reglas preconfiguradas")
        print("  3) Ver o eliminar reglas instaladas")
        print("  4) Salir")
        choice = _ask("\nOpción: ").casefold()
        if choice in {"4", "q", "salir", "exit"}:
            print(colors.dim("Hasta luego."))
            return 0
        if choice in {"1", "j", "joystick"}:
            _interactive_device(host, args, colors)
        elif choice in {"2", "p", "presets"}:
            _interactive_presets(host, args, colors)
        elif choice in {"3", "r", "reglas"}:
            _interactive_installed(host, colors)
        else:
            print(colors.red("Opción no válida."))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="udev-rule-generator",
        description=(
            "Crea reglas udev para permitir o ignorar joysticks.  Sin argumentos "
            "abre el menú interactivo."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  udev-rule-generator --list\n"
            "  udev-rule-generator --device 1 --action allow\n"
            "  udev-rule-generator --device 045e:0b12 --action ignore --dry-run\n"
            "  udev-rule-generator --presets recommended\n"
            "  udev-rule-generator --presets all --yes\n"
            "  udev-rule-generator --installed\n\n"
            f"Proyecto: {PROJECT_URL}\n"
            f"Problemas: {ISSUE_URL}"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="lista los joysticks detectados y sale",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="salida JSON para --list o --installed",
    )
    parser.add_argument(
        "--device",
        metavar="ID",
        help="índice, VID:PID o parte del nombre del joystick",
    )
    parser.add_argument(
        "--action",
        choices=[action.value for action in RuleAction],
        help="acción a aplicar con --device",
    )
    parser.add_argument(
        "--presets",
        nargs="?",
        const="menu",
        metavar="SELECCIÓN",
        help=(
            "instala reglas preconfiguradas: recommended, all o un id.  Sin "
            "valor abre el menú"
        ),
    )
    parser.add_argument(
        "--installed",
        action="store_true",
        help="lista las reglas instaladas por esta aplicación",
    )
    parser.add_argument(
        "--remove",
        action="append",
        default=[],
        metavar="ARCHIVO.rules",
        help="elimina una regla administrada (se puede repetir)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="muestra las reglas sin instalarlas",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="no pide confirmación antes de llamar a pkexec",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    colors = _colors()
    host = Host()

    try:
        if args.list:
            return _cmd_list(host, as_json=args.json, colors=colors)
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
            parser.error("--action requiere --device.")
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            parser.print_help()
            return 2
        return _interactive(host, args)
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        return 130
    except (HostError, CommandNotAvailable, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
