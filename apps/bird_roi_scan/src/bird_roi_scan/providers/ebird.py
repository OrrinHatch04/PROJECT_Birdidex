"""eBird occurrence provider stub.

API docs: https://documenter.getpostman.com/view/664302/S1ENwy59
Requires: EBIRD_API_KEY environment variable.
TODO: Implement using /ref/region and /data/obs/geo/recent endpoints.
TODO: eBird only exposes recent (30-day) data via the free API — note in scoring.
"""

from __future__ import annotations

from bird_data.species import SpeciesRecord
from bird_core.config import get_settings


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
            raise RuntimeError("EBIRD_API_KEY is not configured — set it in .env")
        raise NotImplementedError("EBirdProvider.fetch_occurrences not yet implemented")
