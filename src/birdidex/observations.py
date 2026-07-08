"""Forward-ready observation logging schema for cyberdeck field captures.

This is schema/model only. It does not require live GPS, weather, or a camera — the
fields exist so the on-device logger and the offline review UI can agree on a shape now.
The live SQLite writer lives in :mod:`birdidex.db`; this module defines the richer
capture record and emits a JSON Schema for validation and documentation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

# (field name, JSON type, nullable) — the ordered contract for a capture record.
OBSERVATION_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("observation_id", "string", False),
    ("captured_at_utc", "string", False),
    ("local_time", "string", True),
    ("timezone", "string", True),
    ("season", "string", True),
    ("latitude", "number", True),
    ("longitude", "number", True),
    ("gps_accuracy_m", "number", True),
    ("region_guess", "string", True),
    ("weather_summary", "string", True),
    ("temperature_c", "number", True),
    ("humidity_percent", "number", True),
    ("wind_speed_mps", "number", True),
    ("pressure_hpa", "number", True),
    ("device_id", "string", True),
    ("camera_id", "string", True),
    ("image_path", "string", True),
    ("crop_path", "string", True),
    ("thumbnail_path", "string", True),
    ("detector_model_id", "string", True),
    ("classifier_model_id", "string", True),
    ("predicted_class_id", "integer", True),
    ("predicted_label", "string", True),
    ("confidence", "number", True),
    ("top_k_predictions", "array", True),
    ("user_confirmed_class_id", "integer", True),
    ("user_feedback", "string", True),
    ("notes", "string", True),
)


@dataclass
class ObservationRecord:
    observation_id: str
    captured_at_utc: str
    local_time: str | None = None
    timezone: str | None = None
    season: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    gps_accuracy_m: float | None = None
    region_guess: str | None = None
    weather_summary: str | None = None
    temperature_c: float | None = None
    humidity_percent: float | None = None
    wind_speed_mps: float | None = None
    pressure_hpa: float | None = None
    device_id: str | None = None
    camera_id: str | None = None
    image_path: str | None = None
    crop_path: str | None = None
    thumbnail_path: str | None = None
    detector_model_id: str | None = None
    classifier_model_id: str | None = None
    predicted_class_id: int | None = None
    predicted_label: str | None = None
    confidence: float | None = None
    top_k_predictions: list[dict[str, Any]] = field(default_factory=list)
    user_confirmed_class_id: int | None = None
    user_feedback: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservationRecord:
        known = {name for name, _, _ in OBSERVATION_FIELDS}
        payload = {key: value for key, value in data.items() if key in known}
        return cls(**payload)


def observation_json_schema() -> dict[str, Any]:
    """Return a JSON Schema (draft 2020-12) describing an observation record."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, json_type, nullable in OBSERVATION_FIELDS:
        types: list[str] = [json_type]
        if nullable:
            types.append("null")
        properties[name] = {"type": types if len(types) > 1 else json_type}
        if not nullable:
            required.append(name)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "BirdidexObservation",
        "description": "Cyberdeck field capture record (schema only; not yet logged live).",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def observation_schema_json() -> str:
    return json.dumps(observation_json_schema(), indent=2, ensure_ascii=False)
