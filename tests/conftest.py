"""Pytest configuration for the single-package src layout."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip ``live_api`` tests unless explicitly selected with ``-m live_api``.

    This keeps a plain ``pytest`` run fully offline even on a developer machine that has
    provider keys configured; the live tests only run when opted into.
    """
    markexpr = str(config.getoption("-m") or "")
    if "live_api" in markexpr:
        return
    skip_live = pytest.mark.skip(reason="live API test; run with -m live_api")
    for item in items:
        if "live_api" in item.keywords:
            item.add_marker(skip_live)
