"""Atlas of Living Australia (ALA) occurrence provider stub.

API docs: https://api.ala.org.au/
Rate limit: 1 req/s (no auth required for occurrence search).
TODO: Implement fetch_occurrences() using httpx + tenacity retry.
TODO: Map ALA occurrence fields to the shared occurrence schema.
"""

from __future__ import annotations

from typing import Any

from bird_data.species import SpeciesRecord

from bird_roi_scan.occurrences import NormalizedOccurrence, parse_iso_date

ALA_BASE_URL = "https://api.ala.org.au"


def parse_occurrences(records: list[dict[str, Any]]) -> list[NormalizedOccurrence]:
    """Parse ALA occurrence-search records into normalised occurrences.

    ALA uses DarwinCore-style camelCase fields. ``establishmentMeans`` values such as
    "cultivated" / "managed" mark captive records.
    """
    out: list[NormalizedOccurrence] = []
    for rec in records:
        establishment = str(rec.get("establishmentMeans") or "").lower()
        captive = establishment in {"cultivated", "managed", "captive"}
        out.append(
            NormalizedOccurrence(
                source="ala",
                source_record_id=str(rec.get("uuid") or rec.get("id") or ""),
                scientific_name=str(rec.get("scientificName") or ""),
                common_name=rec.get("vernacularName"),
                latitude=_as_float(rec.get("decimalLatitude")),
                longitude=_as_float(rec.get("decimalLongitude")),
                event_date=parse_iso_date(rec.get("eventDate")),
                inside_roi=rec.get("inside_roi"),
                captive_or_cultivated=captive or None,
            )
        )
    return out


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class ALAProvider:
    name: str = "ala"

    def fetch_occurrences(
        self,
        species: SpeciesRecord,
        roi_wkt: str,
        max_records: int = 500,
    ) -> list[dict[str, object]]:
        """TODO: POST to ALA occurrence search with WKT filter."""
        raise NotImplementedError("ALAProvider.fetch_occurrences not yet implemented")
