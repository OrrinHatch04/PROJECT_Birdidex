"""Offline species profile records for the Pokedex-style UI.

Profiles are built only from structured local data: the class index, accepted image
records, and optional curated note files. Free-text natural-history fields are never
invented — they are left ``null`` (or ``"TODO"`` in a curated file) so a later
enrichment pass from ALA/GBIF/Wikidata/Wikipedia or hand-written notes can fill them.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from birdidex.images import image_records_path, read_metadata_jsonl
from birdidex.paths import data_dir
from birdidex.paths import images_dir as default_images_dir
from birdidex.taxonomy import TaxonClass, load_class_index

# Natural-history fields that must come from curated data, never inference.
ENRICHABLE_FIELDS: tuple[str, ...] = (
    "habitat",
    "behaviour",
    "diet",
    "breeding_notes",
    "seasonal_notes",
    "similar_species",
    "rarity_notes",
    "conservation_status",
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def profiles_dir() -> Path:
    return data_dir() / "profiles"


def profile_notes_dir() -> Path:
    """Optional curated overrides: ``data/profiles/notes/{folder}.json``."""
    return profiles_dir() / "notes"


def species_profiles_path() -> Path:
    return profiles_dir() / "species_profiles.json"


def load_species_profiles(path: Path | None = None) -> list[dict[str, Any]]:
    """Load combined species profiles, returning an empty list when absent."""
    source = path or species_profiles_path()
    if not source.exists():
        return []
    payload = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("profiles"), list):
        return [profile for profile in payload["profiles"] if isinstance(profile, dict)]
    if isinstance(payload, list):
        return [profile for profile in payload if isinstance(profile, dict)]
    return []


def lookup_profile(
    profiles: list[dict[str, Any]],
    *,
    class_id: int | None = None,
    label: str | None = None,
) -> dict[str, Any] | None:
    """Find a profile by stable class id or label without inventing missing fields."""
    normalized_label = label.strip().lower() if label else None
    for profile in profiles:
        if class_id is not None and profile.get("class_id") == class_id:
            return dict(profile)
        if normalized_label and str(profile.get("label") or "").lower() == normalized_label:
            return dict(profile)
    return None


@dataclass
class SpeciesProfile:
    class_id: int
    label: str
    common_name: str
    scientific_name: str | None
    aliases: list[str]
    known_regions: list[str]
    habitat: str | None = None
    behaviour: str | None = None
    diet: str | None = None
    breeding_notes: str | None = None
    seasonal_notes: str | None = None
    similar_species: list[str] = field(default_factory=list)
    rarity_notes: str | None = None
    conservation_status: str | None = None
    representative_image_path: str | None = None
    representative_image_attribution: str | None = None
    data_sources: list[str] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _representative_image(
    class_id: int, records_by_class: dict[int, list[Any]]
) -> tuple[str | None, str | None]:
    for record in records_by_class.get(class_id, []):
        if record.status == "accepted" and record.local_path:
            return record.local_path, record.attribution
    return None, None


def _load_notes(taxon: TaxonClass) -> dict[str, Any]:
    path = profile_notes_dir() / f"{taxon.folder_name}.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_profile(
    taxon: TaxonClass,
    *,
    records_by_class: dict[int, list[Any]],
) -> SpeciesProfile:
    notes = _load_notes(taxon)
    image_path, attribution = _representative_image(taxon.class_id, records_by_class)
    data_sources = ["class_index.json"]
    if notes:
        data_sources.append("curated_notes")
    if image_path:
        data_sources.append("image_records.jsonl")

    profile = SpeciesProfile(
        class_id=taxon.class_id,
        label=taxon.label,
        common_name=taxon.common_name,
        scientific_name=taxon.scientific_name,
        aliases=list(taxon.aliases),
        known_regions=list(taxon.known_regions),
        representative_image_path=image_path,
        representative_image_attribution=attribution,
        data_sources=data_sources,
        generated_at=_utc_now(),
    )
    for field_name in ENRICHABLE_FIELDS:
        if field_name in notes and notes[field_name] not in (None, ""):
            setattr(profile, field_name, notes[field_name])
    return profile


def build_profiles(
    *,
    class_index_path: Path | None = None,
    images_root: Path | None = None,
) -> list[SpeciesProfile]:
    """Build one profile per class plus the combined ``species_profiles.json``."""
    classes = load_class_index(class_index_path)
    root = images_root or default_images_dir()
    records = read_metadata_jsonl(image_records_path(root))
    records_by_class: dict[int, list[Any]] = {}
    for record in records:
        records_by_class.setdefault(record.class_id, []).append(record)

    out_dir = profiles_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    profiles: list[SpeciesProfile] = []
    for taxon in classes:
        profile = build_profile(taxon, records_by_class=records_by_class)
        profiles.append(profile)
        per_path = out_dir / f"{taxon.folder_name}.json"
        per_path.write_text(
            json.dumps(profile.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    combined = {
        "generated_at": _utc_now(),
        "n_profiles": len(profiles),
        "class_source": "class_index.json",
        "profiles": [profile.to_dict() for profile in profiles],
    }
    species_profiles_path().write_text(
        json.dumps(combined, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return profiles
