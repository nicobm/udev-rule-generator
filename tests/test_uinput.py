"""Pruebas de detección del módulo uinput."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from udev_rule_generator.host import HostError
from udev_rule_generator.uinput import uinput_available


class FakeHost:
    def __init__(self, modules: list[str] | None = None, proc: str = "") -> None:
        self.modules = modules or []
        self.proc = proc

    def list_dir(self, _path: str) -> list[str]:
        return self.modules

    def read_text(self, _path: str) -> str:
        if not self.proc:
            raise HostError("sin proc")
        return self.proc


class UinputTests(unittest.TestCase):
    def test_detects_module_in_sys_module(self) -> None:
        self.assertTrue(uinput_available(FakeHost(["uinput"])))

    def test_detects_module_in_proc_modules(self) -> None:
        host = FakeHost([], "uinput 20480 0 - Live 0x0000000000000000\n")
        self.assertTrue(uinput_available(host))

    def test_debug_override_forces_off(self) -> None:
        with mock.patch.dict(os.environ, {"TEST_UINPUT_OFF": "1"}):
            self.assertFalse(uinput_available(FakeHost(["uinput"])))

    def test_unknown_state_does_not_disable(self) -> None:
        self.assertTrue(uinput_available(FakeHost([], "")))


if __name__ == "__main__":
    unittest.main()
