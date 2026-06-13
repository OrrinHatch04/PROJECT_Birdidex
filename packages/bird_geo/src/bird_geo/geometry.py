"""Utility helpers for coordinate transforms and spatial predicates."""

from __future__ import annotations

from typing import Any


def point_in_shape(lat: float, lon: float, shape: Any) -> bool:
    """Return True if (lat, lon) falls inside a shapely geometry.

    TODO: add CRS reprojection via pyproj when source data uses non-WGS84 CRS.
    """
    try:
        from shapely.geometry import Point
    except ImportError as exc:
        raise ImportError("shapely required — install the 'scanner' group") from exc
    return bool(shape.contains(Point(lon, lat)))


def bbox_of_shape(shape: Any) -> tuple[float, float, float, float]:
    """Return (min_lon, min_lat, max_lon, max_lat) bounding box."""
    return tuple(shape.bounds)  # type: ignore[return-value]
