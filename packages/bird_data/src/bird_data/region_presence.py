"""Build per-region species encounter logs — the "regional Pokedex" priors.

Role in BIRDIDEX
----------------
This is the **single source of truth for where each species normally appears**. From the
same normalised observation rows used by ``species_classes``, it builds one row per
(region, species) pair with counts, date range, and visit/checklist counts, plus a
JSON summary of which regions each species is known from. Those priors later drive the
Pokemon-style "this species is out of region" rareness flag.

Region label
------------
:func:`canonicalise_region` picks the most specific available label:
``LOCALITY`` (our exports' ``Location`` column) first, else ``COUNTY``/``STATE``.
eBird localities already look like ``Lamington National Park--Rainforest Circuit``; we
keep that verbatim so it round-trips against future eBird pulls.

Next tasks
----------
* TODO(roi): compare these visited-region priors against a broader SEQ ROI species list
  (from eBird API / GBIF) to flag regionally anomalous sightings — see ``bird_data.rarity``.
* TODO(effort): fold ``DURATION MINUTES`` / checklist completeness in so presence is
  effort-normalised, not just raw counts.
* TODO(geo): attach lat/lon centroids per region for map rendering in the cyberdeck UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bird_data.ebird_ingest import (
    F_CHECKLIST_ID,
    F_COMMON_NAME,
    F_COUNTY,
    F_LATITUDE,
    F_LOCALITY,
    F_LONGITUDE,
    F_OBSERVATION_COUNT,
    F_OBSERVATION_DATE,
    F_OBSERVER,
    F_SCIENTIFIC_NAME,
    F_STATE,
)
from bird_data.species_classes import canonicalise_species_name, slugify

# Column order for region_species_presence.csv — explicit and stable.
REGION_PRESENCE_FIELDS: list[str] = [
    "region",
    "label",
    "common_name",
    "scientific_name",
    "observation_count",
    "first_seen",
    "last_seen",
    "visit_count",
    "latitude",
    "longitude",
]


@dataclass
class RegionSpecies:
    """Aggregate for one (region, species) pair."""

    region: str
    label: str
    common_name: str
    scientific_name: str | None
    observation_count: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    _visits: set = field(default_factory=set)  # SAMPLING EVENT ids or (date, observer)
    latitude: str | None = None
    longitude: str | None = None

    @property
    def visit_count(self) -> int:
        return len(self._visits)


def canonicalise_region(row: dict[str, str | None]) -> str:
    """Return the best available region/locality label for an observation row."""
    for key in (F_LOCALITY, F_COUNTY, F_STATE):
        value = row.get(key)
        if value and value.strip():
            return value.strip()
    return "unknown_region"


def _parse_count(value: str | None) -> int:
    if value is None:
        return 1
    v = value.strip()
    return int(v) if v.isdigit() else 1


def _visit_key(row: dict[str, str | None]) -> str:
    """A stable per-checklist key: prefer the eBird sampling-event id, else date+observer."""
    checklist = row.get(F_CHECKLIST_ID)
    if checklist and checklist.strip():
        return checklist.strip()
    return f"{row.get(F_OBSERVATION_DATE) or ''}|{row.get(F_OBSERVER) or ''}"


def build_region_species_presence(observations: list[dict[str, str | None]]) -> list[RegionSpecies]:
    """Build one :class:`RegionSpecies` per (region, species) pair, sorted deterministically."""
    by_key: dict[tuple[str, str], RegionSpecies] = {}
    for row in observations:
        common = (row.get(F_COMMON_NAME) or "").strip()
        scientific = (row.get(F_SCIENTIFIC_NAME) or "").strip() or None
        if not common and not scientific:
            continue
        label = canonicalise_species_name(common or scientific or "", scientific)
        region = canonicalise_region(row)
        key = (region, slugify(scientific) if scientific else slugify(common))

        rs = by_key.get(key)
        if rs is None:
            rs = RegionSpecies(
                region=region,
                label=label,
                common_name=common or (scientific or ""),
                scientific_name=scientific,
                latitude=row.get(F_LATITUDE),
                longitude=row.get(F_LONGITUDE),
            )
            by_key[key] = rs

        rs.observation_count += _parse_count(row.get(F_OBSERVATION_COUNT))
        rs._visits.add(_visit_key(row))

        date = (row.get(F_OBSERVATION_DATE) or "").strip() or None
        if date:
            if rs.first_seen is None or date < rs.first_seen:
                rs.first_seen = date
            if rs.last_seen is None or date > rs.last_seen:
                rs.last_seen = date

    return sorted(by_key.values(), key=lambda r: (r.region, r.label))


def build_species_region_summary(presence: list[RegionSpecies]) -> dict:
    """Build a JSON-friendly summary of where each species appears and vice versa.

    Shape::

        {
          "species_to_regions": {label: [region, ...]},
          "region_to_species":  {region: [label, ...]},
        }
    """
    species_to_regions: dict[str, list[str]] = {}
    region_to_species: dict[str, list[str]] = {}
    for rs in presence:
        species_to_regions.setdefault(rs.label, [])
        if rs.region not in species_to_regions[rs.label]:
            species_to_regions[rs.label].append(rs.region)
        region_to_species.setdefault(rs.region, [])
        if rs.label not in region_to_species[rs.region]:
            region_to_species[rs.region].append(rs.label)

    return {
        "species_to_regions": {k: sorted(v) for k, v in sorted(species_to_regions.items())},
        "region_to_species": {k: sorted(v) for k, v in sorted(region_to_species.items())},
    }


def write_region_presence_csv(presence: list[RegionSpecies], output_path: Path) -> None:
    """Write ``region_species_presence.csv`` — one row per (region, species) pair."""
    import csv

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REGION_PRESENCE_FIELDS)
        writer.writeheader()
        for rs in presence:
            writer.writerow(
                {
                    "region": rs.region,
                    "label": rs.label,
                    "common_name": rs.common_name,
                    "scientific_name": rs.scientific_name or "",
                    "observation_count": rs.observation_count,
                    "first_seen": rs.first_seen or "",
                    "last_seen": rs.last_seen or "",
                    "visit_count": rs.visit_count,
                    "latitude": rs.latitude or "",
                    "longitude": rs.longitude or "",
                }
            )
