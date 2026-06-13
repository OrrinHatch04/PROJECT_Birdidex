"""test_imports.py — verify all internal packages are importable."""

from __future__ import annotations

import importlib

import pytest

PACKAGES = [
    "bird_core",
    "bird_core.ids",
    "bird_core.schemas",
    "bird_core.paths",
    "bird_core.config",
    "bird_core.logging",
    "bird_geo",
    "bird_geo.roi",
    "bird_geo.geometry",
    "bird_geo.places",
    "bird_data",
    "bird_data.species",
    "bird_data.manifests",
    "bird_data.taxonomy",
    "bird_data.storage",
    "bird_ml",
    "bird_ml.labels",
    "bird_ml.metrics",
    "bird_ml.calibration",
    "bird_ml.transforms",
    "bird_device",
    "bird_device.battery",
    "bird_device.camera_base",
    "bird_device.telemetry",
    "bird_scanner",
    "bird_scanner.cli",
    "bird_scanner.pipeline",
    "bird_scanner.providers",
    "bird_scanner.providers.base",
    "bird_scanner.providers.ala",
    "bird_scanner.providers.gbif",
    "bird_scanner.providers.ebird",
    "bird_scanner.providers.inaturalist",
    "bird_scanner.providers.web_search",
    "bird_training",
    "bird_ui",
]


@pytest.mark.parametrize("module_name", PACKAGES)
def test_importable(module_name: str) -> None:
    """Each internal module must import without error."""
    mod = importlib.import_module(module_name)
    assert mod is not None
