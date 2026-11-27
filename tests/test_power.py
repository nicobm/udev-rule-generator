"""Pruebas del control de energía USB sin tocar el sistema real."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from udev_rule_generator import power
from udev_rule_generator.host import Host


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


class UsbPathTests(unittest.TestCase):
    def test_extracts_device_not_interface(self) -> None:
        devpaths = (
            "/devices/pci0000:00/0000:00:14.0/usb1/1-2/1-2:1.0/input/"
            "input20/event18",
        )
        self.assertEqual(
            power.usb_sysname_from_devpaths(devpaths),
            "1-2",
        )

    def test_nested_hub_uses_last_usb_device(self) -> None:
        devpaths = (
            "/devices/pci0000:00/0000:00:14.0/usb1/1-1/1-1.2/1-1.2:1.0/"
            "input/input12/js0",
        )
        self.assertEqual(
            power.usb_sysname_from_devpaths(devpaths),
            "1-1.2",
        )

    def test_no_usb_device(self) -> None:
        self.assertEqual(
            power.usb_sysname_from_devpaths(
                ("/devices/platform/i8042/serio0/input/input3/event3",)
            ),
            "",
        )


class ScanUsbPowerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.host = Host(in_flatpak=False)

    def _device(
        self,
        sysname: str,
        vendor: str = "045e",
        product: str = "02fd",
        serial: str = "",
        authorized: str = "1",
        product_name: str = "Controller",
    ) -> None:
        base = self.directory / sysname
        _write(base / "idVendor", vendor + "\n")
        _write(base / "idProduct", product + "\n")
        _write(base / "serial", serial + "\n")
        _write(base / "product", product_name + "\n")
        _write(base / "authorized", authorized + "\n")

    def test_reads_authorized_state(self) -> None:
        self._device("1-2", serial="ABC", authorized="0")
        devices = power.scan_usb_power(
            self.host, directory=str(self.directory)
        )
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].sysname, "1-2")
        self.assertEqual(devices[0].identifier, "045e:02fd")
        self.assertEqual(devices[0].serial, "ABC")
        self.assertFalse(devices[0].authorized)

    def test_skips_devices_without_complete_ids(self) -> None:
        self._device("1-2", vendor="")
        self._device("1-3", product="zzzz")
        self._device("usb1")
        devices = power.scan_usb_power(
            self.host, directory=str(self.directory)
        )
        self.assertEqual(devices, [])

    def test_skips_unknown_authorized_value(self) -> None:
        self._device("1-2", authorized="?")
        devices = power.scan_usb_power(
            self.host, directory=str(self.directory)
        )
        self.assertEqual(devices, [])

    def test_find_by_sysname_and_serial(self) -> None:
        self._device("1-2", serial="ABC")
        self._device("1-3", serial="XYZ")
        devices = power.scan_usb_power(
            self.host, directory=str(self.directory)
        )
        by_path = power.find_usb_power(
            devices,
            vendor_id="045e",
            product_id="02fd",
            sysname="1-3",
        )
        self.assertIsNotNone(by_path)
        self.assertEqual(by_path.sysname, "1-3")
        by_serial = power.find_usb_power(
            devices,
            vendor_id="045e",
            product_id="02fd",
            serial="ABC",
        )
        self.assertIsNotNone(by_serial)
        self.assertEqual(by_serial.sysname, "1-2")
        by_stale_path = power.find_usb_power(
            devices,
            vendor_id="045e",
            product_id="02fd",
            serial="ABC",
            sysname="1-3",
        )
        self.assertIsNotNone(by_stale_path)
        self.assertEqual(by_stale_path.sysname, "1-2")

    def test_ambiguous_devices_are_not_selected(self) -> None:
        self._device("1-2")
        self._device("1-3")
        devices = power.scan_usb_power(
            self.host, directory=str(self.directory)
        )
        self.assertIsNone(
            power.find_usb_power(
                devices,
                vendor_id="045e",
                product_id="02fd",
            )
        )


class SetUsbPowerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.target = self.directory / "1-2" / "authorized"
        _write(self.target, "1\n")
        self.host = Host(in_flatpak=False)

    def test_writes_one_or_zero_as_root(self) -> None:
        with mock.patch.object(power.os, "geteuid", return_value=0):
            power.set_usb_power(
                self.host,
                "1-2",
                False,
                directory=str(self.directory),
            )
            self.assertEqual(self.target.read_text(encoding="ascii"), "0")
            power.set_usb_power(
                self.host,
                "1-2",
                True,
                directory=str(self.directory),
            )
        self.assertEqual(self.target.read_text(encoding="ascii"), "1")

    def test_rejects_unsafe_sysname(self) -> None:
        with self.assertRaises(ValueError):
            power.set_usb_power(
                self.host,
                "../1-2",
                False,
                directory=str(self.directory),
            )


class KnownDeviceUsbPathTests(unittest.TestCase):
    def test_round_trips_usb_path(self) -> None:
        from udev_rule_generator.known import KnownDevice

        record = KnownDevice.from_dict(
            {
                "id": "045e|02fd|Controller|",
                "name": "Controller",
                "vendor_id": "045e",
                "product_id": "02fd",
                "usb_path": "1-2",
            }
        )
        self.assertEqual(record.usb_path, "1-2")
        self.assertEqual(record.to_dict()["usb_path"], "1-2")


if __name__ == "__main__":
    unittest.main()
