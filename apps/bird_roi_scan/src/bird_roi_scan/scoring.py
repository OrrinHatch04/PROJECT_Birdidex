"""Score ROI species candidates from aggregated evidence.

The final score is a weighted blend of five interpretable components, each normalised
to ``[0, 1]``:

* **occurrence** — log-scaled, source-weighted total occurrence count.
* **source_agreement** — fraction of configured providers that reported the species.
* **recency** — coverage of the most recent years.
* **roi_match** — fraction of records falling inside the ROI.
* **seasonal** — breadth of months with evidence.

Species with a manual-review flag or thin evidence are routed to the ``review`` tier
rather than silently accepted or rejected, so rare/vagrant species are never hard-blocked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from bird_core.ids import SpeciesId
from bird_core.schemas import SpeciesStatus

# Configured occurrence providers (source_agreement denominator).
OCCURRENCE_SOURCES: tuple[str, ...] = ("ala", "gbif", "inaturalist", "ebird")

# Default component blend weights (sum need not be 1; the score is re-normalised).
DEFAULT_COMPONENT_WEIGHTS: dict[str, float] = {
    "occurrence": 0.35,
    "source_agreement": 0.20,
    "recency": 0.15,
    "roi_match": 0.20,
    "seasonal": 0.10,
}

# Occurrence saturation cap: a source-weighted total at/above this scores ~1.0.
_OCCURRENCE_CAP = 500.0
_RECENCY_WINDOW = 4  # years


@dataclass
class SpeciesEvidence:
    """Aggregated, provider-agnostic evidence for one species."""

    species_id: SpeciesId
    scientific_name: str
    common_name: str | None = None
    ebird_code: str | None = None
    occurrences_by_source: dict[str, int] = field(default_factory=dict)
    months_observed: set[int] = field(default_factory=set)
    inside_roi_fraction: float = 1.0
    recent_years: set[int] = field(default_factory=set)
    manual_review: bool = False

    @property
    def total_occurrences(self) -> int:
        return int(sum(self.occurrences_by_source.values()))


@dataclass
class ScoredSpecies:
    species_id: SpeciesId
    scientific_name: str
    common_name: str | None
    ebird_code: str | None
    total_occurrences: int
    n_sources: int
    components: dict[str, float]
    final_score: float
    tier: str  # "core" | "review" | "rejected"
    status: SpeciesStatus
    manual_review: bool


@dataclass
class ScoringConfig:
    source_weights: dict[str, float]
    component_weights: dict[str, float]
    min_occurrence_count: int
    min_score: float
    review_score: float

    @classmethod
    def defaults(cls) -> ScoringConfig:
        return cls(
            source_weights={"ala": 1.5, "gbif": 1.0, "ebird": 0.8, "inaturalist": 1.0},
            component_weights=dict(DEFAULT_COMPONENT_WEIGHTS),
            min_occurrence_count=3,
            min_score=0.5,
            review_score=0.3,
        )

    @classmethod
    def from_yaml(cls, path: Path) -> ScoringConfig:
        import yaml

        raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        base = cls.defaults()
        weights = raw.get("weights", {})
        source_weights = {**base.source_weights, **(weights.get("occurrence_sources") or {})}
        component_weights = {**base.component_weights, **(weights.get("components") or {})}
        thresholds = raw.get("thresholds", {})
        return cls(
            source_weights=source_weights,
            component_weights=component_weights,
            min_occurrence_count=int(
                thresholds.get("min_occurrence_count", base.min_occurrence_count)
            ),
            min_score=float(thresholds.get("min_score", base.min_score)),
            review_score=float(thresholds.get("review_score", base.review_score)),
        )


def _occurrence_component(evidence: SpeciesEvidence, source_weights: dict[str, float]) -> float:
    weighted = sum(
        count * source_weights.get(src, 1.0)
        for src, count in evidence.occurrences_by_source.items()
    )
    if weighted <= 0:
        return 0.0
    return min(1.0, math.log10(1 + weighted) / math.log10(1 + _OCCURRENCE_CAP))


def _recency_component(evidence: SpeciesEvidence, current_year: int) -> float:
    if not evidence.recent_years:
        return 0.0
    window = {current_year - i for i in range(_RECENCY_WINDOW)}
    return len(evidence.recent_years & window) / _RECENCY_WINDOW


def score_species(
    evidence: SpeciesEvidence,
    config: ScoringConfig,
    *,
    current_year: int | None = None,
) -> ScoredSpecies:
    """Score a single species from its aggregated evidence."""
    year = current_year if current_year is not None else date.today().year
    n_sources = sum(1 for s in OCCURRENCE_SOURCES if evidence.occurrences_by_source.get(s, 0) > 0)

    components = {
        "occurrence": _occurrence_component(evidence, config.source_weights),
        "source_agreement": n_sources / len(OCCURRENCE_SOURCES),
        "recency": _recency_component(evidence, year),
        "roi_match": max(0.0, min(1.0, evidence.inside_roi_fraction)),
        "seasonal": len(evidence.months_observed) / 12.0,
    }
    weight_total = sum(config.component_weights.get(k, 0.0) for k in components) or 1.0
    weighted = sum(components[k] * config.component_weights.get(k, 0.0) for k in components)
    final = weighted / weight_total
    final = round(final, 4)

    # Tiering — manual-review flag always routes to review, never hard-rejects.
    if evidence.manual_review:
        tier, status = "review", SpeciesStatus.review
    elif final >= config.min_score and evidence.total_occurrences >= config.min_occurrence_count:
        tier, status = "core", SpeciesStatus.accepted
    elif final >= config.review_score:
        tier, status = "review", SpeciesStatus.review
    else:
        tier, status = "rejected", SpeciesStatus.rejected

    return ScoredSpecies(
        species_id=evidence.species_id,
        scientific_name=evidence.scientific_name,
        common_name=evidence.common_name,
        ebird_code=evidence.ebird_code,
        total_occurrences=evidence.total_occurrences,
        n_sources=n_sources,
        components={k: round(v, 4) for k, v in components.items()},
        final_score=final,
        tier=tier,
        status=status,
        manual_review=evidence.manual_review,
    )


def score_all(
    evidences: list[SpeciesEvidence],
    config: ScoringConfig,
    *,
    current_year: int | None = None,
) -> list[ScoredSpecies]:
    """Score and rank species by final score (descending, then name)."""
    scored = [score_species(e, config, current_year=current_year) for e in evidences]
    scored.sort(key=lambda s: (-s.final_score, s.scientific_name))
    return scored
