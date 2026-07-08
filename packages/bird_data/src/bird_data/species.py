"""Pydantic model for a resolved species record."""

from __future__ import annotations

from bird_core.ids import SpeciesId
from bird_core.schemas import SpeciesStatus
from pydantic import BaseModel, Field


class SpeciesRecord(BaseModel):
    species_id: SpeciesId
    scientific_name: str
    common_name: str | None = None
    taxon_id_ala: str | None = None
    taxon_id_gbif: int | None = None
    taxon_id_inat: int | None = None
    ebird_code: str | None = None
    aliases: list[str] = Field(default_factory=list)
    status: SpeciesStatus = SpeciesStatus.review
