"""Pruebas de la identidad estable de dispositivos."""

from __future__ import annotations

import unittest

from udev_rule_generator.devices import Joystick
from udev_rule_generator.userconfig import device_identity


def _device() -> Joystick:
    return Joystick(
        key="key-test",
        name="Test Pad",
        vendor="Test",
        model="Test Pad",
        vendor_id="045e",
        product_id="0b12",
        serial="abc123",
        bus="usb",
        devpaths=("/devices/test",),
        event_devices=("/dev/input/event30",),
        js_devices=("/dev/input/js0",),
        input_names=("Test Pad",),
        properties={},
    )


class DeviceIdentityTests(unittest.TestCase):
    def test_identity_does_not_depend_on_device_path(self) -> None:
        first = _device()
        second = Joystick(
            key="other-key",
            name=first.name,
            vendor=first.vendor,
            model=first.model,
            vendor_id=first.vendor_id,
            product_id=first.product_id,
            serial=first.serial,
            bus=first.bus,
            devpaths=("/devices/other",),
            event_devices=("/dev/input/event31",),
            js_devices=("/dev/input/js1",),
            input_names=first.input_names,
            properties={},
        )
        self.assertEqual(device_identity(first), device_identity(second))


if __name__ == "__main__":
    unittest.main()
