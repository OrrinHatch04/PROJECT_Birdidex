"""GBIF occurrence provider stub.

API docs: https://www.gbif.org/developer/occurrence
Rate limit: 1 req/s (anonymous).
TODO: Implement fetch_occurrences() using httpx + tenacity retry.
TODO: Map GBIF DarwinCore fields to the shared occurrence schema.
"""

from __future__ import annotations

from bird_data.species import SpeciesRecord

GBIF_BASE_URL = "https://api.gbif.org/v1"


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
