"""Pruebas de validación de reglas de presets."""

from __future__ import annotations

import unittest

from udev_rule_generator.presets import (
    STEAM,
    build_preset_content,
    validate_rule_text,
)


class RuleValidationTests(unittest.TestCase):
    def test_bundled_steam_rules_are_valid(self) -> None:
        for preset in STEAM:
            content = build_preset_content(preset)
            self.assertIn("ValveSoftware/steam-devices", content)

    def test_rejects_unexpected_run_command(self) -> None:
        with self.assertRaises(ValueError):
            validate_rule_text(
                'KERNEL=="input*", RUN+="/bin/sh -c \'rm -rf /\'"\n',
                filename="evil.rules",
            )

    def test_rejects_program_and_import(self) -> None:
        for line in (
            'PROGRAM="/bin/sh -c evil"\n',
            'IMPORT{program}="/bin/sh -c evil"\n',
        ):
            with self.assertRaises(ValueError):
                validate_rule_text(line, filename="evil.rules")

    def test_allows_the_known_steam_run_line(self) -> None:
        line = (
            'KERNEL=="input*", ATTRS{name}=="Lic Pro Controller", '
            'RUN{program}+="/bin/sh -c \'udevadm test-builtin uaccess '
            '/sys/%p/../../hidraw/hidraw*\'"\n'
        )
        self.assertEqual(validate_rule_text(line, filename="steam.rules"), line)

    def test_rejects_binary_data(self) -> None:
        with self.assertRaises(ValueError):
            validate_rule_text("KERNEL==\"input*\"\x00\n", filename="evil.rules")
