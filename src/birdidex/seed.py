"""Deterministic seed derivation for reproducible dataset operations.

Every randomised step in the pipeline (species-selection order, train/val/test splits,
candidate sampling, duplicate tie-breaking, audit subsets) draws from the single project
master seed via :func:`derive_seed`, so a fixed seed makes the whole pipeline repeatable.
The seed itself is loaded through :mod:`birdidex.secrets` and never printed in full.
"""

from __future__ import annotations

import hashlib
import random

from birdidex.secrets import load_master_seed
from birdidex.taxonomy import (
    TaxonClass,
    clean_classifier_classes,
    normalise_scientific_name,
    slugify,
)

# Stable purpose labels so a derived stream never accidentally changes.
PURPOSE_SPECIES_SELECTION = "species_selection"
PURPOSE_SPLITS = "splits"
PURPOSE_SAMPLING = "sampling"
PURPOSE_DEDUPE = "dedupe_tiebreak"
PURPOSE_AUDIT_SUBSET = "audit_subset"

_INT32 = 2**31


def derive_seed(purpose: str, *, master: int | None = None) -> int:
    """Derive a stable non-negative 31-bit seed for ``purpose`` from the master seed."""
    root_seed = master if master is not None else load_master_seed()
    digest = hashlib.sha256(f"{root_seed}:{purpose}".encode()).hexdigest()
    return int(digest, 16) % _INT32


def seeded_random(purpose: str, *, master: int | None = None) -> random.Random:
    """Return a ``random.Random`` seeded deterministically for ``purpose``."""
    return random.Random(derive_seed(purpose, master=master))


def _selection_key(class_id: int, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{class_id}".encode()).hexdigest()


def _matches_requested(taxon: TaxonClass, wanted: set[str]) -> bool:
    keys = {
        taxon.label.lower(),
        taxon.folder_name.lower(),
        taxon.common_name.lower(),
        slugify(taxon.common_name),
        str(taxon.class_id),
    }
    if taxon.scientific_name:
        keys.add(normalise_scientific_name(taxon.scientific_name).lower())
        keys.add(slugify(taxon.scientific_name))
    return bool(keys & wanted)


def select_species(
    classes: list[TaxonClass],
    *,
    limit: int | None = None,
    species_list: list[str] | None = None,
    include_ambiguous: bool = False,
    master: int | None = None,
) -> list[TaxonClass]:
    """Deterministically select classes for a collection run.

    Without ``species_list`` the clean (non-ambiguous) classes are ordered by a
    seed-derived key and the first ``limit`` are returned, so the same seed always yields
    the same species set. With ``species_list`` the named species are selected (order
    preserved) and ``limit`` is ignored. Ambiguous taxa are excluded unless
    ``include_ambiguous`` is set.
    """
    pool = classes if include_ambiguous else clean_classifier_classes(classes)

    if species_list:
        by_class = {taxon.class_id: taxon for taxon in pool}
        selected: list[TaxonClass] = []
        seen: set[int] = set()
        # Preserve the caller's order, matching each requested name once.
        for name in species_list:
            token = name.strip().lower()
            for taxon in by_class.values():
                if taxon.class_id in seen:
                    continue
                if _matches_requested(taxon, {token}):
                    selected.append(taxon)
                    seen.add(taxon.class_id)
                    break
        return selected

    seed = derive_seed(PURPOSE_SPECIES_SELECTION, master=master)
    ordered = sorted(pool, key=lambda taxon: (_selection_key(taxon.class_id, seed), taxon.class_id))
    if limit is not None:
        ordered = ordered[: max(0, limit)]
    return ordered
