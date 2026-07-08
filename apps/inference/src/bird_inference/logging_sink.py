"""Persist inference results to the SQLite observation log.

Each detected bird becomes one observation row (with its own top-k JSON), so an image
with several birds yields several observations. Lives in the app layer because it bridges
the inference schema (app) and the shared :class:`ObservationLog` (package).
"""

from __future__ import annotations

from bird_data.observation_log import ObservationLog

from bird_inference.schema import ImageInferenceResult


def log_result(
    log: ObservationLog,
    result: ImageInferenceResult,
    *,
    image_path: str | None = None,
    session_id: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    weather: str | None = None,
) -> list[int]:
    """Log every detection in ``result`` and return the new observation row ids."""
    ids: list[int] = []
    for i, det in enumerate(result.detections):
        top = det.top1
        top5 = [p.model_dump() for p in det.predictions]
        ids.append(
            log.log_observation(
                image_path=image_path,
                crop_path=f"{result.image_id}#det{i}",
                predicted_species_id=top.species_id if top else None,
                top5=top5,
                confidence=top.score if top else None,
                model_version=result.model_version,
                latitude=latitude,
                longitude=longitude,
                weather=weather,
                session_id=session_id,
            )
        )
    return ids
