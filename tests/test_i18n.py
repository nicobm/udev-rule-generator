"""Pruebas de autodetección de idioma y traducciones."""

from __future__ import annotations

import unittest
from unittest import mock

from udev_rule_generator import i18n


class LanguageDetectionTests(unittest.TestCase):
    def test_english_us_and_uk(self) -> None:
        self.assertEqual(i18n.detect_language("en_US.UTF-8"), "en")
        self.assertEqual(i18n.detect_language("en_GB.UTF-8"), "en")
        self.assertEqual(i18n.detect_language("en-US"), "en")
        self.assertEqual(i18n.detect_language("en-GB"), "en")

    def test_spanish_variants(self) -> None:
        self.assertEqual(i18n.detect_language("es_ES.UTF-8"), "es")
        self.assertEqual(i18n.detect_language("es_AR.UTF-8"), "es")
        self.assertEqual(i18n.detect_language("es_MX.UTF-8"), "es")
        self.assertEqual(i18n.detect_language("es"), "es")

    def test_other_locales_fall_back_to_english(self) -> None:
        self.assertEqual(i18n.detect_language("fr_FR.UTF-8"), "en")
        self.assertEqual(i18n.detect_language("de_DE.UTF-8"), "en")
        self.assertEqual(i18n.detect_language("C"), "en")
        self.assertEqual(i18n.detect_language(""), "en")

    def test_language_list_from_environment(self) -> None:
        self.assertEqual(i18n.detect_language("en_GB:en"), "en")
        self.assertEqual(i18n.detect_language("es_AR:es"), "es")


class TranslationTests(unittest.TestCase):
    def test_translates_when_english(self) -> None:
        with mock.patch.object(i18n, "LANGUAGE", "en"):
            self.assertEqual(
                i18n.tr("Habilitar (predeterminado)"), "Enable (default)"
            )
            self.assertEqual(
                i18n.tr(
                    "Se instalará como /etc/udev/rules.d/{filename}",
                    filename="10-test.rules",
                ),
                "It will be installed as /etc/udev/rules.d/10-test.rules",
            )

    def test_keeps_spanish_by_default(self) -> None:
        with mock.patch.object(i18n, "LANGUAGE", "es"):
            self.assertEqual(
                i18n.tr("Habilitar (predeterminado)"),
                "Habilitar (predeterminado)",
            )

    def test_unknown_text_is_returned_as_is(self) -> None:
        with mock.patch.object(i18n, "LANGUAGE", "en"):
            self.assertEqual(i18n.tr("Texto sin traducir"), "Texto sin traducir")


if __name__ == "__main__":
    unittest.main()
