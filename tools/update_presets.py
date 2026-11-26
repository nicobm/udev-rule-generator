#!/usr/bin/env python3
"""Refresh the bundled preset snapshots from their upstream sources.

The application itself does not use the network: it ships reviewed copies of
the rules in ``udev_rule_generator/data/presets``.  This development tool
downloads the current files from Codeberg/GitHub so they can be reviewed,
tested, and committed.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from udev_rule_generator.presets import _UPSTREAM_TITLES  # noqa: E402

PRESET_DIR = ROOT / "udev_rule_generator" / "data" / "presets"

FABISCAFE_RAW = "https://codeberg.org/fabiscafe/game-devices-udev/raw/branch/main/"
STEAM_RAW = "https://raw.githubusercontent.com/ValveSoftware/steam-devices/master/"
USER_AGENT = "udev-rule-generator-preset-updater"


def normalize(text: str) -> str:
    """Normalize line endings and trailing whitespace for a stable diff."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).rstrip() + "\n"


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} for {url}")
        return normalize(response.read().decode("utf-8"))


def remote_files() -> dict[str, str]:
    files: dict[str, str] = {}
    for name in _UPSTREAM_TITLES:
        files[name] = f"{FABISCAFE_RAW}src/{name}"
    files["LICENSE.game-devices-udev"] = f"{FABISCAFE_RAW}LICENSE"

    for name in ("60-steam-input.rules", "60-steam-vr.rules"):
        files[name] = f"{STEAM_RAW}{name}"
    files["LICENSE.steam-devices"] = f"{STEAM_RAW}LICENSE"
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="only report whether upstream files differ; write nothing",
    )
    args = parser.parse_args()

    PRESET_DIR.mkdir(parents=True, exist_ok=True)
    files = remote_files()
    changed: list[str] = []
    failed: list[str] = []

    print(f"Preset directory: {PRESET_DIR}")
    for filename, url in files.items():
        target = PRESET_DIR / filename
        try:
            content = fetch(url)
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
            print(f"  ERROR  {filename}: {exc}", file=sys.stderr)
            failed.append(filename)
            continue

        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current == content:
            print(f"  same   {filename}")
            continue

        changed.append(filename)
        if args.check:
            print(f"  new    {filename}")
            continue

        target.write_text(content, encoding="utf-8")
        print(f"  update {filename}")

    if failed:
        print(f"\n{len(failed)} file(s) could not be downloaded.", file=sys.stderr)
        return 1
    if args.check:
        if changed:
            print(f"\n{len(changed)} file(s) differ from upstream.")
            return 1
        print("\nEverything is up to date.")
        return 0

    if changed:
        print(f"\nUpdated {len(changed)} file(s). Review the diff before committing.")
    else:
        print("\nEverything is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
