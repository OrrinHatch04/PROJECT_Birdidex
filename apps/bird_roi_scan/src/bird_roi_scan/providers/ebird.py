"""eBird occurrence provider stub.

API docs: https://documenter.getpostman.com/view/664302/S1ENwy59
Optional provider access reads EBIRD_API_KEY from local runtime config.
TODO: Implement using /ref/region and /data/obs/geo/recent endpoints.
TODO: eBird only exposes recent (30-day) data via the free API — note in scoring.
"""

from __future__ import annotations

from typing import Any

from bird_core.config import get_settings
from bird_data.species import SpeciesRecord

from bird_roi_scan.occurrences import NormalizedOccurrence, parse_iso_date


def parse_occurrences(records: list[dict[str, Any]]) -> list[NormalizedOccurrence]:
    """Parse eBird recent-observation records into normalised occurrences.

    eBird only exposes recent (30-day) sightings via the free API, so evidence here is
    inherently recency-biased — weight it conservatively in scoring.
    """
    out: list[NormalizedOccurrence] = []
    for rec in records:
        lat = rec.get("lat")
        lon = rec.get("lng")
        out.append(
            NormalizedOccurrence(
                source="ebird",
                source_record_id=str(
                    rec.get("subId") or rec.get("obsId") or rec.get("speciesCode") or ""
                ),
                scientific_name=str(rec.get("sciName") or ""),
                common_name=rec.get("comName"),
                latitude=float(lat) if isinstance(lat, (int, float)) else None,
                longitude=float(lon) if isinstance(lon, (int, float)) else None,
                event_date=parse_iso_date(rec.get("obsDt")),
                inside_roi=rec.get("inside_roi"),
                captive_or_cultivated=None,
            )
        )
    return out


class EBirdProvider:
    name: str = "ebird"

    def fetch_occurrences(
        self,
        species: SpeciesRecord,
        roi_wkt: str,
        max_records: int = 500,
    ) -> list[dict[str, object]]:
        """TODO: Call eBird /data/obs/geo/recent with lat/lng bbox derived from roi_wkt."""
        settings = get_settings()
        if not settings.ebird_api_key:
            raise RuntimeError(
                "EBIRD_API_KEY is not configured - set it in local .env if using eBird"
            )
        raise NotImplementedError("EBirdProvider.fetch_occurrences not yet implemented")
