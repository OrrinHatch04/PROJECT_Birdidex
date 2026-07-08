"""Normalised occurrence records and evidence aggregation.

Providers return heterogeneous JSON; each provider module exposes a ``parse_occurrences``
function that maps its native shape onto :class:`NormalizedOccurrence`. This module then
aggregates normalised occurrences into the :class:`SpeciesEvidence` consumed by scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from bird_core.ids import SpeciesId
from bird_data.taxonomy import build_species_key

from bird_roi_scan.scoring import SpeciesEvidence


@dataclass(frozen=True)
class NormalizedOccurrence:
    source: str
    source_record_id: str
    scientific_name: str
    common_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    event_date: date | None = None
    inside_roi: bool | None = None
    captive_or_cultivated: bool | None = None

    @property
    def year(self) -> int | None:
        return self.event_date.year if self.event_date else None

    @property
    def month(self) -> int | None:
        return self.event_date.month if self.event_date else None


def parse_iso_date(raw: str | None) -> date | None:
    """Parse a variety of provider date strings into a ``date`` (or None)."""
    if not raw or not isinstance(raw, str):
        return None
    token = raw.strip().replace("T", " ").split(" ")[0]
    try:
        return date.fromisoformat(token[:10])
    except ValueError:
        return None


def aggregate_to_evidence(
    occurrences: list[NormalizedOccurrence],
    *,
    species_id: SpeciesId | None = None,
    common_name: str | None = None,
    ebird_code: str | None = None,
    exclude_captive: bool = True,
) -> SpeciesEvidence:
    """Aggregate normalised occurrences for a single species into scoring evidence."""
    if not occurrences:
        raise ValueError("cannot aggregate an empty occurrence list")
    sci_name = occurrences[0].scientific_name
    sid = species_id or SpeciesId(build_species_key(sci_name))

    by_source: dict[str, int] = {}
    months: set[int] = set()
    years: set[int] = set()
    inside = 0
    total_geo = 0
    for occ in occurrences:
        if exclude_captive and occ.captive_or_cultivated:
            continue
        by_source[occ.source] = by_source.get(occ.source, 0) + 1
        if occ.month is not None:
            months.add(occ.month)
        if occ.year is not None:
            years.add(occ.year)
        if occ.inside_roi is not None:
            total_geo += 1
            if occ.inside_roi:
                inside += 1
    roi_fraction = inside / total_geo if total_geo else 1.0

    return SpeciesEvidence(
        species_id=sid,
        scientific_name=sci_name,
        common_name=common_name or occurrences[0].common_name,
        ebird_code=ebird_code,
        occurrences_by_source=by_source,
        months_observed=months,
        inside_roi_fraction=roi_fraction,
        recent_years=years,
        manual_review=False,
    )
