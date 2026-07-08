from __future__ import annotations

from birdidex.providers import (
    fetch_ebird_priors,
    is_open_license,
    normalize_ebird_observations,
    resolve_ebird_region,
    resolve_ebird_species_code,
)
from birdidex.taxonomy import TaxonClass

LORIKEET = TaxonClass(
    class_id=42,
    label="rainbow_lorikeet",
    common_name="Rainbow Lorikeet",
    scientific_name="Trichoglossus moluccanus",
)

SIGHTINGS = [
    {
        "speciesCode": "rainlor3",
        "comName": "Rainbow Lorikeet",
        "sciName": "Trichoglossus moluccanus",
        "locId": "L1",
        "locName": "Park A",
        "obsDt": "2026-03-15 09:00",
        "howMany": 4,
        "lat": -27.4,
        "lng": 153.0,
        "obsValid": True,
    },
    {
        "locName": "Park B",
        "obsDt": "2026-07-02",
        "howMany": 2,
        "lat": -27.5,
        "lng": 153.1,
    },
    {"locName": "Park A", "obsDt": "2026-07-20", "howMany": 1},
]


class MockResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class MockClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs: object) -> MockResponse:
        self.calls.append((url, kwargs))
        return MockResponse(self.payload)


def test_region_alias_resolution() -> None:
    assert resolve_ebird_region("seq") == "AU-QLD"
    assert resolve_ebird_region("SEQ") == "AU-QLD"
    assert resolve_ebird_region("AU-NSW") == "AU-NSW"  # pass-through for real codes
    assert resolve_ebird_region(None) == "AU-QLD"


def test_species_code_resolution_from_taxonomy_map() -> None:
    mapping = {"trichoglossus moluccanus": "rainlor3"}
    assert resolve_ebird_species_code(LORIKEET, api_key="x", taxonomy_map=mapping) == "rainlor3"
    unknown = TaxonClass(class_id=1, label="x", common_name="X", scientific_name="No match")
    assert resolve_ebird_species_code(unknown, api_key="x", taxonomy_map=mapping) is None


def test_normalize_ebird_observations() -> None:
    prior = normalize_ebird_observations(SIGHTINGS, LORIKEET, region="seq", species_code="rainlor3")
    assert prior.provider == "ebird"
    assert prior.region == "seq"
    assert prior.region_resolved == "AU-QLD"
    assert prior.total_observations == 3
    assert prior.total_individuals == 7
    assert prior.distinct_localities == 2
    assert prior.month_histogram == {"03": 1, "07": 2}
    assert prior.first_observed_on == "2026-03-15 09:00"
    assert prior.last_observed_on == "2026-07-20"
    assert prior.top_localities[0]["loc_name"] == "Park A"
    assert prior.top_localities[0]["observations"] == 2
    assert len(prior.sample_observations) == 3


def test_normalize_ebird_handles_empty() -> None:
    prior = normalize_ebird_observations([], LORIKEET, region="seq", species_code=None)
    assert prior.total_observations == 0
    assert prior.month_histogram == {}
    assert prior.first_observed_on is None


def test_fetch_ebird_priors_uses_auth_header_and_normalizes() -> None:
    client = MockClient(SIGHTINGS)
    prior = fetch_ebird_priors(
        LORIKEET,
        region="seq",
        api_key="tok",
        client=client,
        live=True,
        taxonomy_map={"trichoglossus moluccanus": "rainlor3"},
    )
    assert prior is not None
    assert prior.total_observations == 3
    assert prior.species_code == "rainlor3"
    # exactly one live call (observations); auth header carries the token
    assert len(client.calls) == 1
    url, kwargs = client.calls[0]
    assert "AU-QLD/recent/rainlor3" in url
    assert kwargs["headers"]["X-eBirdApiToken"] == "tok"


def test_fetch_ebird_priors_not_live_returns_none() -> None:
    assert fetch_ebird_priors(LORIKEET, api_key="tok", live=False) is None


def test_open_license_allowlist() -> None:
    assert is_open_license("CC-BY")
    assert is_open_license("cc0")
    assert is_open_license("https://creativecommons.org/licenses/by-sa/4.0/")
    assert not is_open_license("all-rights-reserved")
    assert not is_open_license(None)
    assert not is_open_license("cc-by-nd")
