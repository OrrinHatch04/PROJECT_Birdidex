#!/usr/bin/env python3
"""verify_stack.py — smoke-test the birdidex Python environment.

Run with:  python scripts/setup/verify_stack.py
Or:        make verify-stack

Exits 0 on success, non-zero if any critical check fails.
Does NOT make network calls or read large data files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

failures: list[str] = []
warnings: list[str] = []


def check(label: str, condition: bool, critical: bool = True) -> None:
    if condition:
        print(f"{PASS} {label}")
    else:
        marker = FAIL if critical else WARN
        print(f"{marker} {label}")
        if critical:
            failures.append(label)
        else:
            warnings.append(label)


# ── Python version ──────────────────────────────────────────────────────────
print("\n=== Python ===")
ver = sys.version_info
print(f"  Python {ver.major}.{ver.minor}.{ver.micro}")
check("Python 3.11.x", ver.major == 3 and ver.minor == 11)

# ── Standard library ────────────────────────────────────────────────────────
print("\n=== Standard library ===")
for mod in ["pathlib", "json", "typing", "dataclasses", "enum"]:
    try:
        __import__(mod)
        check(f"import {mod}", True)
    except ImportError:
        check(f"import {mod}", False)

# ── Core third-party packages ────────────────────────────────────────────────
print("\n=== Core third-party packages ===")
core_packages = [
    ("pydantic", "pydantic"),
    ("pydantic_settings", "pydantic-settings"),
    ("typer", "typer"),
    ("rich", "rich"),
    ("httpx", "httpx"),
    ("tenacity", "tenacity"),
    ("orjson", "orjson"),
    ("dotenv", "python-dotenv"),
    ("yaml", "pyyaml"),
]
for mod, pkg in core_packages:
    try:
        __import__(mod)
        check(f"import {mod} ({pkg})", True)
    except ImportError:
        check(f"import {mod} ({pkg})", False)

# ── Project packages ─────────────────────────────────────────────────────────
print("\n=== Project packages ===")

# Add package src dirs to path for uninstalled packages
for pkg_dir in (REPO_ROOT / "packages").iterdir():
    src = pkg_dir / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
for app_dir in (REPO_ROOT / "apps").iterdir():
    src = app_dir / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))

project_packages = [
    "bird_core",
    "bird_core.ids",
    "bird_core.schemas",
    "bird_core.paths",
    "bird_core.config",
    "bird_geo",
    "bird_geo.roi",
    "bird_data",
    "bird_data.species",
    "bird_data.manifests",
    "bird_ml",
    "bird_device",
    "bird_scanner",
    "bird_scanner.providers.base",
]
for mod in project_packages:
    try:
        __import__(mod)
        check(f"import {mod}", True)
    except ImportError as e:
        check(f"import {mod} — {e}", False)

# ── Config files ──────────────────────────────────────────────────────────────
print("\n=== Config files ===")
config_files = [
    REPO_ROOT / "configs/roi/roi.yaml",
    REPO_ROOT / "configs/roi/roi.example.geojson",
    REPO_ROOT / "configs/scanner/providers.yaml",
    REPO_ROOT / "configs/scanner/scoring.yaml",
    REPO_ROOT / ".env.example",
    REPO_ROOT / ".python-version",
    REPO_ROOT / "pyproject.toml",
]
for path in config_files:
    check(f"exists: {path.relative_to(REPO_ROOT)}", path.exists())

# ── Sample ROI loads ──────────────────────────────────────────────────────────
print("\n=== ROI geometry ===")
sample_roi = REPO_ROOT / "tests/fixtures/sample_roi.geojson"
check("fixture sample_roi.geojson exists", sample_roi.exists())
if sample_roi.exists():
    try:
        from bird_geo.roi import load_roi_geojson
        data = load_roi_geojson(sample_roi)
        check("load_roi_geojson returns dict", isinstance(data, dict))
        check("GeoJSON has 'type' key", "type" in data)
    except Exception as e:
        check(f"load_roi_geojson — {e}", False)

    try:
        from bird_geo.roi import export_roi_wkt
        wkt = export_roi_wkt(sample_roi)
        check("export_roi_wkt returns string", isinstance(wkt, str))
        check("WKT starts with POLYGON", wkt.upper().startswith("POLYGON"), critical=False)
    except ImportError:
        check("export_roi_wkt (shapely not available)", False, critical=False)
        warnings.append("shapely not installed — install scanner group for full ROI tests")
    except Exception as e:
        check(f"export_roi_wkt — {e}", False)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 50)
if failures:
    print(f"{FAIL} {len(failures)} critical failure(s):")
    for f in failures:
        print(f"       • {f}")
if warnings:
    print(f"{WARN} {len(warnings)} warning(s):")
    for w in warnings:
        print(f"       • {w}")
if not failures:
    print(f"{PASS} All critical checks passed.")

sys.exit(1 if failures else 0)
