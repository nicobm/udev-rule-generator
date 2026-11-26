"""Pruebas del almacenamiento de dispositivos ocultos."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from udev_rule_generator.devices import Joystick
from udev_rule_generator.hidden import HiddenDevices, device_identity


def _device(name: str = "Test Pad", serial: str = "abc123") -> Joystick:
    return Joystick(
        key=f"key-{name}",
        name=name,
        vendor="Test",
        model=name,
        vendor_id="045e",
        product_id="0b12",
        serial=serial,
        bus="usb",
        devpaths=("/devices/test",),
        event_devices=("/dev/input/event30",),
        js_devices=("/dev/input/js0",),
        input_names=(name,),
        properties={},
    )


class HiddenDevicesTests(unittest.TestCase):
    def test_hide_persist_unhide(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hidden.json"
            store = HiddenDevices(path)
            device = _device()

            self.assertFalse(store.is_hidden(device))
            store.hide(device)
            self.assertTrue(store.is_hidden(device))
            self.assertEqual(len(store.devices()), 1)

            reloaded = HiddenDevices(path)
            self.assertTrue(reloaded.is_hidden(device))
            hidden = reloaded.devices()[0]
            self.assertEqual(hidden.name, "Test Pad")
            self.assertEqual(hidden.identifier, "045e:0b12")

            reloaded.unhide(hidden.id)
            self.assertFalse(reloaded.is_hidden(device))
            self.assertEqual(len(reloaded), 0)

    def test_identity_does_not_depend_on_device_path(self) -> None:
        first = _device()
        second = _device()
        self.assertEqual(device_identity(first), device_identity(second))

    def test_corrupt_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hidden.json"
            path.write_text("no es json", encoding="utf-8")
            store = HiddenDevices(path)
            self.assertEqual(len(store), 0)


if __name__ == "__main__":
    unittest.main()
