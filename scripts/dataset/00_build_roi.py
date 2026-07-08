#!/usr/bin/env python3
"""00_build_roi.py — Validate and export the ROI polygon.

Reads configs/roi/roi.yaml, loads the GeoJSON, and writes:
  - data/roi/roi.wkt       (WKT string for provider geometry queries)

TODO: Add interactive visualisation once geopandas + folium are installed.
TODO: Allow user to specify a custom GeoJSON path via --roi-path argument.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages/bird_geo/src"))
sys.path.insert(0, str(REPO_ROOT / "packages/bird_core/src"))


def main() -> None:
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml not installed — run: make sync-scanner")
        sys.exit(1)

    config_path = REPO_ROOT / "configs/roi/roi.yaml"
    with config_path.open() as fh:
        roi_cfg = yaml.safe_load(fh)

    geojson_path = REPO_ROOT / roi_cfg["geojson_path"]
    print(f"ROI GeoJSON: {geojson_path}")

    from bird_geo.roi import export_roi_wkt, load_roi_geojson

    data = load_roi_geojson(geojson_path)
    print(f"GeoJSON type: {data.get('type')}")

    try:
        wkt = export_roi_wkt(geojson_path)
        out_path = REPO_ROOT / "data/roi/roi.wkt"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(wkt)
        print(f"WKT written to: {out_path}")
        print(f"WKT preview: {wkt[:120]}...")
    except ImportError:
        print("WARN: shapely not available — WKT export skipped (install scanner group)")


if __name__ == "__main__":
    main()
