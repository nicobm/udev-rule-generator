"""Pruebas de los argumentos de la CLI."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

from udev_rule_generator.cli import _collect_devices, build_parser, main
from udev_rule_generator.devices import Joystick
from udev_rule_generator.known import KnownDevices
from udev_rule_generator.rules import RuleAction, build_rule


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
