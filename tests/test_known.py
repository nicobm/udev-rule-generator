"""Pruebas del registro JSON de dispositivos guardados."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest import mock

from udev_rule_generator.cli import Colors, _cmd_known
from udev_rule_generator.devices import Joystick
from udev_rule_generator.userconfig import device_identity
from udev_rule_generator.known import KnownDevice, KnownDevices
from udev_rule_generator.installed import _parse_header
from udev_rule_generator.rules import RuleAction, build_rule


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


class KnownDevicesTests(unittest.TestCase):
    def test_record_persist_and_disable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            store = KnownDevices(path)
            device = _device()
            spec = build_rule(device, RuleAction.ALLOW)

            record = store.record_rule(device, spec)
            self.assertEqual(record.id, device_identity(device))
            self.assertTrue(record.active)
            self.assertEqual(record.filename, spec.filename)
            self.assertEqual(
                record.sha256,
                hashlib.sha256(record.content.encode("utf-8")).hexdigest(),
            )
            self.assertEqual(len(store), 1)

            reloaded = KnownDevices(path)
            loaded = reloaded.devices()[0]
            self.assertEqual(loaded.name, "Test Pad")
            self.assertEqual(loaded.identifier, "045e:0b12")
            self.assertEqual(loaded.action, "allow")
            self.assertEqual(loaded.content, spec.content)
            self.assertIn('ENV{ID_INPUT_JOYSTICK}="1"', loaded.content)

            self.assertTrue(reloaded.mark_inactive_by_filename(spec.filename))
            self.assertFalse(KnownDevices(path).devices()[0].active)

    def test_alias_persists_without_a_saved_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            store = KnownDevices(path)
            key = device_identity(_device())

            self.assertEqual(store.alias_for(key), "")
            store.set_alias(key, "  Joystick rojo  ")
            self.assertEqual(store.alias_for(key), "Joystick rojo")
            self.assertEqual(
                KnownDevices(path).alias_for(key),
                "Joystick rojo",
            )

            store.clear_alias(key)
            self.assertEqual(KnownDevices(path).alias_for(key), "")

    def test_icon_persists_without_a_saved_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            store = KnownDevices(path)
            key = device_identity(_device())

            store.set_icon(key, "joystick")
            self.assertEqual(store.icon_for(key), "joystick")
            self.assertEqual(KnownDevices(path).icon_for(key), "joystick")

    def test_color_persists_without_a_saved_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            store = KnownDevices(path)
            key = device_identity(_device())

            store.set_color(key, "cyan")
            self.assertEqual(store.color_for(key), "cyan")
            self.assertEqual(
                KnownDevices(path).color_for(key),
                "cyan",
            )

    def test_clear_all_removes_devices_and_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            store = KnownDevices(path)
            device = _device()
            key = device_identity(device)
            store.record_rule(
                device,
                build_rule(device, RuleAction.ALLOW),
            )
            store.set_alias(key, "Temporal")
            store.set_icon(key, "joystick")
            store.set_color(key, "cyan")
            store.clear_all()

            reloaded = KnownDevices(path)
            self.assertEqual(reloaded.devices(), [])
            self.assertEqual(reloaded.alias_for(key), "")
            self.assertEqual(reloaded.icon_for(key), "")
            self.assertEqual(reloaded.color_for(key), "")

    def test_hidden_state_persists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            store = KnownDevices(path)
            record = store.record_rule(
                _device(), build_rule(_device(), RuleAction.ALLOW)
            )
            self.assertFalse(record.hidden)

            store.set_hidden(record.id, True)
            self.assertTrue(KnownDevices(path).devices()[0].hidden)

            store.set_hidden(record.id, False)
            self.assertFalse(KnownDevices(path).devices()[0].hidden)

    def test_cli_hide_and_unhide_known(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ, {"XDG_CONFIG_HOME": directory}
            ), mock.patch(
                "udev_rule_generator.cli.list_installed_rules",
                return_value=[],
            ):
                store = KnownDevices()
                device = _device()
                spec = build_rule(device, RuleAction.ALLOW)
                record = store.record_rule(device, spec)
                store.mark_inactive_by_filename(spec.filename)

                with redirect_stdout(io.StringIO()):
                    _cmd_known(
                        None,  # type: ignore[arg-type]
                        as_json=False,
                        enable=None,
                        disable=None,
                        hide=record.id,
                        unhide=None,
                        assume_yes=True,
                        dry_run=False,
                        colors=Colors(False),
                    )
                self.assertTrue(KnownDevices().devices()[0].hidden)

                with redirect_stdout(io.StringIO()):
                    _cmd_known(
                        None,  # type: ignore[arg-type]
                        as_json=False,
                        enable=None,
                        disable=None,
                        hide=None,
                        unhide=record.id,
                        assume_yes=True,
                        dry_run=False,
                        colors=Colors(False),
                    )
                self.assertFalse(KnownDevices().devices()[0].hidden)

    def test_reconcile_imports_and_tracks_existing_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            store = KnownDevices(path)
            spec = build_rule(_device(), RuleAction.ALLOW)
            parsed = _parse_header(spec.filename, spec.content)
            self.assertIsNotNone(parsed)

            store.reconcile([parsed])
            self.assertEqual(len(store), 1)
            imported = store.devices()[0]
            self.assertEqual(imported.filename, spec.filename)
            self.assertEqual(imported.action, "allow")
            self.assertEqual(imported.vendor_id, "045e")
            self.assertEqual(imported.product_id, "0b12")
            self.assertEqual(imported.name, "Test Pad")
            self.assertTrue(imported.active)

            store.reconcile([])
            self.assertFalse(store.devices()[0].active)

    def test_build_spec_migrates_old_filename_and_updates_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            store = KnownDevices(path)
            spec = build_rule(_device(), RuleAction.ALLOW)
            legacy = spec.content.replace(
                "# Dispositivo: Test Pad\n",
                "# Dispositivo: Test Pad\n"
                "# Nodos: /dev/input/js0, /dev/input/event30\n",
            )
            parsed = _parse_header(spec.filename, legacy)
            self.assertIsNotNone(parsed)

            store.reconcile([parsed])
            record = store.devices()[0]
            self.assertNotIn("# Nodos:", record.content)

            legacy_filename = "10-gamepad-045e-0b12-test-pad.rules"
            legacy_record = replace(
                record, filename=legacy_filename, content=legacy
            )
            rebuilt = legacy_record.build_spec()
            self.assertEqual(rebuilt.filename, spec.filename)
            self.assertNotEqual(rebuilt.filename, legacy_filename)
            self.assertNotIn("# Nodos:", rebuilt.content)
            self.assertIn('ENV{ID_INPUT_JOYSTICK}="1"', rebuilt.content)

    def test_bluetooth_rule_reads_ids_from_kernel_line(self) -> None:
        device = _device()
        bluetooth = replace(device, bus="bluetooth")
        spec = build_rule(bluetooth, RuleAction.ALLOW)
        self.assertNotIn("# Bus:", spec.content)
        parsed = _parse_header(spec.filename, spec.content)
        self.assertIsNotNone(parsed)

        record = KnownDevice.from_installed(parsed)
        self.assertEqual(record.vendor_id, "045e")
        self.assertEqual(record.product_id, "0b12")
        self.assertEqual(record.bus, "bluetooth")
        self.assertEqual(record.action, "allow")
        self.assertIn("KERNELS", record.build_spec().content)

    def test_batch_disable_saves_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = KnownDevices(Path(directory) / "devices.json")
            first = _device("First Pad")
            second = _device("Second Pad")
            store.record_rule(first, build_rule(first, RuleAction.ALLOW))
            store.record_rule(second, build_rule(second, RuleAction.ALLOW))
            filenames = [device.filename for device in store.devices()]

            with mock.patch.object(
                store, "save", wraps=store.save
            ) as save:
                self.assertTrue(store.mark_inactive_by_filenames(filenames))

            save.assert_called_once()
            self.assertTrue(
                all(not device.active for device in store.devices())
            )

    def test_corrupt_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "devices.json"
            path.write_text("no es json", encoding="utf-8")
            store = KnownDevices(path)
            self.assertEqual(len(store), 0)

    def test_from_dict_defaults(self) -> None:
        record = KnownDevice.from_dict({"name": "Only a name"})
        self.assertEqual(record.name, "Only a name")
        self.assertEqual(record.action, "allow")
        self.assertFalse(record.active)


if __name__ == "__main__":
    unittest.main()
