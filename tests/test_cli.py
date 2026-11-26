"""Pruebas de los argumentos de la CLI."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

from udev_rule_generator.cli import build_parser, main


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
