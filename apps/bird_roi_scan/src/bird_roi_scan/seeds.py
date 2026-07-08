"""Deterministic local seed species list for SEQ dry-run scanning.

This is a small, hand-curated set of birds that are well known from the
Bundaberg-to-Goondiwindi region. It exists so the scan pipeline can run end-to-end
**offline** — no provider requests — and produce reproducible candidate outputs.

Each seed carries a synthetic *evidence profile* (occurrence counts per source, months
observed, ROI fraction, recent years). These stand in for real provider evidence during
dry-run so scoring is deterministic; live runs replace them with parsed provider records.
The numbers are illustrative only and must not be read as real occurrence data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bird_core.ids import SpeciesId
from bird_data.species import SpeciesRecord
from bird_data.taxonomy import build_species_key


@dataclass(frozen=True)
class SeedSpecies:
    scientific_name: str
    common_name: str
    ebird_code: str
    occurrences_by_source: dict[str, int] = field(default_factory=dict)
    months_observed: tuple[int, ...] = ()
    inside_roi_fraction: float = 1.0
    recent_years: tuple[int, ...] = ()
    manual_review: bool = False

    @property
    def species_id(self) -> SpeciesId:
        return SpeciesId(build_species_key(self.scientific_name))

    def to_species_record(self) -> SpeciesRecord:
        return SpeciesRecord(
            species_id=self.species_id,
            scientific_name=self.scientific_name,
            common_name=self.common_name,
            ebird_code=self.ebird_code,
        )


# Illustrative, deterministic SEQ seed set. Evidence profiles are synthetic.
SEED_SPECIES: list[SeedSpecies] = [
    SeedSpecies(
        "Dacelo novaeguineae", "Laughing Kookaburra", "laukoo1",
        {"ala": 420, "gbif": 310, "inaturalist": 260, "ebird": 90},
        months_observed=tuple(range(1, 13)), inside_roi_fraction=0.98,
        recent_years=(2022, 2023, 2024, 2025),
    ),
    SeedSpecies(
        "Cracticus tibicen", "Australian Magpie", "ausmag2",
        {"ala": 510, "gbif": 400, "inaturalist": 330, "ebird": 120},
        months_observed=tuple(range(1, 13)), inside_roi_fraction=0.99,
        recent_years=(2022, 2023, 2024, 2025),
    ),
    SeedSpecies(
        "Grallina cyanoleuca", "Magpie-lark", "maglar1",
        {"ala": 300, "gbif": 220, "inaturalist": 180, "ebird": 70},
        months_observed=tuple(range(1, 13)), inside_roi_fraction=0.97,
        recent_years=(2022, 2023, 2024, 2025),
    ),
    SeedSpecies(
        "Trichoglossus moluccanus", "Rainbow Lorikeet", "railor4",
        {"ala": 480, "gbif": 360, "inaturalist": 400, "ebird": 110},
        months_observed=tuple(range(1, 13)), inside_roi_fraction=0.96,
        recent_years=(2022, 2023, 2024, 2025),
    ),
    SeedSpecies(
        "Eolophus roseicapilla", "Galah", "galah1",
        {"ala": 360, "gbif": 280, "inaturalist": 150, "ebird": 80},
        months_observed=tuple(range(1, 13)), inside_roi_fraction=0.92,
        recent_years=(2022, 2023, 2024, 2025),
    ),
    SeedSpecies(
        "Malurus cyaneus", "Superb Fairywren", "supfai1",
        {"ala": 210, "gbif": 160, "inaturalist": 190, "ebird": 60},
        months_observed=tuple(range(1, 13)), inside_roi_fraction=0.90,
        recent_years=(2022, 2023, 2024, 2025),
    ),
    SeedSpecies(
        "Threskiornis moluccus", "Australian White Ibis", "auibis1",
        {"ala": 260, "gbif": 200, "inaturalist": 170, "ebird": 75},
        months_observed=tuple(range(1, 13)), inside_roi_fraction=0.88,
        recent_years=(2022, 2023, 2024, 2025),
    ),
    SeedSpecies(
        "Platycercus adscitus", "Pale-headed Rosella", "pahros1",
        {"ala": 150, "gbif": 110, "inaturalist": 90, "ebird": 40},
        months_observed=tuple(range(1, 13)), inside_roi_fraction=0.94,
        recent_years=(2022, 2023, 2024, 2025),
    ),
    SeedSpecies(
        "Menura alberti", "Albert's Lyrebird", "alblyr1",
        {"ala": 22, "gbif": 14, "inaturalist": 9, "ebird": 3},
        months_observed=(5, 6, 7, 8), inside_roi_fraction=0.75,
        recent_years=(2023, 2024),
    ),
    SeedSpecies(
        "Turnix melanogaster", "Black-breasted Buttonquail", "blbbut1",
        {"ala": 12, "gbif": 6, "inaturalist": 3, "ebird": 1},
        months_observed=(3, 4, 9, 10), inside_roi_fraction=0.60,
        recent_years=(2023, 2024), manual_review=True,
    ),
    SeedSpecies(
        "Rostratula australis", "Australian Painted-snipe", "auapsn1",
        {"ala": 5, "gbif": 3, "inaturalist": 1, "ebird": 0},
        months_observed=(11, 12, 1), inside_roi_fraction=0.45,
        recent_years=(2022,), manual_review=True,
    ),
    SeedSpecies(
        "Lathamus discolor", "Swift Parrot", "swipar1",
        {"ala": 2, "gbif": 1, "inaturalist": 0, "ebird": 0},
        months_observed=(6, 7), inside_roi_fraction=0.20,
        recent_years=(2021,), manual_review=True,
    ),
]


def seed_species() -> list[SeedSpecies]:
    """Return the deterministic SEQ seed species list (stable order)."""
    return list(SEED_SPECIES)
