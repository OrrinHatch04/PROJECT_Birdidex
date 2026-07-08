"""Species scoring: component scores, tiering, and rare-species safeguard."""

from __future__ import annotations

from bird_core.ids import SpeciesId
from bird_core.schemas import SpeciesStatus
from bird_roi_scan.scoring import ScoringConfig, SpeciesEvidence, score_all, score_species


def _ev(**kw: object) -> SpeciesEvidence:
    base = dict(
        species_id=SpeciesId("test_sp"),
        scientific_name="Test species",
        occurrences_by_source={"ala": 100, "gbif": 80, "inaturalist": 60, "ebird": 20},
        months_observed=set(range(1, 13)),
        inside_roi_fraction=0.95,
        recent_years={2022, 2023, 2024, 2025},
        manual_review=False,
    )
    base.update(kw)
    return SpeciesEvidence(**base)  # type: ignore[arg-type]


def test_strong_evidence_is_core_accepted() -> None:
    s = score_species(_ev(), ScoringConfig.defaults(), current_year=2025)
    assert s.tier == "core"
    assert s.status == SpeciesStatus.accepted
    assert 0.0 <= s.final_score <= 1.0
    assert s.n_sources == 4


def test_components_in_unit_range() -> None:
    s = score_species(_ev(), ScoringConfig.defaults(), current_year=2025)
    for name in ("occurrence", "source_agreement", "recency", "roi_match", "seasonal"):
        assert 0.0 <= s.components[name] <= 1.0


def test_manual_review_flag_routes_to_review_not_rejected() -> None:
    # Thin evidence + manual_review must land in review, never rejected/hard-blocked.
    ev = _ev(
        occurrences_by_source={"ala": 2},
        months_observed={6},
        inside_roi_fraction=0.2,
        recent_years={2021},
        manual_review=True,
    )
    s = score_species(ev, ScoringConfig.defaults(), current_year=2025)
    assert s.tier == "review"
    assert s.status == SpeciesStatus.review


def test_recency_decays_with_age() -> None:
    recent = score_species(_ev(recent_years={2025}), ScoringConfig.defaults(), current_year=2025)
    old = score_species(_ev(recent_years={2010}), ScoringConfig.defaults(), current_year=2025)
    assert recent.components["recency"] > old.components["recency"]


def test_score_all_is_sorted_descending() -> None:
    evs = [
        _ev(species_id=SpeciesId("a"), scientific_name="A", occurrences_by_source={"ala": 500}),
        _ev(species_id=SpeciesId("b"), scientific_name="B", occurrences_by_source={"ala": 3}),
    ]
    scored = score_all(evs, ScoringConfig.defaults(), current_year=2025)
    assert [s.final_score for s in scored] == sorted((s.final_score for s in scored), reverse=True)


def test_scoring_is_deterministic() -> None:
    cfg = ScoringConfig.defaults()
    a = score_species(_ev(), cfg, current_year=2025)
    b = score_species(_ev(), cfg, current_year=2025)
    assert a.final_score == b.final_score
