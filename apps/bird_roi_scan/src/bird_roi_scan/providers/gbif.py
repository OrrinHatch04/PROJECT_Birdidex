"""GBIF occurrence provider stub.

API docs: https://www.gbif.org/developer/occurrence
Rate limit: 1 req/s (anonymous).
TODO: Implement fetch_occurrences() using httpx + tenacity retry.
TODO: Map GBIF DarwinCore fields to the shared occurrence schema.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from bird_data.species import SpeciesRecord

from bird_roi_scan.occurrences import NormalizedOccurrence, parse_iso_date

GBIF_BASE_URL = "https://api.gbif.org/v1"


def parse_occurrences(records: list[dict[str, Any]]) -> list[NormalizedOccurrence]:
    """Parse GBIF occurrence-search records into normalised occurrences.

    GBIF may provide either an ``eventDate`` string or separate year/month/day ints.
    ``basisOfRecord == "LIVING_SPECIMEN"`` marks captive/cultivated records.
    """
    out: list[NormalizedOccurrence] = []
    for rec in records:
        event_date = parse_iso_date(rec.get("eventDate"))
        if event_date is None and rec.get("year"):
            try:
                event_date = date(
                    int(rec["year"]), int(rec.get("month") or 1), int(rec.get("day") or 1)
                )
            except (ValueError, TypeError):
                event_date = None
        basis = str(rec.get("basisOfRecord") or "").upper()
        captive = basis == "LIVING_SPECIMEN"
        out.append(
            NormalizedOccurrence(
                source="gbif",
                source_record_id=str(rec.get("key") or rec.get("gbifID") or ""),
                scientific_name=str(rec.get("scientificName") or rec.get("species") or ""),
                common_name=rec.get("vernacularName"),
                latitude=_as_float(rec.get("decimalLatitude")),
                longitude=_as_float(rec.get("decimalLongitude")),
                event_date=event_date,
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


class GBIFProvider:
    name: str = "gbif"

    def fetch_occurrences(
        self,
        species: SpeciesRecord,
        roi_wkt: str,
        max_records: int = 500,
    ) -> list[dict[str, object]]:
        """TODO: GET /occurrence/search with geometry and taxonKey params."""
        raise NotImplementedError("GBIFProvider.fetch_occurrences not yet implemented")
