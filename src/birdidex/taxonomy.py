"""Classifier class-index and taxonomy helpers.

The image dataset scaffold reads classes only from ``class_index.json``. Folder
names are derived from those records, never discovered from the filesystem.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from birdidex.paths import default_class_index_path


@dataclass(frozen=True)
class TaxonClass:
    class_id: int
    label: str
    common_name: str
    scientific_name: str | None
    aliases: tuple[str, ...] = ()
    known_regions: tuple[str, ...] = ()
    source_files: tuple[str, ...] = ()
    observation_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def folder_name(self) -> str:
        return class_folder_name(self.class_id, self.label)

    @property
    def is_ambiguous(self) -> bool:
        return is_ambiguous_taxon(self.common_name, self.scientific_name)

    @property
    def clean_classifier_class(self) -> bool:
        return not self.is_ambiguous


def slugify(text: str) -> str:
    """Return a lower-case filesystem-safe slug."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def normalise_scientific_name(name: str | None) -> str:
    """Strip repeated whitespace from a scientific name."""
    return " ".join((name or "").strip().split())


def scientific_names_match(left: str | None, right: str | None) -> bool:
    return normalise_scientific_name(left).lower() == normalise_scientific_name(right).lower()


def build_species_key(scientific_name: str) -> str:
    return slugify(normalise_scientific_name(scientific_name))


def class_folder_name(class_id: int, label: str) -> str:
    """Return ``{class_id:03d}.{label}`` for ImageFolder-style directories."""
    if class_id < 0:
        raise ValueError(f"class_id must be non-negative, got {class_id}")
    clean_label = slugify(label)
    if not clean_label:
        raise ValueError("class label cannot be blank")
    return f"{class_id:03d}.{clean_label}"


def is_ambiguous_taxon(common_name: str | None, scientific_name: str | None) -> bool:
    """Return True for taxa that are not clean classifier classes."""
    for value in (common_name or "", scientific_name or ""):
        lowered = value.lower()
        if "sp." in lowered or "/" in lowered:
            return True
    return False


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def load_class_index(path: Path | None = None) -> list[TaxonClass]:
    """Load the canonical class index and validate stable identifiers."""
    class_index = path or default_class_index_path()
    payload = json.loads(class_index.read_text(encoding="utf-8"))
    rows = payload.get("classes")
    if not isinstance(rows, list):
        raise ValueError(f"{class_index} must contain a 'classes' list")

    classes: list[TaxonClass] = []
    seen_ids: set[int] = set()
    seen_folders: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"class row must be an object, got {type(row).__name__}")
        class_id = int(row["class_id"])
        label = str(row["label"])
        taxon = TaxonClass(
            class_id=class_id,
            label=slugify(label),
            common_name=str(row.get("common_name") or label),
            scientific_name=normalise_scientific_name(row.get("scientific_name")) or None,
            aliases=_tuple(row.get("aliases")),
            known_regions=_tuple(row.get("known_regions")),
            source_files=_tuple(row.get("source_files")),
            observation_count=int(row.get("observation_count") or 0),
            raw=dict(row),
        )
        if taxon.class_id in seen_ids:
            raise ValueError(f"duplicate class_id in {class_index}: {taxon.class_id}")
        if taxon.folder_name in seen_folders:
            raise ValueError(f"duplicate class folder in {class_index}: {taxon.folder_name}")
        seen_ids.add(taxon.class_id)
        seen_folders.add(taxon.folder_name)
        classes.append(taxon)

    classes.sort(key=lambda taxon: taxon.class_id)
    return classes


def clean_classifier_classes(classes: list[TaxonClass]) -> list[TaxonClass]:
    """Return taxa that should be used for image fetching by default."""
    return [taxon for taxon in classes if taxon.clean_classifier_class]


def classes_by_id(classes: list[TaxonClass]) -> dict[int, TaxonClass]:
    return {taxon.class_id: taxon for taxon in classes}


def expected_class_folders(classes: list[TaxonClass]) -> set[str]:
    return {taxon.folder_name for taxon in classes}


def write_class_folder_index_csv(classes: list[TaxonClass], output_path: Path) -> None:
    """Write ``data/images/class_folder_index.csv``."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "class_id",
                "label",
                "folder_name",
                "common_name",
                "scientific_name",
                "clean_classifier_class",
                "ambiguous_taxon",
            ],
        )
        writer.writeheader()
        for taxon in classes:
            writer.writerow(
                {
                    "class_id": taxon.class_id,
                    "label": taxon.label,
                    "folder_name": taxon.folder_name,
                    "common_name": taxon.common_name,
                    "scientific_name": taxon.scientific_name or "",
                    "clean_classifier_class": str(taxon.clean_classifier_class).lower(),
                    "ambiguous_taxon": str(taxon.is_ambiguous).lower(),
                }
            )
