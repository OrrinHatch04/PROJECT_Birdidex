"""Geotemporal reranker stub.

Combines the classifier's visual score with a location/season prior so that species that
are plausible for the ROI and the current month are boosted relative to implausible ones.

Crucially the prior is a *soft* multiplier bounded below by ``floor`` — an unlikely
species is penalised but never driven to zero, so genuine rare/vagrant sightings can
still surface for human review. This is intentionally not a hard filter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bird_inference.schema import SpeciesPrediction


@dataclass(frozen=True)
class SpeciesPrior:
    """ROI/seasonal prior for one species."""

    roi_score: float = 0.5  # 0..1 — how expected the species is in the ROI overall
    months: frozenset[int] = field(default_factory=frozenset)  # months with evidence (empty = any)


class GeoTemporalReranker:
    """Rerank predictions using per-species ROI/month priors."""

    def __init__(
        self,
        priors: dict[str, SpeciesPrior],
        *,
        floor: float = 0.1,
        unknown_prior: float = 0.4,
        off_season_penalty: float = 0.6,
    ) -> None:
        self._priors = priors
        self._floor = floor
        self._unknown_prior = unknown_prior
        self._off_season_penalty = off_season_penalty

    def prior_factor(self, species_id: str, month: int | None) -> float:
        prior = self._priors.get(species_id)
        if prior is None:
            factor = self._unknown_prior
        else:
            factor = prior.roi_score
            if month is not None and prior.months and month not in prior.months:
                factor *= self._off_season_penalty
        return max(self._floor, factor)

    def rerank(
        self, predictions: list[SpeciesPrediction], *, month: int | None = None
    ) -> list[SpeciesPrediction]:
        """Return predictions reranked by ``visual_score * prior_factor`` (renormalised)."""
        if not predictions:
            return []
        adjusted = [
            (p, p.visual_score * self.prior_factor(p.species_id, month)) for p in predictions
        ]
        total = sum(score for _, score in adjusted) or 1.0
        reranked = sorted(adjusted, key=lambda kv: -kv[1])
        out: list[SpeciesPrediction] = []
        for rank, (pred, score) in enumerate(reranked, start=1):
            out.append(
                SpeciesPrediction(
                    rank=rank,
                    species_id=pred.species_id,
                    common_name=pred.common_name,
                    score=round(score / total, 6),
                    visual_score=pred.visual_score,
                )
            )
        return out


def priors_from_candidates_csv(path: str) -> dict[str, SpeciesPrior]:
    """Build reranker priors from a ROI candidates CSV (uses roi_match + final_score)."""
    import csv

    priors: dict[str, SpeciesPrior] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            sid = row["species_id"]
            roi = float(row.get("final_score") or 0.0)
            priors[sid] = SpeciesPrior(roi_score=roi, months=frozenset())
    return priors
