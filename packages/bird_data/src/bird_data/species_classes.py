"""Turn normalised eBird observations into a stable BIRDIDEX species class index.

Role in BIRDIDEX
----------------
This is the **single source of truth for classifier class IDs**. It collapses raw
observation rows down to one record per species, assigns a stable integer ``class_id``,
and emits ``class_index.json`` (for training code) plus ``species_catalog.csv`` (for
humans). Later, image folders will be mapped onto these ``class_id`` values.

Class-ID policy
---------------
IDs are assigned by deterministic sort, never by filesystem/insertion order:

1. by ``taxonomic_order`` when every species has a valid one (true eBird exports), else
2. by canonical label alphabetically (our current simplified exports have no taxon order).

Species identity is keyed on the **scientific name** when available (the stable
biological identity), falling back to the common name. The human ``label`` is a slug of
the common name; if two distinct scientific names would collide on the same label, the
scientific slug is appended (``common__genus_species``) so labels stay unique.

Next tasks
----------
* TODO(images): join a per-class image-folder manifest onto ``class_id`` so training can
  resolve label -> images (hook into ``bird_data.manifests``).
* TODO(aliases): load manual alias/synonym overrides from a small YAML/CSV so lumped or
  renamed taxa map onto one class (``aliases`` is populated but not yet fed by overrides).
* TODO(taxonomy): validate scientific names against a taxonomy backbone before ID
  assignment so a typo does not mint a spurious class.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from bird_data.ebird_ingest import (
    F_COMMON_NAME,
    F_OBSERVATION_COUNT,
    F_SCIENTIFIC_NAME,
    F_SOURCE_FILE,
    F_TAXONOMIC_ORDER,
)

CLASS_ID_POLICY = "stable_sorted_by_taxonomic_order_then_common_name"
CLASS_INDEX_VERSION = 1

# Column order for species_catalog.csv — explicit so the schema is stable and testable.
SPECIES_CATALOG_FIELDS: list[str] = [
    "class_id",
    "label",
    "common_name",
    "scientific_name",
    "aliases",
    "known_regions",
    "source_files",
    "observation_count",
    "taxonomic_order",
]


@dataclass
class SpeciesClass:
    """One classifier class: a species plus its provenance and region priors."""

    label: str
    common_name: str
    scientific_name: str | None
    class_id: int = -1  # assigned by build_species_catalog after sorting
    aliases: list[str] = field(default_factory=list)
    known_regions: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    observation_count: int = 0
    taxonomic_order: float | None = None


def slugify(text: str) -> str:
    """Lower-case, ASCII-ish slug: ``Rainbow Bee-eater`` -> ``rainbow_bee_eater``."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def canonicalise_species_name(common_name: str, scientific_name: str | None = None) -> str:
    """Create a stable class label from a common name (+ optional scientific name).

    Returns the common-name slug by default (``australian_brushturkey``). When a
    scientific name is supplied the extended, guaranteed-unique form is
    ``australian_brushturkey__alectura_lathami`` — :func:`build_species_catalog` only
    falls back to that extended form on a genuine label collision.
    """
    base = slugify(common_name) or (slugify(scientific_name) if scientific_name else "")
    return base


def _extended_label(common_name: str, scientific_name: str | None) -> str:
    base = slugify(common_name)
    sci = slugify(scientific_name) if scientific_name else ""
    return f"{base}__{sci}" if sci else base


def _parse_count(value: str | None) -> int:
    """eBird uses ``X`` for "present, not counted"; treat X/blank/non-numeric as 1."""
    if value is None:
        return 1
    v = value.strip()
    if v.isdigit():
        return int(v)
    return 1


def _parse_taxon_order(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None


def build_species_catalog(
    observations: list[dict[str, str | None]],
    region_of: Callable[[dict], str] | None = None,
) -> list[SpeciesClass]:
    """Return one :class:`SpeciesClass` per species, with stable ``class_id`` assigned.

    ``region_of`` maps an observation row to its region label (defaults to
    ``region_presence.canonicalise_region`` to avoid a hard import cycle at call time).
    Aggregates observation counts, source files and known regions per species.
    """
    if region_of is None:
        from bird_data.region_presence import canonicalise_region

        region_of = canonicalise_region

    by_identity: dict[str, SpeciesClass] = {}
    for row in observations:
        common = (row.get(F_COMMON_NAME) or "").strip()
        scientific = (row.get(F_SCIENTIFIC_NAME) or "").strip() or None
        if not common and not scientific:
            continue  # nothing to key on; skip blank line

        identity = slugify(scientific) if scientific else slugify(common)
        sp = by_identity.get(identity)
        if sp is None:
            sp = SpeciesClass(
                label=canonicalise_species_name(common or scientific or identity, scientific),
                common_name=common or (scientific or identity),
                scientific_name=scientific,
                taxonomic_order=_parse_taxon_order(row.get(F_TAXONOMIC_ORDER)),
            )
            by_identity[identity] = sp

        sp.observation_count += _parse_count(row.get(F_OBSERVATION_COUNT))
        source = row.get(F_SOURCE_FILE)
        if source and source not in sp.source_files:
            sp.source_files.append(source)
        region = region_of(row)
        if region and region not in sp.known_regions:
            sp.known_regions.append(region)

    species = list(by_identity.values())
    _disambiguate_labels(species)
    for sp in species:
        sp.source_files.sort()
        sp.known_regions.sort()

    # Deterministic ordering -> stable class_id.
    all_have_taxon = species and all(s.taxonomic_order is not None for s in species)
    if all_have_taxon:
        species.sort(key=lambda s: (s.taxonomic_order, s.label))
    else:
        species.sort(key=lambda s: s.label)
    for class_id, sp in enumerate(species):
        sp.class_id = class_id
    return species


def _disambiguate_labels(species: list[SpeciesClass]) -> None:
    """Promote colliding common-name labels to the extended ``common__genus_species`` form."""
    seen: dict[str, list[SpeciesClass]] = {}
    for sp in species:
        seen.setdefault(sp.label, []).append(sp)
    for group in seen.values():
        if len(group) > 1:
            for sp in group:
                sp.label = _extended_label(sp.common_name, sp.scientific_name)


def write_class_index(species: list[SpeciesClass], output_path: Path) -> None:
    """Write ``class_index.json`` — the canonical label map for classifier training."""
    payload = {
        "version": CLASS_INDEX_VERSION,
        "class_id_policy": CLASS_ID_POLICY,
        "n_classes": len(species),
        "classes": [
            {
                "class_id": sp.class_id,
                "label": sp.label,
                "common_name": sp.common_name,
                "scientific_name": sp.scientific_name,
                "aliases": sp.aliases,
                "known_regions": sp.known_regions,
                "source_files": sp.source_files,
                "observation_count": sp.observation_count,
            }
            for sp in species
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def write_species_catalog_csv(species: list[SpeciesClass], output_path: Path) -> None:
    """Write ``species_catalog.csv`` — a diff-friendly, spreadsheet-openable catalog."""
    import csv

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SPECIES_CATALOG_FIELDS)
        writer.writeheader()
        for sp in species:
            writer.writerow(
                {
                    "class_id": sp.class_id,
                    "label": sp.label,
                    "common_name": sp.common_name,
                    "scientific_name": sp.scientific_name or "",
                    "aliases": "|".join(sp.aliases),
                    "known_regions": "|".join(sp.known_regions),
                    "source_files": "|".join(sp.source_files),
                    "observation_count": sp.observation_count,
                    "taxonomic_order": "" if sp.taxonomic_order is None else sp.taxonomic_order,
                }
            )
