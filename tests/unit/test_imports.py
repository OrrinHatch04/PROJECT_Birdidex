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
    "bird_roi_scan",
    "bird_roi_scan.cli",
    "bird_roi_scan.pipeline",
    "bird_roi_scan.providers",
    "bird_roi_scan.providers.base",
    "bird_roi_scan.providers.ala",
    "bird_roi_scan.providers.gbif",
    "bird_roi_scan.providers.ebird",
    "bird_roi_scan.providers.inaturalist",
    "bird_roi_scan.providers.web_search",
    "bird_training",
    "bird_training.train_classifier",
    "bird_training.train_detector",
    "bird_training.export_onnx",
    "bird_training.evaluate",
    "bird_inference",
    "bird_inference.app",
    "bird_inference.camera",
    "bird_inference.detector",
    "bird_inference.classifier",
    "bird_inference.species_db",
    "bird_ui",
    # NOTE: bird_ui.server imports fastapi at module top, so it is intentionally
    # excluded here — it is only importable once the 'ui' dependency group is synced.
]


@pytest.mark.parametrize("module_name", PACKAGES)
def test_importable(module_name: str) -> None:
    """Each internal module must import without error."""
    mod = importlib.import_module(module_name)
    assert mod is not None
