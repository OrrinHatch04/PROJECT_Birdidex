"""Label map construction/serialisation and numpy metrics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from bird_ml.labels import LabelMap
from bird_ml.metrics import (
    confusion_matrix,
    per_class_prf,
    top_k_accuracy,
    weighted_f1,
)


def test_label_map_from_species_is_sorted_and_deduped() -> None:
    lm = LabelMap.from_species(["c", "a", "a", "b"])
    assert lm.species_ids == ["a", "b", "c"]
    assert len(lm) == 3
    assert int(lm.to_index("a")) == 0  # type: ignore[arg-type]
    assert str(lm.to_species(lm.to_index("b"))) == "b"


def test_label_map_json_round_trip(tmp_path: Path) -> None:
    lm = LabelMap.from_species(["dacelo_novaeguineae", "cracticus_tibicen"])
    path = tmp_path / "label_map.json"
    lm.to_json(path)
    loaded = LabelMap.from_json(path)
    assert loaded.species_ids == lm.species_ids


def test_label_map_rejects_duplicate_index_values() -> None:
    from bird_core.ids import ModelClassId, SpeciesId

    with pytest.raises(ValueError):
        LabelMap({ModelClassId(0): SpeciesId("x"), ModelClassId(1): SpeciesId("x")})


def test_top_k_accuracy() -> None:
    scores = np.array([[0.1, 0.9, 0.0], [0.8, 0.1, 0.1], [0.2, 0.3, 0.5]])
    labels = np.array([1, 0, 2])
    assert top_k_accuracy(scores, labels, k=1) == 1.0
    labels_wrong = np.array([2, 2, 0])
    assert top_k_accuracy(scores, labels_wrong, k=1) == 0.0
    assert top_k_accuracy(scores, labels_wrong, k=3) == 1.0


def test_confusion_and_prf_and_weighted_f1() -> None:
    labels = np.array([0, 0, 1, 1])
    preds = np.array([0, 1, 1, 1])
    cm = confusion_matrix(labels, preds, 2)
    assert cm.tolist() == [[1, 1], [0, 2]]
    prf = per_class_prf(labels, preds, 2)
    assert prf[1]["recall"] == 1.0
    wf1 = weighted_f1(labels, preds, 2)
    assert 0.0 <= wf1 <= 1.0
