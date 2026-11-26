"""Pruebas de los argumentos de la CLI."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from udev_rule_generator.cli import _collect_devices, build_parser, main
from udev_rule_generator.devices import Joystick
from udev_rule_generator.known import KnownDevices
from udev_rule_generator.rules import RuleAction, build_rule
from udev_rule_generator.userconfig import device_identity


class GuiArgumentTests(unittest.TestCase):
    def test_parser_accepts_gui(self) -> None:
        args = build_parser().parse_args(["--gui"])
        self.assertTrue(args.gui)

    def test_gui_is_routed_to_the_gui_launcher(self) -> None:
        with mock.patch("gui.main.main", return_value=0) as gui_main:
            result = main(["--gui"])
        self.assertEqual(result, 0)
        gui_main.assert_called_once()
        self.assertEqual(gui_main.call_args.args[0], [sys.argv[0]])

    def test_gui_rejects_other_actions(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--gui", "--list"])
        self.assertEqual(raised.exception.code, 2)


class DeviceListTests(unittest.TestCase):
    def test_saved_disconnected_device_is_listed(self) -> None:
        device = Joystick(
            key="saved-key",
            name="Saved Pad",
            vendor="Test",
            model="Saved Pad",
            vendor_id="045e",
            product_id="0b12",
            serial="saved-serial",
            bus="usb",
            devpaths=(),
            event_devices=(),
            js_devices=(),
            input_names=("Saved Pad",),
            properties={},
        )
        with tempfile.TemporaryDirectory() as directory:
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}),
                mock.patch(
                    "udev_rule_generator.cli.detect_joysticks",
                    return_value=[],
                ),
                mock.patch(
                    "udev_rule_generator.cli.list_installed_rules",
                    return_value=[],
                ),
            ):
                store = KnownDevices()
                spec = build_rule(device, RuleAction.ALLOW)
                store.record_rule(device, spec)
                entries = _collect_devices(None)  # type: ignore[arg-type]

        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0].connected)
        self.assertIsNotNone(entries[0].saved)
        self.assertEqual(entries[0].device.display_name, "Saved Pad")


class BackupArgumentTests(unittest.TestCase):
    def test_parser_accepts_backup_actions(self) -> None:
        args = build_parser().parse_args(["--export", "backup.tar.gz"])
        self.assertEqual(args.export, "backup.tar.gz")
        args = build_parser().parse_args(["--import", "backup.tar.gz"])
        self.assertEqual(args.import_backup, "backup.tar.gz")

    def test_cli_export_writes_archive(self) -> None:
        device = Joystick(
            key="export-key",
            name="Export Pad",
            vendor="Test",
            model="Export Pad",
            vendor_id="045e",
            product_id="0b12",
            serial="export-serial",
            bus="usb",
            devpaths=(),
            event_devices=(),
            js_devices=(),
            input_names=("Export Pad",),
            properties={},
        )
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "backup.tar.gz"
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}),
                mock.patch(
                    "udev_rule_generator.backup.list_installed_rules",
                    return_value=[],
                ),
                mock.patch(
                    "udev_rule_generator.cli.list_installed_rules",
                    return_value=[],
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                store = KnownDevices()
                store.record_rule(
                    device,
                    build_rule(device, RuleAction.ALLOW),
                )
                result = main(["--export", str(archive)])
            self.assertEqual(result, 0)
            self.assertTrue(archive.is_file())
            self.assertGreater(archive.stat().st_size, 0)


class AliasArgumentTests(unittest.TestCase):
    def test_parser_accepts_alias_actions(self) -> None:
        args = build_parser().parse_args(
            ["--alias", "045e:0b12", "Joystick rojo"]
        )
        self.assertEqual(args.alias, ["045e:0b12", "Joystick rojo"])
        self.assertEqual(
            build_parser().parse_args(["--unalias", "1"]).unalias,
            "1",
        )

    def test_alias_set_and_remove_for_connected_device(self) -> None:
        device = Joystick(
            key="alias-key",
            name="Test Pad",
            vendor="Test",
            model="Test Pad",
            vendor_id="045e",
            product_id="0b12",
            serial="alias-serial",
            bus="usb",
            devpaths=(),
            event_devices=(),
            js_devices=(),
            input_names=("Test Pad",),
            properties={},
        )
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}),
                mock.patch(
                    "udev_rule_generator.cli.detect_joysticks",
                    return_value=[device],
                ),
                mock.patch(
                    "udev_rule_generator.cli.list_installed_rules",
                    return_value=[],
                ),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(
                    main(["--alias", "045e:0b12", "Joystick rojo"]),
                    0,
                )
                store = KnownDevices()
                key = device_identity(device)
                self.assertEqual(store.alias_for(key), "Joystick rojo")
                self.assertEqual(
                    main(["--unalias", "Joystick rojo"]),
                    0,
                )
                self.assertEqual(KnownDevices().alias_for(key), "")
        self.assertIn("Alias guardado", output.getvalue())
        self.assertIn("Alias eliminado", output.getvalue())


class KnownArgumentTests(unittest.TestCase):
    def test_parser_accepts_known_actions(self) -> None:
        args = build_parser().parse_args(
            ["--enable-known", "045e:02fd"]
        )
        self.assertEqual(args.enable_known, "045e:02fd")
        self.assertTrue(build_parser().parse_args(["--known"]).known)

    def test_known_list_with_empty_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}),
                mock.patch(
                    "udev_rule_generator.cli.list_installed_rules",
                    return_value=[],
                ),
                contextlib.redirect_stdout(output),
            ):
                result = main(["--known"])
        self.assertEqual(result, 0)
        self.assertIn("No hay dispositivos guardados", output.getvalue())


if __name__ == "__main__":
    unittest.main()
