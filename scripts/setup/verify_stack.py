#!/usr/bin/env python3
"""verify_stack.py — smoke-test the birdidex workspace + Python environment.

Run with:  python scripts/setup/verify_stack.py
Or:        make verify-stack

Offline only - this script never makes provider requests and never reads large data files.

Checks:
  * Python is 3.11.x
  * repo root resolves and is printed
  * shared root directories exist (configs/ data/ models/ scripts/ tests/ packages/ docs/ ...)
  * app directories exist (apps/bird_roi_scan, apps/training, apps/inference, apps/cyberdeck_ui)
  * core third-party packages import
  * internal packages import (bird_core, bird_geo, bird_data, bird_ml, bird_device,
    bird_roi_scan, bird_training, bird_inference, bird_ui)
  * YAML configs parse
  * the sample ROI GeoJSON loads

Exits 0 on success, non-zero if any critical check fails.
"""

from __future__ import annotations

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
        (failures if critical else warnings).append(label)


# ── Python version ────────────────────────────────────────────────────────────
print("\n=== Python ===")
ver = sys.version_info
print(f"  Python {ver.major}.{ver.minor}.{ver.micro}")
check("Python 3.11.x", ver.major == 3 and ver.minor == 11)

# ── Repo root ─────────────────────────────────────────────────────────────────
print("\n=== Repo root ===")
print(f"  {REPO_ROOT}")
check("repo root exists", REPO_ROOT.is_dir())

# ── Shared root directories ───────────────────────────────────────────────────
print("\n=== Shared root directories ===")
for d in ["configs", "data", "models", "notebooks", "scripts", "tests", "packages", "docs"]:
    check(f"dir exists: {d}/", (REPO_ROOT / d).is_dir())

# ── App directories ───────────────────────────────────────────────────────────
print("\n=== App directories ===")
for app in ["bird_roi_scan", "training", "inference", "cyberdeck_ui", "tools"]:
    check(f"app exists: apps/{app}/", (REPO_ROOT / "apps" / app).is_dir())

# Confirm the old nested project is gone.
check("no nested bird-roi-scan/ project", not (REPO_ROOT / "bird-roi-scan").exists())

# ── Standard library ──────────────────────────────────────────────────────────
print("\n=== Standard library ===")
for mod in ["pathlib", "json", "typing", "dataclasses", "enum"]:
    try:
        __import__(mod)
        check(f"import {mod}", True)
    except ImportError:
        check(f"import {mod}", False)

# ── Core third-party packages ─────────────────────────────────────────────────
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

# ── Project packages ──────────────────────────────────────────────────────────
print("\n=== Project packages ===")

# Add package + app src dirs to path so this works without `uv sync` / editable installs.
for base in ("packages", "apps"):
    for child in sorted((REPO_ROOT / base).iterdir()):
        src = child / "src"
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
    "bird_roi_scan",
    "bird_roi_scan.providers.base",
    "bird_training",
    "bird_inference",
    "bird_ui",  # package root only — bird_ui.server needs the 'ui' group (fastapi)
]
for mod in project_packages:
    try:
        __import__(mod)
        check(f"import {mod}", True)
    except ImportError as e:
        check(f"import {mod} — {e}", False)

# ── Path helpers resolve relative to repo root ────────────────────────────────
print("\n=== Path helpers (bird_core.paths) ===")
try:
    from bird_core.paths import get_app_dir, get_configs_dir, get_repo_root

    check("get_repo_root() == verify_stack REPO_ROOT", get_repo_root() == REPO_ROOT)
    check("get_configs_dir() resolves", get_configs_dir() == REPO_ROOT / "configs")
    check(
        "get_app_dir('bird_roi_scan') resolves",
        get_app_dir("bird_roi_scan") == REPO_ROOT / "apps" / "bird_roi_scan",
    )
except Exception as e:  # noqa: BLE001 - smoke test reports any failure
    check(f"bird_core.paths helpers — {e}", False)

# ── YAML configs parse ────────────────────────────────────────────────────────
print("\n=== Config files (YAML parse) ===")
yaml_configs = [
    "configs/roi/roi.yaml",
    "configs/scanner/providers.yaml",
    "configs/scanner/scoring.yaml",
    "configs/scanner/species_filters.yaml",
    "configs/training/classifier.yaml",
    "configs/training/detector.yaml",
    "configs/training/augmentation.yaml",
    "configs/inference/runtime.yaml",
    "configs/device/cyberdeck.yaml",
]
try:
    import yaml

    for rel in yaml_configs:
        path = REPO_ROOT / rel
        if not path.exists():
            check(f"exists: {rel}", False)
            continue
        try:
            data = yaml.safe_load(path.read_text())
            check(f"parse: {rel}", True)
            check(f"non-empty: {rel}", data is not None, critical=False)
        except yaml.YAMLError as e:
            check(f"parse: {rel} — {e}", False)
except ImportError:
    check("pyyaml available for config parsing", False, critical=False)
    warnings.append("pyyaml not installed — install dev/scanner group to parse configs")

# ── Sample ROI GeoJSON loads ──────────────────────────────────────────────────
print("\n=== ROI geometry ===")
sample_roi = REPO_ROOT / "tests/fixtures/sample_roi.geojson"
check("fixture sample_roi.geojson exists", sample_roi.exists())
example_roi = REPO_ROOT / "configs/roi/roi.example.geojson"
check("configs/roi/roi.example.geojson exists", example_roi.exists())
if sample_roi.exists():
    try:
        from bird_geo.roi import load_roi_geojson

        data = load_roi_geojson(sample_roi)
        check("load_roi_geojson returns dict", isinstance(data, dict))
        check("GeoJSON has 'type' key", "type" in data)
    except Exception as e:  # noqa: BLE001 - smoke test reports any failure
        check(f"load_roi_geojson — {e}", False)

    try:
        from bird_geo.roi import export_roi_wkt

        wkt = export_roi_wkt(sample_roi)
        check("export_roi_wkt returns string", isinstance(wkt, str))
        check("WKT starts with POLYGON", wkt.upper().startswith("POLYGON"), critical=False)
    except ImportError:
        check("export_roi_wkt (shapely not installed)", False, critical=False)
        warnings.append("shapely not installed — install the 'scanner' group for full ROI tests")
    except Exception as e:  # noqa: BLE001 - smoke test reports any failure
        check(f"export_roi_wkt — {e}", False)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
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
