"""Pruebas de detección de Steam nativo y Flatpak."""

from __future__ import annotations

import unittest

from udev_rule_generator.host import CommandNotAvailable, CommandResult
from udev_rule_generator.steam import steam_running


def result(returncode: int, stdout: str = "") -> CommandResult:
    return CommandResult(
        argv=(),
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


class FakeHost:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, **_kwargs):
        self.calls.append(tuple(argv))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class SteamDetectionTests(unittest.TestCase):
    def test_native_steam_process(self) -> None:
        host = FakeHost([result(0, "1234\n")])
        self.assertTrue(steam_running(host))
        self.assertEqual(host.calls, [("pgrep", "-x", "steam")])

    def test_flatpak_steam_process(self) -> None:
        host = FakeHost(
            [
                result(1),
                result(1),
                result(0, "com.valvesoftware.Steam\t1234\n"),
            ]
        )
        self.assertTrue(steam_running(host))

    def test_steam_not_running(self) -> None:
        host = FakeHost(
            [
                result(1),
                result(1),
                result(0, "\n"),
            ]
        )
        self.assertFalse(steam_running(host))

    def test_missing_commands_are_not_fatal(self) -> None:
        host = FakeHost(
            [
                CommandNotAvailable("pgrep"),
                CommandNotAvailable("pgrep"),
                CommandNotAvailable("flatpak"),
            ]
        )
        self.assertFalse(steam_running(host))


if __name__ == "__main__":
    unittest.main()
