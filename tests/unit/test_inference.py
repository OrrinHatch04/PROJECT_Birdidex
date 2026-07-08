"""Detector/cropper multi-box output, reranker behaviour, and inference JSON schema."""

from __future__ import annotations

import json

import numpy as np
from bird_inference.classifier import MockClassifier
from bird_inference.cropper import crop_box, crop_boxes
from bird_inference.detector import (
    BoundingBox,
    MockDetector,
    WholeFrameFallbackDetector,
)
from bird_inference.pipeline import run_image_inference
from bird_inference.reranker import GeoTemporalReranker, SpeciesPrior
from bird_inference.schema import (
    WARN_MULTIPLE_BIRDS,
    WARN_NO_BIRD,
    ImageInferenceResult,
    SpeciesPrediction,
)
from bird_ml.labels import LabelMap

FRAME = np.full((240, 320, 3), 100, dtype=np.uint8)
LABELS = LabelMap.from_species(["sp_a", "sp_b", "sp_c", "sp_d", "sp_e"])


def test_mock_detector_returns_multiple_boxes() -> None:
    det = MockDetector([BoundingBox(0, 0, 50, 50, 0.9), BoundingBox(60, 60, 120, 120, 0.8)])
    assert len(det.detect(FRAME)) == 2


def test_fallback_detector_covers_whole_frame() -> None:
    boxes = WholeFrameFallbackDetector().detect(FRAME)
    assert len(boxes) == 1
    assert boxes[0].as_tuple() == (0.0, 0.0, 320.0, 240.0)


def test_cropper_clamps_and_drops_degenerate() -> None:
    crop = crop_box(FRAME, BoundingBox(-10, -10, 50, 50, 0.9))
    assert crop.shape[:2] == (50, 50)
    # out-of-frame / inverted box yields empty crop, dropped by crop_boxes
    assert crop_boxes(FRAME, [BoundingBox(100, 100, 10, 10, 0.5)]) == []


def test_pipeline_multi_bird_result_schema() -> None:
    det = MockDetector([BoundingBox(0, 0, 100, 100, 0.9), BoundingBox(100, 100, 200, 200, 0.7)])
    result = run_image_inference(
        FRAME, image_id="img1", detector=det, classifier=MockClassifier(LABELS), top_k=5
    )
    assert isinstance(result, ImageInferenceResult)
    assert result.n_birds == 2
    assert WARN_MULTIPLE_BIRDS in result.warnings
    assert len(result.detections[0].predictions) == 5
    assert result.detections[0].predictions[0].rank == 1
    # JSON round-trips through the schema
    parsed = ImageInferenceResult.model_validate_json(result.to_json())
    assert parsed.n_birds == 2
    assert isinstance(json.loads(result.to_json())["detections"], list)


def test_pipeline_no_bird_case() -> None:
    result = run_image_inference(
        FRAME, image_id="img2", detector=MockDetector([]), classifier=MockClassifier(LABELS)
    )
    assert result.n_birds == 0
    assert WARN_NO_BIRD in result.warnings


def test_reranker_penalises_but_never_zeroes_rare_species() -> None:
    preds = [
        SpeciesPrediction(rank=1, species_id="rare", score=0.6, visual_score=0.6),
        SpeciesPrediction(rank=2, species_id="common", score=0.4, visual_score=0.4),
    ]
    priors = {
        "rare": SpeciesPrior(roi_score=0.02, months=frozenset({6})),
        "common": SpeciesPrior(roi_score=0.95, months=frozenset(range(1, 13))),
    }
    reranker = GeoTemporalReranker(priors, floor=0.1)
    reranked = reranker.rerank(preds, month=1)
    # common should now outrank rare, but rare keeps a non-zero score (floor)
    assert reranked[0].species_id == "common"
    rare = next(p for p in reranked if p.species_id == "rare")
    assert rare.score > 0.0


def test_reranker_prior_factor_floor() -> None:
    reranker = GeoTemporalReranker({}, floor=0.1, unknown_prior=0.4)
    assert reranker.prior_factor("unknown_sp", month=5) == 0.4
    assert reranker.prior_factor("x", None) >= 0.1
