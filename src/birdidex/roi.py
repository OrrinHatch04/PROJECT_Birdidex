"""ROI GeoJSON loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_roi_geojson(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"GeoJSON at {path} must be an object")
    return data


def load_roi_shape(path: Path) -> Any:
    """Return a shapely geometry from a GeoJSON file."""
    try:
        from shapely.geometry import shape
    except ImportError as exc:
        raise ImportError("shapely is required; sync the scanner dependency group") from exc

    data = load_roi_geojson(path)
    if data.get("type") == "FeatureCollection":
        features = data.get("features") or []
        if not features:
            raise ValueError(f"GeoJSON at {path} has no features")
        geometry = features[0]["geometry"]
    elif data.get("type") == "Feature":
        geometry = data["geometry"]
    else:
        geometry = data
    return shape(geometry)


def export_roi_wkt(path: Path) -> str:
    return str(load_roi_shape(path).wkt)
