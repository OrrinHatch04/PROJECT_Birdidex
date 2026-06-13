"""test_roi.py — verify sample ROI loading and WKT export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_ROI = REPO_ROOT / "tests/fixtures/sample_roi.geojson"


def test_sample_roi_fixture_exists() -> None:
    assert SAMPLE_ROI.exists()


def test_sample_roi_is_valid_geojson() -> None:
    with SAMPLE_ROI.open() as fh:
        data = json.load(fh)
    assert data["type"] == "Feature"
    assert data["geometry"]["type"] == "Polygon"
    coords = data["geometry"]["coordinates"]
    assert len(coords) == 1
    assert len(coords[0]) >= 4


def test_load_roi_geojson() -> None:
    from bird_geo.roi import load_roi_geojson

    data = load_roi_geojson(SAMPLE_ROI)
    assert isinstance(data, dict)
    assert "type" in data


def test_export_roi_wkt_requires_shapely() -> None:
    """export_roi_wkt should succeed if shapely is installed, or raise ImportError if not."""
    from bird_geo.roi import export_roi_wkt

    try:
        wkt = export_roi_wkt(SAMPLE_ROI)
        assert isinstance(wkt, str)
        assert len(wkt) > 10
        upper = wkt.upper()
        assert "POLYGON" in upper, f"Expected POLYGON in WKT, got: {wkt[:80]}"
    except ImportError:
        pytest.skip("shapely not installed — skipping WKT test")


def test_example_geojson_polygon() -> None:
    """The placeholder ROI GeoJSON must be a valid Feature with a Polygon geometry."""
    example = REPO_ROOT / "configs/roi/roi.example.geojson"
    with example.open() as fh:
        data = json.load(fh)
    assert data["type"] == "Feature"
    assert data["geometry"]["type"] == "Polygon"
