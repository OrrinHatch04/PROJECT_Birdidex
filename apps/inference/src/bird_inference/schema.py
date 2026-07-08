"""Pydantic schema for multi-bird image inference results.

One image can contain several birds, so the result is a list of detections, each with
its own top-k species predictions and warning flags. This schema is the stable contract
serialised to JSON for the UI and the SQLite observation log.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Warning flag constants.
WARN_NO_BIRD = "no_bird"
WARN_MULTIPLE_BIRDS = "multiple_birds"
WARN_LOW_CONFIDENCE = "low_confidence"
WARN_SIMILAR_SPECIES = "similar_species"


class SpeciesPrediction(BaseModel):
    rank: int
    species_id: str
    common_name: str | None = None
    score: float  # final (possibly reranked) score
    visual_score: float  # raw classifier score before reranking


class DetectionResult(BaseModel):
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    detector_confidence: float
    predictions: list[SpeciesPrediction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def top1(self) -> SpeciesPrediction | None:
        return self.predictions[0] if self.predictions else None


class ImageInferenceResult(BaseModel):
    image_id: str
    n_birds: int
    model_version: str | None = None
    reranked: bool = False
    detections: list[DetectionResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_json(self, *, indent: int | None = None) -> str:
        return self.model_dump_json(indent=indent)
