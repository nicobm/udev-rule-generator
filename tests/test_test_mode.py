"""Tests for the development-only TEST flag."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from gui.test_mode import test_mode_enabled


class TestModeTests(unittest.TestCase):
    def test_enabled_values(self) -> None:
        for value in ("1", "true", "YES", "on", " 1 "):
            with mock.patch.dict(os.environ, {"TEST": value}):
                self.assertTrue(test_mode_enabled())

    def test_disabled_or_missing_value(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST", None)
            self.assertFalse(test_mode_enabled())
        for value in ("0", "false", "no", "off", ""):
            with mock.patch.dict(os.environ, {"TEST": value}):
                self.assertFalse(test_mode_enabled())


if __name__ == "__main__":
    unittest.main()
