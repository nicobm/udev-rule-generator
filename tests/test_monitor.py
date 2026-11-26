"""Pruebas del parser de eventos de udevadm monitor."""

from __future__ import annotations

import io
import unittest

from udev_rule_generator.monitor import UdevMonitor, parse_monitor_stream


class FakeProcess:
    def __init__(self, text: str) -> None:
        self.stdout = io.StringIO(text)

    def terminate(self) -> None:
        pass

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        pass


class FakeMonitorHost:
    def __init__(self, text: str) -> None:
        self.text = text

    def which(self, program: str) -> str | None:
        return "/usr/bin/udevadm" if program == "udevadm" else None

    def popen(self, _args):
        return FakeProcess(self.text)


class MonitorParserTests(unittest.TestCase):
    def test_parses_multiple_events(self) -> None:
        lines = [
            "monitor will print the received events for:\n",
            "UDEV - the event which udev sends out after rule processing\n",
            "\n",
            "UDEV  [123.456] add      /devices/virtual/input/input30 (input)\n",
            "ACTION=add\n",
            "DEVPATH=/devices/virtual/input/input30\n",
            "SUBSYSTEM=input\n",
            "DEVNAME=/dev/input/event30\n",
            "ID_INPUT_JOYSTICK=1\n",
            "\n",
            "UDEV  [124.000] remove   /devices/virtual/input/input30 (input)\n",
            "ACTION=remove\n",
            "SUBSYSTEM=input\n",
            "\n",
        ]
        events = list(parse_monitor_stream(lines))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["ACTION"], "add")
        self.assertEqual(events[0]["SUBSYSTEM"], "input")
        self.assertEqual(events[0]["ID_INPUT_JOYSTICK"], "1")
        self.assertEqual(events[1]["ACTION"], "remove")

    def test_ignores_non_property_lines(self) -> None:
        lines = [
            "UDEV  [1.0] add /devices/a (input)\n",
            "ACTION=add\n",
            "SUBSYSTEM=input\n",
        ]
        events = list(parse_monitor_stream(lines))
        self.assertEqual(events, [{"ACTION": "add", "SUBSYSTEM": "input"}])

    def test_monitor_calls_callback_for_add_and_remove(self) -> None:
        text = (
            "UDEV  [1.0] add /devices/a (input)\n"
            "ACTION=add\n"
            "SUBSYSTEM=input\n"
            "\n"
            "UDEV  [2.0] remove /devices/a (input)\n"
            "ACTION=remove\n"
            "SUBSYSTEM=input\n"
            "\n"
        )
        events: list[dict[str, str]] = []
        monitor = UdevMonitor(FakeMonitorHost(text), events.append)
        self.assertTrue(monitor.start())
        assert monitor._thread is not None
        monitor._thread.join(timeout=2)
        self.assertEqual(
            [event["ACTION"] for event in events],
            ["add", "remove"],
        )


if __name__ == "__main__":
    unittest.main()
