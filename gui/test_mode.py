"""Small helpers for development-only UI features."""

from __future__ import annotations

import os

_TRUE_VALUES = {"1", "true", "yes", "on"}


def test_mode_enabled() -> bool:
    """Return whether the ``TEST`` environment flag is enabled."""
    return os.environ.get("TEST", "").strip().lower() in _TRUE_VALUES
