"""Pruebas del núcleo: detección, agrupación y generación de reglas."""

from __future__ import annotations

import unittest
from pathlib import Path

from udev_rule_generator.devices import (
    Joystick,
    joysticks_from_export_db,
    joysticks_from_proc,
    parse_export_db,
    parse_proc_blocks,
)
from udev_rule_generator.host import HostError
from udev_rule_generator.installed import _parse_header
from udev_rule_generator.presets import (
    PRESETS,
    STEAM,
    build_preset_content,
    get_preset,
    preset_files,
    presets_trigger,
    select_presets,
)
from udev_rule_generator.rules import (
    RuleAction,
    build_rule,
    rule_filename,
    validate_rule_filename,
)

FIXTURES = Path(__file__).parent / "fixtures"


class FakeHost:
    """Host mínimo para leer los fixtures sin tocar el sistema."""

    def __init__(self, proc_text: str = "") -> None:
        self.proc_text = proc_text

    def read_text(self, path: str) -> str:
        if path == "/proc/bus/input/devices":
            if not self.proc_text:
                raise HostError("sin proc")
            return self.proc_text
        raise HostError(f"archivo no disponible: {path}")

    def run(self, *args, **kwargs):
        raise HostError("comando no disponible")


def _device(
    *,
    name: str = "Test Pad",
    vendor_id: str = "045e",
    product_id: str = "0b12",
    bus: str = "usb",
) -> Joystick:
    return Joystick(
        key="test-key",
        name=name,
        vendor="Test",
        model=name,
        vendor_id=vendor_id,
        product_id=product_id,
        serial="",
        bus=bus,
        devpaths=("/devices/test",),
        event_devices=("/dev/input/event30",),
        js_devices=("/dev/input/js0",),
        input_names=(name,),
        properties={},
    )


class DetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proc_text = (FIXTURES / "proc-bus-input-devices.txt").read_text(
            encoding="utf-8"
        )
        self.export_text = (FIXTURES / "udevadm-export-db.txt").read_text(
            encoding="utf-8"
        )

    def test_parse_export_db(self) -> None:
        records = parse_export_db(self.export_text)
        self.assertEqual(len(records), 5)
        self.assertTrue(any(props.get("ID_INPUT_JOYSTICK") == "1" for _, props in records))

    def test_parse_proc_blocks(self) -> None:
        blocks = parse_proc_blocks(self.proc_text)
        self.assertEqual(len(blocks), 3)
        xbox = next(block for block in blocks if "Xbox" in block.name)
        self.assertIn("js0", xbox.handlers)
        self.assertEqual(xbox.vendor_id, "045e")
        self.assertEqual(xbox.product_id, "0b12")

    def test_groups_event_and_js_by_physical_device(self) -> None:
        devices = joysticks_from_export_db(self.export_text, FakeHost(self.proc_text))
        self.assertEqual(len(devices), 2)
        xbox = next(device for device in devices if device.product_id == "0b12")
        self.assertEqual(xbox.display_name, "Microsoft Xbox Series S|X Controller")
        self.assertEqual(xbox.event_devices, ("/dev/input/event30",))
        self.assertEqual(xbox.js_devices, ("/dev/input/js0",))
        self.assertEqual(
            xbox.input_names, ("Microsoft Xbox Series S|X Controller",)
        )
        self.assertTrue(xbox.is_usb)
        self.assertEqual(xbox.identifier, "045e:0b12")

    def test_detects_bluetooth(self) -> None:
        devices = joysticks_from_export_db(self.export_text, FakeHost(self.proc_text))
        dualsense = next(device for device in devices if device.product_id == "0ce6")
        self.assertTrue(dualsense.is_bluetooth)
        self.assertEqual(dualsense.bus_label, "Bluetooth")

    def test_proc_fallback(self) -> None:
        devices = joysticks_from_proc(FakeHost(self.proc_text))
        self.assertEqual(len(devices), 2)
        self.assertTrue(all(device.js_devices for device in devices))


