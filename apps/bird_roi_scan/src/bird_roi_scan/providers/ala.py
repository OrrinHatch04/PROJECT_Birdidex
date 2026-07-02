"""Atlas of Living Australia (ALA) occurrence provider stub.

API docs: https://api.ala.org.au/
Rate limit: 1 req/s (no auth required for occurrence search).
TODO: Implement fetch_occurrences() using httpx + tenacity retry.
TODO: Map ALA occurrence fields to the shared occurrence schema.
"""

from __future__ import annotations

from bird_data.species import SpeciesRecord

ALA_BASE_URL = "https://api.ala.org.au"


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
