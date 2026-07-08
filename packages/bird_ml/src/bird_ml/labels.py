"""Label map: integer class index ↔ SpeciesId.

The label map is the contract between the dataset builder, the trained model's output
layer, and the inference classifier. Indices are assigned by sorted species id so the
mapping is deterministic and reproducible across builds.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from bird_core.ids import ModelClassId, SpeciesId


class LabelMap:
    def __init__(self, idx_to_species: dict[ModelClassId, SpeciesId]) -> None:
        self._fwd: dict[ModelClassId, SpeciesId] = idx_to_species
        self._rev: dict[SpeciesId, ModelClassId] = {v: k for k, v in idx_to_species.items()}
        if len(self._rev) != len(self._fwd):
            raise ValueError("label map contains duplicate species ids")

    def __len__(self) -> int:
        return len(self._fwd)

    def to_species(self, idx: ModelClassId) -> SpeciesId:
        return self._fwd[idx]

    def to_index(self, species_id: SpeciesId) -> ModelClassId:
        return self._rev[species_id]

    @property
    def species_ids(self) -> list[SpeciesId]:
        """Species ids ordered by class index."""
        return [self._fwd[ModelClassId(i)] for i in range(len(self._fwd))]

    @classmethod
    def from_species(cls, species: Iterable[SpeciesId | str]) -> LabelMap:
        """Build a label map from an iterable of species ids (deduplicated + sorted)."""
        unique = sorted({str(s) for s in species})
        return cls({ModelClassId(i): SpeciesId(s) for i, s in enumerate(unique)})

    @classmethod
    def from_json(cls, path: Path) -> LabelMap:
        """Load a label_map.json with {index: species_id} entries."""
        with path.open() as fh:
            raw: dict[str, str] = json.load(fh)
        return cls({ModelClassId(int(k)): SpeciesId(v) for k, v in raw.items()})

    def to_json(self, path: Path) -> None:
        """Serialise as label_map.json with {index: species_id} entries."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {str(int(idx)): str(sid) for idx, sid in sorted(self._fwd.items())}
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
