"""PROTOTYPE regional rarity scaffold — NOT a biological abundance model.

Read this before trusting any number here
------------------------------------------
* This is a **prototype** rarity score.
* It is computed **only** from the eBird CSVs currently loaded into this prototype.
* It is **not** a true abundance or occurrence-probability model.
* It **must not** be treated as biological truth or used for conservation claims.
* A species can look "rare" here simply because we have few checklists for its region,
  not because it is actually uncommon.

Later this must incorporate: broader ROI scans (eBird API / GBIF / iNat / web sources),
seasonality, survey effort (duration, distance), checklist completeness
(``ALL SPECIES REPORTED``), and a location radius. See the TODOs below and in
``bird_data.region_presence``.

Role in BIRDIDEX
----------------
Given the per-region presence table, this produces a conservative placeholder score per
(region, species) and a rarity scaffold JSON pairing "known regions per species" with
"expected species per region" — the seed of the Pokemon-style regional encounter check.
"""

from __future__ import annotations

from dataclasses import dataclass

from bird_data.region_presence import RegionSpecies, build_species_region_summary


@dataclass
class RarityRecord:
    region: str
    label: str
    observation_count: int
    species_region_count: int  # how many regions this species appears in (loaded set)
    total_region_count: int
    rarity_score: float


def compute_region_rarity_score(
    observation_count: int,
    species_region_count: int,
    total_region_count: int,
) -> float:
    """Prototype rarity score in ``[0.0, 1.0]``.

    Higher means *more regionally unusual within the currently loaded CSV set*. Two crude
    signals, blended: how few regions the species occupies (region scarcity) and how few
    individuals were seen (count scarcity).

    TODO(roi-rarity): replace with an effort-aware ROI rarity model that compares against
    a broad SEQ species pool, weights by season and survey effort, and normalises by
    checklist count rather than raw observation totals.
    """
    total = max(total_region_count, 1)
    region_scarcity = 1.0 - (species_region_count / total)  # in a single region -> high
    count_scarcity = 1.0 / (1.0 + max(observation_count, 0))  # few birds -> high
    score = 0.6 * region_scarcity + 0.4 * count_scarcity
    return round(max(0.0, min(1.0, score)), 4)


def build_rarity_scaffold(presence: list[RegionSpecies]) -> dict:
    """Build the rarity scaffold: per-(region, species) scores + presence cross-index.

    Returns a JSON-friendly dict::

        {
          "disclaimer": "...prototype, not biological truth...",
          "total_region_count": N,
          "species_to_regions": {...},   # known regions per species
          "region_to_species":  {...},   # expected species per region
          "scores": [ {region, label, observation_count, ..., rarity_score}, ... ],
        }
    """
    summary = build_species_region_summary(presence)
    species_to_regions = summary["species_to_regions"]
    total_region_count = len(summary["region_to_species"])

    scores: list[RarityRecord] = []
    for rs in presence:
        species_region_count = len(species_to_regions.get(rs.label, [rs.region]))
        scores.append(
            RarityRecord(
                region=rs.region,
                label=rs.label,
                observation_count=rs.observation_count,
                species_region_count=species_region_count,
                total_region_count=total_region_count,
                rarity_score=compute_region_rarity_score(
                    rs.observation_count, species_region_count, total_region_count
                ),
            )
        )
    scores.sort(key=lambda r: (-r.rarity_score, r.region, r.label))

    return {
        "disclaimer": (
            "PROTOTYPE rarity — derived only from the supplied eBird CSVs. Not a biological "
            "abundance model; do not treat as truth. TODO: effort/season/ROI-aware model."
        ),
        "total_region_count": total_region_count,
        "species_to_regions": species_to_regions,
        "region_to_species": summary["region_to_species"],
        "scores": [
            {
                "region": r.region,
                "label": r.label,
                "observation_count": r.observation_count,
                "species_region_count": r.species_region_count,
                "total_region_count": r.total_region_count,
                "rarity_score": r.rarity_score,
            }
            for r in scores
        ],
    }
