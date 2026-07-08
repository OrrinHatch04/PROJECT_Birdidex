"""Image -> detect -> crop -> classify -> (rerank) -> multi-bird top-k result.

Handles the required edge cases explicitly:
* **no bird** — detector returns nothing → empty result flagged ``no_bird``.
* **multiple birds** — one detection per box, image flagged ``multiple_birds``.
* **low confidence** — top-1 below threshold → detection flagged ``low_confidence``.
* **similar species** — small top1/top2 gap → detection flagged ``similar_species``.

The reranker is optional; when supplied it applies ROI/month priors without hard-blocking
rare species (see :mod:`bird_inference.reranker`).
"""

from __future__ import annotations

from typing import Any

from bird_inference.classifier import ClassifierProtocol
from bird_inference.cropper import crop_box
from bird_inference.detector import DetectorProtocol
from bird_inference.reranker import GeoTemporalReranker
from bird_inference.schema import (
    WARN_LOW_CONFIDENCE,
    WARN_MULTIPLE_BIRDS,
    WARN_NO_BIRD,
    WARN_SIMILAR_SPECIES,
    DetectionResult,
    ImageInferenceResult,
    SpeciesPrediction,
)


def run_image_inference(
    image: Any,
    *,
    image_id: str,
    detector: DetectorProtocol,
    classifier: ClassifierProtocol,
    reranker: GeoTemporalReranker | None = None,
    common_names: dict[str, str] | None = None,
    model_version: str | None = None,
    top_k: int = 5,
    low_confidence_threshold: float = 0.3,
    similar_species_margin: float = 0.1,
    month: int | None = None,
) -> ImageInferenceResult:
    """Run the full single-image inference pipeline and return a structured result."""
    names = common_names or {}
    boxes = detector.detect(image)

    detections: list[DetectionResult] = []
    for box in boxes:
        crop = crop_box(image, box)
        if not getattr(crop, "size", 1):  # degenerate crop — skip this box
            continue
        raw = classifier.classify(crop, top_k=top_k)
        preds = [
            SpeciesPrediction(
                rank=i + 1,
                species_id=str(sid),
                common_name=names.get(str(sid)),
                score=float(score),
                visual_score=float(score),
            )
            for i, (sid, score) in enumerate(raw)
        ]
        if reranker is not None:
            preds = reranker.rerank(preds, month=month)

        warnings: list[str] = []
        if preds:
            if preds[0].score < low_confidence_threshold:
                warnings.append(WARN_LOW_CONFIDENCE)
            if len(preds) >= 2 and (preds[0].score - preds[1].score) < similar_species_margin:
                warnings.append(WARN_SIMILAR_SPECIES)

        detections.append(
            DetectionResult(
                bbox=box.as_tuple(),
                detector_confidence=float(box.confidence),
                predictions=preds,
                warnings=warnings,
            )
        )

    image_warnings: list[str] = []
    if not detections:
        image_warnings.append(WARN_NO_BIRD)
    elif len(detections) > 1:
        image_warnings.append(WARN_MULTIPLE_BIRDS)

    return ImageInferenceResult(
        image_id=image_id,
        n_birds=len(detections),
        model_version=model_version,
        reranked=reranker is not None,
        detections=detections,
        warnings=image_warnings,
    )
