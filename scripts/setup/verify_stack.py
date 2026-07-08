#!/usr/bin/env python3
"""Smoke-test the simplified BIRDIDEX package.

This script performs local checks only. It does not make provider requests,
retrieve media, train models, or start services.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

failures: list[str] = []
warnings: list[str] = []


def check(label: str, condition: bool, *, critical: bool = True) -> None:
    if condition:
        print(f"{PASS} {label}")
        return
    marker = FAIL if critical else WARN
    print(f"{marker} {label}")
    (failures if critical else warnings).append(label)


def check_import(module_name: str, *, critical: bool = True) -> None:
    try:
        importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - smoke test reports any failure
        check(f"import {module_name} ({exc.__class__.__name__}: {exc})", False, critical=critical)
    else:
        check(f"import {module_name}", True)


def main() -> int:
    print("\n=== Python ===")
    version = sys.version_info
    print(f"  Python {version.major}.{version.minor}.{version.micro}")
    check("Python 3.11.x", version.major == 3 and version.minor == 11)

    print("\n=== Repo layout ===")
    check("repo root exists", REPO_ROOT.is_dir())
    for dirname in ["src", "configs", "data", "models", "notebooks", "scripts", "tests", "docs"]:
        check(f"dir exists: {dirname}/", (REPO_ROOT / dirname).is_dir())
    check("apps/ removed", not (REPO_ROOT / "apps").exists())
    check("packages/ removed", not (REPO_ROOT / "packages").exists())

    print("\n=== Package imports ===")
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))
    for module_name in [
        "birdidex",
        "birdidex.cli",
        "birdidex.paths",
        "birdidex.settings",
        "birdidex.taxonomy",
        "birdidex.roi",
        "birdidex.providers",
        "birdidex.images",
        "birdidex.splits",
        "birdidex.train",
        "birdidex.infer",
        "birdidex.db",
        "birdidex.ui",
    ]:
        check_import(module_name)

    print("\n=== Class index ===")
    class_index = REPO_ROOT / "data" / "processed" / "birddex" / "class_index.json"
    check("class_index.json exists", class_index.exists())
    if class_index.exists():
        payload = json.loads(class_index.read_text(encoding="utf-8"))
        classes = payload.get("classes")
        check("class_index has classes list", isinstance(classes, list))
        check("class_index non-empty", bool(classes))

    print("\n=== Configs ===")
    for rel in [
        "configs/roi/roi.yaml",
        "configs/scanner/providers.yaml",
        "configs/scanner/scoring.yaml",
        "configs/training/classifier.yaml",
        "configs/inference/runtime.yaml",
    ]:
        check(f"config exists: {rel}", (REPO_ROOT / rel).exists(), critical=False)

    print()
    print("=" * 60)
    if failures:
        print(f"{FAIL} {len(failures)} critical failure(s):")
        for failure in failures:
            print(f"       - {failure}")
    if warnings:
        print(f"{WARN} {len(warnings)} warning(s):")
        for warning in warnings:
            print(f"       - {warning}")
    if not failures:
        print(f"{PASS} All critical checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
