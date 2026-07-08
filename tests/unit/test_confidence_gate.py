from __future__ import annotations

from birdidex.infer import confidence_gate


def test_confidence_gate_accepts_only_strong_separated_prediction() -> None:
    decision = confidence_gate(
        [
            {"class_id": 1, "label": "galah", "confidence": 0.91},
            {"class_id": 2, "label": "little_corella", "confidence": 0.60},
        ],
        image_quality_score=20.0,
    )

    assert decision.status == "high confidence"
    assert decision.accept is True
    assert decision.top_prediction is not None
    assert decision.top_prediction.label == "galah"


def test_confidence_gate_keeps_medium_and_low_for_review() -> None:
    medium = confidence_gate(
        [
            {"class_id": 1, "label": "galah", "confidence": 0.74},
            {"class_id": 2, "label": "little_corella", "confidence": 0.70},
        ],
        image_quality_score=20.0,
    )
    low_quality = confidence_gate(
        [{"class_id": 1, "label": "galah", "confidence": 0.98}],
        image_quality_score=1.0,
    )

    assert medium.status == "medium confidence"
    assert medium.accept is False
    assert low_quality.status == "low confidence"
    assert low_quality.accept is False


def test_confidence_gate_handles_multi_subject_and_out_of_set() -> None:
    multi = confidence_gate(
        [{"class_id": 1, "label": "galah", "confidence": 0.95}],
        multi_subject=True,
    )
    out = confidence_gate([{"class_id": None, "label": "out_of_set", "confidence": 0.80}])

    assert multi.status == "multi-subject"
    assert multi.accept is False
    assert out.status == "out-of-set"
    assert out.accept is False
