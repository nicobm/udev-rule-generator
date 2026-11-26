"""Pruebas de las copias de seguridad .tar.gz."""

from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from udev_rule_generator.backup import (
    BackupError,
    create_backup,
    import_backup,
)
from udev_rule_generator.devices import Joystick
from udev_rule_generator.installed import InstalledRule
from udev_rule_generator.known import KnownDevices
from udev_rule_generator.rules import RuleAction, build_rule
from udev_rule_generator.userconfig import device_identity


def _device() -> Joystick:
    return Joystick(
        key="backup-key",
        name="Backup Pad",
        vendor="Test",
        model="Backup Pad",
        vendor_id="045e",
        product_id="0b12",
        serial="backup-serial",
        bus="usb",
        devpaths=(),
        event_devices=(),
        js_devices=(),
        input_names=("Backup Pad",),
        properties={},
    )


class BackupTests(unittest.TestCase):
    def test_export_includes_devices_aliases_and_generated_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = KnownDevices(Path(directory) / "devices.json")
            device = _device()
            spec = build_rule(device, RuleAction.ALLOW)
            store.record_rule(device, spec)
            store.set_alias(device_identity(device), "Backup rojo")
            store.set_icon(device_identity(device), "joystick")
            store.set_color(device_identity(device), "cyan")
            generated = InstalledRule(
                filename=spec.filename,
                kind="generated",
                title="Backup Pad",
                source="",
                content=spec.content,
            )
            preset = InstalledRule(
                filename="71-steam-devices-valve.rules",
                kind="preset",
                title="Steam",
                source="",
                content="# Installed by udev-rule-generator\n",
            )
            with mock.patch(
                "udev_rule_generator.backup.list_installed_rules",
                return_value=[generated, preset],
            ):
                data, info = create_backup(object(), store)  # type: ignore[arg-type]

        self.assertEqual(info.rules, (spec.filename,))
        self.assertEqual(info.devices, 1)
        self.assertEqual(info.aliases, 1)

        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            names = set(archive.getnames())
            self.assertIn("manifest.json", names)
            self.assertIn("devices.json", names)
            self.assertIn(f"rules/{spec.filename}", names)
            self.assertNotIn("rules/71-steam-devices-valve.rules", names)
            devices_file = archive.extractfile("devices.json")
            self.assertIsNotNone(devices_file)
            payload = json.loads(devices_file.read().decode("utf-8"))
            self.assertIn(device_identity(device), payload["devices"])
            self.assertEqual(
                payload["aliases"][device_identity(device)],
                "Backup rojo",
            )
            self.assertEqual(
                payload["icons"][device_identity(device)],
                "joystick",
            )
            self.assertEqual(
                payload["colors"][device_identity(device)],
                "cyan",
            )

    def test_import_restores_data_without_installing_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_store = KnownDevices(Path(directory) / "source.json")
            device = _device()
            spec = build_rule(device, RuleAction.ALLOW)
            source_store.record_rule(device, spec)
            source_store.set_alias(device_identity(device), "Backup rojo")
            source_store.set_icon(device_identity(device), "joystick")
            source_store.set_color(device_identity(device), "cyan")
            generated = InstalledRule(
                filename=spec.filename,
                kind="generated",
                title="Backup Pad",
                source="",
                content=spec.content,
            )
            preset = InstalledRule(
                filename="71-steam-devices-valve.rules",
                kind="preset",
                title="Steam",
                source="",
                content="# Installed by udev-rule-generator\n",
            )
            with mock.patch(
                "udev_rule_generator.backup.list_installed_rules",
                return_value=[generated, preset],
            ):
                data, _info = create_backup(object(), source_store)  # type: ignore[arg-type]

            target_store = KnownDevices(Path(directory) / "target.json")
            with mock.patch(
                "udev_rule_generator.backup.list_installed_rules",
                return_value=[],
            ):
                result = import_backup(
                    object(),  # type: ignore[arg-type]
                    target_store,
                    data,
                )

            self.assertEqual(result.devices, 1)
            self.assertEqual(result.aliases, 1)
            self.assertEqual(result.rules, 1)
            self.assertEqual(
                target_store.alias_for(device_identity(device)),
                "Backup rojo",
            )
            self.assertEqual(
                target_store.icon_for(device_identity(device)),
                "joystick",
            )
            self.assertEqual(
                target_store.color_for(device_identity(device)),
                "cyan",
            )
            imported = target_store.get(device_identity(device))
            self.assertIsNotNone(imported)
            assert imported is not None
            self.assertFalse(imported.active)

    def test_import_rejects_path_traversal(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            payload = b'{"devices": {}, "aliases": {}}'
            info = tarfile.TarInfo("../devices.json")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        with tempfile.TemporaryDirectory() as directory:
            store = KnownDevices(Path(directory) / "devices.json")
            with self.assertRaises(BackupError):
                import_backup(object(), store, buffer.getvalue())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
