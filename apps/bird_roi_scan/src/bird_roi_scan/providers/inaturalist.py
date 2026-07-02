"""iNaturalist occurrence provider stub.

API docs: https://api.inaturalist.org/v2
Rate limit: ~1 req/s (anonymous), more with OAuth.
TODO: Implement using /observations endpoint with geo_json param.
TODO: Filter to research-grade observations only.
"""

from __future__ import annotations

from bird_data.species import SpeciesRecord

INAT_BASE_URL = "https://api.inaturalist.org/v2"


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
