"""Pytest configuration: add all package src dirs to sys.path for uninstalled packages."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Register package src dirs so tests work without `uv sync` or editable installs.
_src_dirs = [
    REPO_ROOT / "packages/bird_core/src",
    REPO_ROOT / "packages/bird_geo/src",
    REPO_ROOT / "packages/bird_data/src",
    REPO_ROOT / "packages/bird_ml/src",
    REPO_ROOT / "packages/bird_device/src",
    REPO_ROOT / "apps/scanner/src",
    REPO_ROOT / "apps/training/src",
    REPO_ROOT / "apps/inference/src",
    REPO_ROOT / "apps/cyberdeck_ui/src",
]
for p in _src_dirs:
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
