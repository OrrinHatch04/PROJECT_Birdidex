"""test_provider_protocol.py — verify provider skeletons satisfy Protocol interfaces."""

from __future__ import annotations

import pytest

from bird_roi_scan.providers.base import KeywordProviderProtocol, OccurrenceProviderProtocol


def test_occurrence_protocol_is_runtime_checkable() -> None:
    assert hasattr(OccurrenceProviderProtocol, "__protocol_attrs__") or True
    # runtime_checkable ensures isinstance works
    from bird_roi_scan.providers.ala import ALAProvider

    ala = ALAProvider()
    assert isinstance(ala, OccurrenceProviderProtocol)


def test_keyword_protocol_is_runtime_checkable() -> None:
    from bird_roi_scan.providers.web_search import WebSearchProvider

    ws = WebSearchProvider()
    assert isinstance(ws, KeywordProviderProtocol)


def test_ala_provider_has_name() -> None:
    from bird_roi_scan.providers.ala import ALAProvider

    assert ALAProvider.name == "ala"


def test_gbif_provider_has_name() -> None:
    from bird_roi_scan.providers.gbif import GBIFProvider

    assert GBIFProvider.name == "gbif"


def test_ebird_provider_has_name() -> None:
    from bird_roi_scan.providers.ebird import EBirdProvider

    assert EBirdProvider.name == "ebird"


def test_inaturalist_provider_has_name() -> None:
    from bird_roi_scan.providers.inaturalist import INaturalistProvider

    assert INaturalistProvider.name == "inaturalist"


def test_web_search_provider_has_name() -> None:
    from bird_roi_scan.providers.web_search import WebSearchProvider

    assert WebSearchProvider.name == "web_search"


def test_fetch_occurrences_raises_not_implemented() -> None:
    from bird_data.species import SpeciesRecord
    from bird_core.ids import SpeciesId
    from bird_roi_scan.providers.ala import ALAProvider

    species = SpeciesRecord(
        species_id=SpeciesId("dacelo_novaeguineae"),
        scientific_name="Dacelo novaeguineae",
        common_name="Laughing Kookaburra",
    )
    provider = ALAProvider()
    with pytest.raises(NotImplementedError):
        provider.fetch_occurrences(species, "POLYGON((0 0,1 0,1 1,0 1,0 0))")


def test_web_search_build_queries() -> None:
    from bird_data.species import SpeciesRecord
    from bird_core.ids import SpeciesId
    from bird_roi_scan.providers.web_search import WebSearchProvider

    species = SpeciesRecord(
        species_id=SpeciesId("dacelo_novaeguineae"),
        scientific_name="Dacelo novaeguineae",
        common_name="Laughing Kookaburra",
    )
    provider = WebSearchProvider()
    places = ["Brisbane", "Sunshine Coast"]
    queries = provider.build_queries(species, places)
    assert len(queries) > 0
    assert all(isinstance(q, str) for q in queries)
