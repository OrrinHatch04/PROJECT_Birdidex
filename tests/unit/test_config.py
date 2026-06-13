"""test_config.py — verify config files exist and YAML is parseable."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


YAML_CONFIGS = [
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


@pytest.mark.parametrize("rel_path", YAML_CONFIGS)
def test_config_exists(rel_path: str) -> None:
    assert (REPO_ROOT / rel_path).exists(), f"Missing config: {rel_path}"


@pytest.mark.parametrize("rel_path", YAML_CONFIGS)
def test_config_is_valid_yaml(rel_path: str) -> None:
    pytest.importorskip("yaml")
    import yaml

    path = REPO_ROOT / rel_path
    with path.open() as fh:
        data = yaml.safe_load(fh)
    assert data is not None, f"Empty config: {rel_path}"


def test_roi_geojson_exists() -> None:
    path = REPO_ROOT / "configs/roi/roi.example.geojson"
    assert path.exists()


def test_roi_geojson_valid() -> None:
    import json

    path = REPO_ROOT / "configs/roi/roi.example.geojson"
    with path.open() as fh:
        data = json.load(fh)
    assert data.get("type") in ("Feature", "FeatureCollection", "Polygon", "MultiPolygon")


def test_env_example_exists() -> None:
    assert (REPO_ROOT / ".env.example").exists()


def test_python_version_file() -> None:
    pv = REPO_ROOT / ".python-version"
    assert pv.exists()
    content = pv.read_text().strip()
    assert content == "3.11", f"Expected '3.11', got '{content}'"
