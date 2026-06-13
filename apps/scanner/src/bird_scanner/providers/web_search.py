"""Web keyword search provider stub.

This provider supplies WEAK supplementary evidence only.
It must NOT scrape Google directly — plug in a legitimate search API key
(e.g. Serper, Brave Search, or SerpAPI) before calling fetch_keyword_evidence().

QUERY_TEMPLATES and ROI_TERMS are preserved from the existing bird-roi-scan/ prototype.
"""

from __future__ import annotations

from bird_data.species import SpeciesRecord
from bird_core.config import get_settings

QUERY_TEMPLATES: list[str] = [
    '"{common_name}" "{place}" bird',
    '"{scientific_name}" "{place}"',
    '"{common_name}" "{region}" Queensland',
    '"{common_name}" "South East Queensland"',
    '"{common_name}" "Darling Downs"',
    '"{common_name}" "Bundaberg"',
    '"{common_name}" "Goondiwindi"',
    '"{scientific_name}" "Queensland"',
]

BIRD_CONTEXT_TERMS: list[str] = [
    "sighting",
    "observed",
    "recorded",
    "bird list",
    "checklist",
    "ebird",
    "atlas",
    "occurrence",
    "photographed",
    "spotted at",
    "seen at",
]


class WebSearchProvider:
    name: str = "web_search"

    def fetch_keyword_evidence(
        self,
        species: SpeciesRecord,
        roi_places: list[str],
        max_results: int = 20,
    ) -> list[dict[str, object]]:
        """TODO: Call a configured search API (Serper / Brave / SerpAPI).

        Do NOT call this method without SEARCH_API_KEY configured.
        Web evidence is weak — weight it conservatively in scoring.
        """
        settings = get_settings()
        if not settings.search_api_key:
            raise RuntimeError(
                "SEARCH_API_KEY not set — configure a legitimate search API in .env"
            )
        raise NotImplementedError("WebSearchProvider.fetch_keyword_evidence not yet implemented")

    def build_queries(self, species: SpeciesRecord, places: list[str]) -> list[str]:
        """Build query strings from QUERY_TEMPLATES."""
        queries: list[str] = []
        for template in QUERY_TEMPLATES:
            for place in places:
                queries.append(
                    template.format(
                        common_name=species.common_name or "",
                        scientific_name=species.scientific_name,
                        place=place,
                        region="Queensland",
                    )
                )
        return queries
