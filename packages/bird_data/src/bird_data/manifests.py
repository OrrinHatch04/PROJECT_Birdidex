"""Pydantic model for an image manifest record."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from bird_core.ids import ImageId, SourceRecordId
from bird_core.schemas import DatasetSplit, EvidenceSource
from pydantic import BaseModel, Field


class ImageManifestRecord(BaseModel):
    image_id: ImageId
    source: EvidenceSource
    license: str | None = None
    photo_url: str | None = None
    local_path: Path | None = None
    scientific_name: str
    common_name: str | None = None
    taxon_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    event_date: date | None = None
    inside_roi: bool | None = None
    quality_grade: str | None = None
    captive_or_cultivated: bool | None = None
    split: DatasetSplit = DatasetSplit.review
    bbox_path: Path | None = None
    source_record_id: SourceRecordId | None = None
    width_px: int | None = None
    height_px: int | None = None
    extra: dict[str, str] = Field(default_factory=dict)
