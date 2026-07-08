"""iNaturalist occurrence provider stub.

API docs: https://api.inaturalist.org/v2
Rate limit: ~1 req/s (anonymous), more with OAuth.
TODO: Implement using /observations endpoint with geo_json param.
TODO: Filter to research-grade observations only.
"""

from __future__ import annotations

from typing import Any

from bird_data.species import SpeciesRecord

from bird_roi_scan.occurrences import NormalizedOccurrence, parse_iso_date

INAT_BASE_URL = "https://api.inaturalist.org/v2"


def parse_occurrences(records: list[dict[str, Any]]) -> list[NormalizedOccurrence]:
    """Parse iNaturalist observation records into normalised occurrences.

    Location arrives as a ``"lat,lon"`` string; ``captive`` marks non-wild records.
    """
    out: list[NormalizedOccurrence] = []
    for rec in records:
        taxon = rec.get("taxon") or {}
        lat = lon = None
        loc = rec.get("location")
        if isinstance(loc, str) and "," in loc:
            try:
                lat_s, lon_s = loc.split(",", 1)
                lat, lon = float(lat_s), float(lon_s)
            except ValueError:
                lat = lon = None
        out.append(
            NormalizedOccurrence(
                source="inaturalist",
                source_record_id=str(rec.get("id") or ""),
                scientific_name=str(taxon.get("name") or rec.get("scientific_name") or ""),
                common_name=taxon.get("preferred_common_name") or rec.get("common_name"),
                latitude=lat,
                longitude=lon,
                event_date=parse_iso_date(rec.get("observed_on")),
                inside_roi=rec.get("inside_roi"),
                captive_or_cultivated=(
                    bool(rec["captive"]) if rec.get("captive") is not None else None
                ),
            )
        )
    return out


class INaturalistProvider:
    name: str = "inaturalist"

    def fetch_occurrences(
        self,
        species: SpeciesRecord,
        roi_wkt: str,
        max_records: int = 500,
    ) -> list[dict[str, object]]:
        """TODO: GET /observations with taxon_name and place_id (SEQ polygon)."""
        raise NotImplementedError("INaturalistProvider.fetch_occurrences not yet implemented")
