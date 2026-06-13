"""Label map: integer class index ↔ SpeciesId.

TODO: Load from a serialised label_map.json produced by the dataset builder.
TODO: Validate that the label map matches the model's output dimension.
"""

from __future__ import annotations

from pathlib import Path

from bird_core.ids import ModelClassId, SpeciesId


class LabelMap:
    def __init__(self, idx_to_species: dict[ModelClassId, SpeciesId]) -> None:
        self._fwd: dict[ModelClassId, SpeciesId] = idx_to_species
        self._rev: dict[SpeciesId, ModelClassId] = {v: k for k, v in idx_to_species.items()}

    def __len__(self) -> int:
        return len(self._fwd)

    def to_species(self, idx: ModelClassId) -> SpeciesId:
        return self._fwd[idx]

    def to_index(self, species_id: SpeciesId) -> ModelClassId:
        return self._rev[species_id]

    @classmethod
    def from_json(cls, path: Path) -> "LabelMap":
        """Load a label_map.json with {index: species_id} entries."""
        import json
        with path.open() as fh:
            raw: dict[str, str] = json.load(fh)
        return cls({ModelClassId(int(k)): SpeciesId(v) for k, v in raw.items()})
