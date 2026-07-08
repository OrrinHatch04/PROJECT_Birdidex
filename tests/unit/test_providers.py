from __future__ import annotations

from birdidex.providers import fetch_inaturalist, validate_metadata_records
from birdidex.taxonomy import TaxonClass


class MockResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class MockClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs: object) -> MockResponse:
        self.calls.append((url, kwargs))
        return MockResponse(self.payload)


def test_inaturalist_provider_normalization_with_mocked_response() -> None:
    taxon = TaxonClass(
        class_id=3,
        label="laughing_kookaburra",
        common_name="Laughing Kookaburra",
        scientific_name="Dacelo novaeguineae",
    )
    payload = {
        "results": [
            {
                "id": 10,
                "uri": "https://www.inaturalist.org/observations/10",
                "observed_on": "2026-02-03",
                "location": "-27.1,153.1",
                "taxon": {
                    "name": "Dacelo novaeguineae",
                    "preferred_common_name": "Laughing Kookaburra",
                },
                "photos": [
                    {
                        "id": 20,
                        "url": "https://static.inaturalist.org/photo.jpg",
                        "license_code": "CC-BY",
                        "attribution": "Example Person",
                        "original_dimensions": {"width": 1024, "height": 768},
                    }
                ],
            }
        ]
    }
    client = MockClient(payload)

    records = fetch_inaturalist(taxon, client=client, live=True, limit=1)
    validated = validate_metadata_records(records, class_lookup={taxon.class_id: taxon})

    assert client.calls
    assert len(validated) == 1
    assert validated[0].provider == "inaturalist"
    assert validated[0].provider_record_id == "10:20"
    assert validated[0].license_code == "cc-by"
    assert validated[0].status == "accepted"
    assert validated[0].latitude == -27.1


def test_validation_rejects_unknown_license_and_missing_url() -> None:
    taxon = TaxonClass(
        class_id=4,
        label="mystery_bird",
        common_name="Mystery Bird",
        scientific_name="Aves example",
    )
    payload = {
        "results": [
            {
                "id": 10,
                "taxon": {"name": "Aves example"},
                "photos": [{"id": 20, "license_code": None}],
            }
        ]
    }

    records = fetch_inaturalist(taxon, client=MockClient(payload), live=True)
    validated = validate_metadata_records(records, class_lookup={taxon.class_id: taxon})

    assert validated[0].status == "quarantine"
    assert set(validated[0].validation_issues) == {
        "missing_image_url",
        "missing_or_unknown_license",
    }
