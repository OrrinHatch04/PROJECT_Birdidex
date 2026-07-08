"""Live provider smoke tests.

These hit the real eBird and iNaturalist APIs. They are skipped by default (a plain
``pytest`` run stays offline) and only execute with ``pytest -m live_api``. Even then,
each test skips cleanly when its required credentials are not configured.
"""

from __future__ import annotations

import pytest

from birdidex.providers import fetch_ebird_priors, fetch_inaturalist, validate_metadata_records
from birdidex.secrets import get_ebird_api_key, get_inaturalist_access_token
from birdidex.taxonomy import TaxonClass

pytestmark = pytest.mark.live_api

LORIKEET = TaxonClass(
    class_id=0,
    label="rainbow_lorikeet",
    common_name="Rainbow Lorikeet",
    scientific_name="Trichoglossus moluccanus",
)


def test_live_ebird_priors() -> None:
    key = get_ebird_api_key()
    if not key:
        pytest.skip("EBIRD_API_KEY not configured")
    prior = fetch_ebird_priors(LORIKEET, region="seq", api_key=key, live=True)
    assert prior is not None
    assert prior.region_resolved == "AU-QLD"
    assert prior.total_observations >= 0


def test_live_inaturalist_photos() -> None:
    # Public endpoint; token optional. Still gated to the live marker for network use.
    token = get_inaturalist_access_token()
    records = fetch_inaturalist(LORIKEET, live=True, limit=5, access_token=token)
    validated = validate_metadata_records(records, class_lookup={LORIKEET.class_id: LORIKEET})
    accepted = [r for r in validated if r.status == "accepted"]
    # We should get at least some open-license photos for a common species.
    assert all(r.image_url for r in accepted)