class RuleTests(unittest.TestCase):
    def test_filename_is_stable_and_prefixed(self) -> None:
        device = _device()
        self.assertEqual(
            rule_filename(device, RuleAction.ALLOW),
            "10-udev-rule-generator-gamepad-045e-0b12-test-pad.rules",
        )
        self.assertEqual(
            rule_filename(device, RuleAction.IGNORE),
            "99-udev-rule-generator-ignore-045e-0b12-test-pad.rules",
        )

    def test_allow_usb_rule(self) -> None:
        spec = build_rule(_device(), RuleAction.ALLOW)
        self.assertIn('SUBSYSTEM=="usb"', spec.content)
        self.assertIn('ENV{ID_INPUT_JOYSTICK}="1"', spec.content)
        self.assertIn('SUBSYSTEM=="hidraw"', spec.content)
        self.assertIn("TAG+=\"uaccess\"", spec.content)
        self.assertEqual(spec.trigger, "change")
        self.assertNotIn("VID/PID desconocido", spec.content)
        self.assertNotIn("# Nodos:", spec.content)
        self.assertNotIn("# Nodes:", spec.content)
        lines = spec.content.splitlines()
        self.assertTrue(
            lines[0].startswith("# Generado por udev-rule-generator ")
        )
        self.assertEqual(lines[1], "")
        self.assertEqual(lines[2], "# Dispositivo: Test Pad")
        self.assertNotIn("# Bus:", spec.content)
        self.assertNotIn("# Acción:", spec.content)
        self.assertNotIn("# Permisos", spec.content)

    def test_ignore_usb_deauthorizes_and_denies(self) -> None:
        spec = build_rule(_device(), RuleAction.IGNORE)
        self.assertIn('ACTION=="add"', spec.content)
        self.assertIn('ATTR{authorized}="0"', spec.content)
        self.assertIn('MODE="0000"', spec.content)
        self.assertIn('TAG-="uaccess"', spec.content)
        self.assertEqual(spec.trigger, "add")

    def test_ignore_bluetooth_is_soft(self) -> None:
        spec = build_rule(_device(bus="bluetooth"), RuleAction.IGNORE)
        self.assertNotIn('ATTR{authorized}="0"', spec.content)
        self.assertIn('KERNELS=="*045E:0B12*"', spec.content)
        self.assertIn('MODE="0000"', spec.content)

    def test_rule_without_ids_does_not_emit_empty_attrs(self) -> None:
        device = _device(vendor_id="", product_id="")
        spec = build_rule(device, RuleAction.ALLOW)
        self.assertNotIn('idVendor}==""', spec.content)
        self.assertNotIn('idProduct}==""', spec.content)

    def test_rejects_quotes_in_name(self) -> None:
        with self.assertRaises(ValueError):
            build_rule(_device(name='Bad " Pad'), RuleAction.ALLOW)

    def test_generated_rule_is_recognized_as_managed(self) -> None:
        spec = build_rule(_device(), RuleAction.ALLOW)
        parsed = _parse_header(spec.filename, spec.content)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.kind, "generated")
        self.assertEqual(parsed.title, "Test Pad")

    def test_validate_rule_filename(self) -> None:
        validate_rule_filename("10-gamepad-045e-0b12-test.rules")
        for bad in ("../evil.rules", "gamepad.rules", "10-evil.txt", "10-a/b.rules"):
            with self.assertRaises(ValueError):
                validate_rule_filename(bad)


class PresetTests(unittest.TestCase):
    def test_only_steam_presets_are_packaged(self) -> None:
        self.assertEqual(len(PRESETS), 2)
        self.assertEqual(len(STEAM), 2)
        self.assertEqual({p.id for p in STEAM}, {"steam-input", "steam-vr"})
        self.assertEqual(PRESETS, STEAM)

    def test_steam_preset_content_has_valve_source(self) -> None:
        content = build_preset_content(get_preset("steam-input"))
        self.assertIn("ValveSoftware/steam-devices", content)

    def test_preset_files(self) -> None:
        files = preset_files(PRESETS)
        self.assertEqual(
            set(files),
            {"71-steam-input.rules", "71-steam-vr.rules"},
        )
        self.assertEqual(len(files), len(PRESETS))

    def test_presets_use_change_trigger(self) -> None:
        self.assertEqual(presets_trigger(STEAM), "change")
        self.assertEqual(presets_trigger(PRESETS), "change")

    def test_select_presets(self) -> None:
        self.assertEqual(
            {p.id for p in select_presets("steam")},
            {"steam-input", "steam-vr"},
        )
        with self.assertRaises(ValueError):
            select_presets("all")
        with self.assertRaises(ValueError):
            select_presets("steam-vr")
        with self.assertRaises(ValueError):
            select_presets("8bitdo")


if __name__ == "__main__":
    unittest.main()
