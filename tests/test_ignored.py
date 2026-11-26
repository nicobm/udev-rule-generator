"""Pruebas de la sección Ignorados: clasificación, HID y persistencia."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from udev_rule_generator import privileged
from udev_rule_generator.devices import (
    Joystick,
    hid_devices_from_export_db,
)
from udev_rule_generator.host import CommandResult
from udev_rule_generator.known import KnownDevice, KnownDevices
from udev_rule_generator.privileged import (
    HidBindingChange,
    _hid_binding_script,
    apply_rule_changes,
)


def _device(
    *,
    name: str = "ASRock LED Controller",
    vendor_id: str = "26ce",
    product_id: str = "01a2",
    serial: str = "A02019100900",
    js: bool = True,
    properties: dict[str, str] | None = None,
) -> Joystick:
    return Joystick(
        key="test-key",
        name=name,
        vendor="ASRock",
        model="LED Controller",
        vendor_id=vendor_id,
        product_id=product_id,
        serial=serial,
        bus="usb",
        devpaths=("/devices/test",),
        event_devices=("/dev/input/event10",),
        js_devices=("/dev/input/js0",) if js else (),
        input_names=(name,),
        properties=(
            {"ID_BUS": "usb", "ID_MODEL": "LED_Controller"}
            if properties is None
            else properties
        ),
    )


class IgnorableTests(unittest.TestCase):
    def test_js_without_joystick_property_is_ignorable(self) -> None:
        self.assertTrue(_device().is_ignorable)

    def test_real_joystick_is_not_ignorable(self) -> None:
        device = _device(
            properties={
                "ID_BUS": "usb",
                "ID_INPUT_JOYSTICK": "1",
            }
        )
        self.assertFalse(device.is_ignorable)

    def test_device_without_js_is_not_ignorable(self) -> None:
        self.assertFalse(_device(js=False).is_ignorable)

    def test_device_without_udev_properties_is_not_ignorable(self) -> None:
        self.assertFalse(_device(properties={}).is_ignorable)


class HidExportTests(unittest.TestCase):
    def test_parses_bound_and_unbound_hid_devices(self) -> None:
        export = """
P: /devices/pci0000:00/0000:00:14.0/usb1/1-13/1-13:1.0/0003:26CE:01A2.0006
M: 0003:26CE:01A2.0006
U: hid
E: DEVPATH=/devices/pci0000:00/0000:00:14.0/usb1/1-13/1-13:1.0/0003:26CE:01A2.0006
E: DRIVER=hid-generic
E: HID_ID=0003:000026CE:000001A2
E: HID_NAME=ASRock LED Controller
E: SUBSYSTEM=hid

P: /devices/pci0000:00/0000:00:14.0/usb1/1-14/1-14:1.0/0003:1234:5678.0001
U: hid
E: DEVPATH=/devices/pci0000:00/0000:00:14.0/usb1/1-14/1-14:1.0/0003:1234:5678.0001
E: HID_ID=0003:00001234:00005678
E: HID_NAME=Test HID
E: SUBSYSTEM=hid
""".strip()
        devices = hid_devices_from_export_db(export)
        self.assertEqual(len(devices), 2)
        asrock = next(d for d in devices if d.identifier == "26ce:01a2")
        self.assertEqual(asrock.sysname, "0003:26CE:01A2.0006")
        self.assertEqual(asrock.driver, "hid-generic")
        self.assertTrue(asrock.bound)
        test = next(d for d in devices if d.identifier == "1234:5678")
        self.assertEqual(test.driver, "")
        self.assertFalse(test.bound)


class KnownIgnoredTests(unittest.TestCase):
    def test_ignored_record_round_trips(self) -> None:
        device = _device()
        record = KnownDevice.from_ignored(
            device,
            driver="hid-generic",
        )
        self.assertTrue(record.ignorable)
        self.assertTrue(record.ignored)
        self.assertEqual(record.hid_driver, "hid-generic")
        restored = KnownDevice.from_dict(record.to_dict())
        self.assertEqual(restored.id, record.id)
        self.assertTrue(restored.ignorable)
        self.assertTrue(restored.ignored)
        self.assertEqual(restored.hid_driver, "hid-generic")

    def test_store_persists_ignored_state(self) -> None:
        device = _device()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            store = KnownDevices(path)
            record = store.set_ignored(
                "26ce|01a2|ASRock LED Controller|A02019100900",
                True,
                device=device,
                driver="hid-generic",
            )
            self.assertIsNotNone(record)
            reloaded = KnownDevices(path)
            saved = reloaded.get(
                "26ce|01a2|ASRock LED Controller|A02019100900"
            )
            self.assertIsNotNone(saved)
            assert saved is not None
            self.assertTrue(saved.ignored)
            self.assertTrue(saved.ignorable)

            updated = reloaded.set_ignored(
                saved.id,
                False,
                device=device,
                driver="hid-generic",
            )
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertFalse(updated.ignored)
            self.assertTrue(updated.ignorable)


class HidScriptTests(unittest.TestCase):
    def test_unbind_uses_current_driver(self) -> None:
        lines = _hid_binding_script(
            [HidBindingChange("26ce", "01a2", bound=False)]
        )
        script = "\n".join(lines)
        self.assertIn("/sys/bus/hid/devices/*26CE:01A2*", script)
        self.assertIn("/unbind", script)
        self.assertIn('readlink -f "$dev/driver"', script)

    def test_bind_uses_stored_driver(self) -> None:
        lines = _hid_binding_script(
            [
                HidBindingChange(
                    "26ce",
                    "01a2",
                    bound=True,
                    driver="hid-generic",
                )
            ]
        )
        script = "\n".join(lines)
        self.assertIn('"/sys/bus/hid/drivers/hid-generic"', script)
        self.assertIn("/bind", script)

    def test_invalid_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _hid_binding_script(
                [HidBindingChange("../etc", "01a2", bound=False)]
            )
        with self.assertRaises(ValueError):
            _hid_binding_script(
                [
                    HidBindingChange(
                        "26ce",
                        "01a2",
                        bound=True,
                        driver="hid-generic; rm -rf /",
                    )
                ]
            )


class FakePkexecHost:
    in_flatpak = False

    def __init__(self) -> None:
        self.argv: list[str] = []

    def which(self, program: str) -> str | None:
        return "/usr/bin/pkexec" if program == "pkexec" else None

    def run(self, argv, **_kwargs):
        self.argv = list(argv)
        return CommandResult(
            argv=tuple(argv),
            returncode=0,
            stdout="",
            stderr="",
        )


class PrivilegedIntegrationTests(unittest.TestCase):
    def test_hid_only_changes_reach_the_pkexec_script(self) -> None:
        host = FakePkexecHost()
        with mock.patch.object(
            privileged.os, "geteuid", return_value=1000
        ):
            result = apply_rule_changes(
                host,
                {},
                [],
                hid_changes=[
                    HidBindingChange("26ce", "01a2", bound=False)
                ],
            )
        self.assertTrue(result.used_pkexec)
        self.assertTrue(host.argv)
        script = host.argv[host.argv.index("-c") + 1]
        self.assertIn("26CE:01A2", script)
        self.assertIn("/unbind", script)


if __name__ == "__main__":
    unittest.main()
