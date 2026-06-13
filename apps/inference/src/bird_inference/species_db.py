"""Offline species database: look up display info for a SpeciesId.

TODO: Build from processed SpeciesRecord parquet during dataset pipeline.
TODO: Include photo thumbnails, common name, type/climate/habitat fields.
"""

from __future__ import annotations

from pathlib import Path

from bird_core.ids import SpeciesId
from bird_data.species import SpeciesRecord


class SpeciesDB:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._records: dict[SpeciesId, SpeciesRecord] = {}

    def load(self) -> None:
        """TODO: Load species records from parquet or duckdb."""
        raise NotImplementedError("SpeciesDB.load not yet implemented")

    def lookup(self, species_id: SpeciesId) -> SpeciesRecord | None:
        return self._records.get(species_id)
