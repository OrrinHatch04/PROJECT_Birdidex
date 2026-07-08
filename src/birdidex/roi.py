"""ROI GeoJSON loading and shapely geometry helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_roi_geojson(path: Path) -> dict[str, Any]:
    """Load a GeoJSON file and return its parsed dict."""
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)  # type: ignore[no-any-return]


def load_roi_shape(path: Path) -> Any:
    """Return a shapely geometry from a GeoJSON file.

    Requires shapely. Raises ImportError if shapely is not installed.
    """
    try:
        from shapely.geometry import shape
    except ImportError as exc:
        raise ImportError(
            "shapely is required for load_roi_shape — install the 'scanner' group"
        ) from exc

    data = load_roi_geojson(path)
    # Support FeatureCollection, Feature, or bare geometry
    if data.get("type") == "FeatureCollection":
        features = data["features"]
        if not features:
            raise ValueError(f"GeoJSON at {path} has no features")
        geom_data = features[0]["geometry"]
    elif data.get("type") == "Feature":
        geom_data = data["geometry"]
    else:
        geom_data = data
    return shape(geom_data)


def export_roi_wkt(path: Path) -> str:
    """Return the WKT string for the first geometry in a GeoJSON file."""
    geom = load_roi_shape(path)
    return str(geom.wkt)
