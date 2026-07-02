"""Shared Protocol interfaces for occurrence and keyword evidence providers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bird_data.manifests import ImageManifestRecord
from bird_data.species import SpeciesRecord


@runtime_checkable
class OccurrenceProviderProtocol(Protocol):
    """Returns structured occurrence records for a species within an ROI WKT."""

    name: str

    def fetch_occurrences(
        self,
        species: SpeciesRecord,
        roi_wkt: str,
        max_records: int = 500,
    ) -> list[dict[str, object]]:
        """Fetch raw occurrence dicts from the provider API.

        Returns a list of raw dicts — the pipeline normalises them downstream.
        TODO: Return typed OccurrenceRecord objects once that model is finalised.
        """
        ...


@runtime_checkable
class KeywordProviderProtocol(Protocol):
    """Returns keyword evidence records for a species in an ROI."""

    name: str

    def fetch_keyword_evidence(
        self,
        species: SpeciesRecord,
        roi_places: list[str],
        max_results: int = 20,
    ) -> list[dict[str, object]]:
        """Fetch raw keyword evidence dicts.

        TODO: Return typed EvidenceRecord objects once model is finalised.
        """
        ...
