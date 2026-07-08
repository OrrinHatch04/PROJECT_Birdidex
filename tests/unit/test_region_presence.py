"""Tests for the region/species presence builder and the rarity scaffold.

Uses tiny in-memory observation rows — no real CSVs required.
"""

from __future__ import annotations

from bird_data.ebird_ingest import (
    F_COMMON_NAME,
    F_LOCALITY,
    F_OBSERVATION_COUNT,
    F_OBSERVATION_DATE,
    F_OBSERVER,
    F_SCIENTIFIC_NAME,
)
from bird_data.rarity import build_rarity_scaffold, compute_region_rarity_score
from bird_data.region_presence import (
    build_region_species_presence,
    build_species_region_summary,
    canonicalise_region,
)


def _obs(common, region, count="1", date="2025-09-01", observer="obs1", scientific="Genus species"):
    return {
        F_COMMON_NAME: common,
        F_SCIENTIFIC_NAME: scientific,
        F_LOCALITY: region,
        F_OBSERVATION_COUNT: count,
        F_OBSERVATION_DATE: date,
        F_OBSERVER: observer,
    }


def test_canonicalise_region_prefers_locality():
    assert canonicalise_region({F_LOCALITY: "Noosa Hill Track"}) == "Noosa Hill Track"
    assert canonicalise_region({}) == "unknown_region"


def test_presence_aggregates_counts_dates_and_visits():
    obs = [
        _obs("Australian Magpie", "Region A", count="2", date="2025-09-01", observer="x"),
        _obs("Australian Magpie", "Region A", count="3", date="2025-09-05", observer="y"),
    ]
    presence = build_region_species_presence(obs)
    assert len(presence) == 1
    rs = presence[0]
    assert rs.observation_count == 5
    assert rs.first_seen == "2025-09-01"
    assert rs.last_seen == "2025-09-05"
    assert rs.visit_count == 2  # two distinct date+observer visits


def test_summary_cross_indexes_species_and_regions():
    obs = [
        _obs("Magpie", "Region A", scientific="Gymnorhina tibicen"),
        _obs("Magpie", "Region B", scientific="Gymnorhina tibicen"),
        _obs("Noisy Miner", "Region A", scientific="Manorina melanocephala"),
    ]
    summary = build_species_region_summary(build_region_species_presence(obs))
    assert summary["species_to_regions"]["magpie"] == ["Region A", "Region B"]
    assert set(summary["region_to_species"]["Region A"]) == {"magpie", "noisy_miner"}


def test_missing_optional_columns_do_not_crash():
    # No date, no observer, no count -> should still aggregate.
    presence = build_region_species_presence([{F_COMMON_NAME: "Silvereye", F_LOCALITY: "Region A"}])
    assert presence[0].observation_count == 1
    assert presence[0].first_seen is None


def test_rarity_score_bounds_and_direction():
    # Single-region, few birds -> higher than ubiquitous, many birds.
    rare = compute_region_rarity_score(
        observation_count=1, species_region_count=1, total_region_count=5
    )
    common = compute_region_rarity_score(
        observation_count=50, species_region_count=5, total_region_count=5
    )
    assert 0.0 <= common <= rare <= 1.0
    assert rare > common


def test_rarity_scaffold_shape():
    obs = [_obs("Magpie", "Region A", scientific="Gymnorhina tibicen")]
    scaffold = build_rarity_scaffold(build_region_species_presence(obs))
    assert "disclaimer" in scaffold
    assert scaffold["total_region_count"] == 1
    assert scaffold["scores"][0]["label"] == "magpie"
