"""Training/export dependency boundaries and pure helpers (no torch installed)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from bird_ml.labels import LabelMap
from bird_training.evaluate import summarise_metrics
from bird_training.export_onnx import export, write_export_metadata
from bird_training.train_classifier import (
    build_label_map_from_manifest,
    compute_class_weights,
    train,
)

TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None
DATA = Path(__file__).resolve().parents[1].parent / "data/manifests/images_manifest.csv"


def _manifest(tmp_path: Path) -> Path:
    """Build a small manifest CSV for the boundary tests (independent of pipeline runs)."""
    import json as _json

    from bird_data.csvio import save_manifest_csv
    from bird_data.manifest_build import parse_inat_observations

    sample = Path(__file__).resolve().parents[1].parent / "data/seeds/inat_observations.sample.json"
    records = parse_inat_observations(_json.loads(sample.read_text()))
    path = tmp_path / "m.csv"
    save_manifest_csv(records, path)
    return path


def test_build_label_map_from_manifest(tmp_path: Path) -> None:
    lm = build_label_map_from_manifest(_manifest(tmp_path))
    assert len(lm) >= 3
    assert lm.species_ids == sorted(lm.species_ids)


def test_class_weights_length_matches_label_map(tmp_path: Path) -> None:
    m = _manifest(tmp_path)
    lm = build_label_map_from_manifest(m)
    weights = compute_class_weights(m, lm)
    assert len(weights) == len(lm)
    assert all(w >= 0 for w in weights)


@pytest.mark.skipif(TORCH_AVAILABLE, reason="torch installed — boundary not exercised")
def test_train_requires_torch(tmp_path: Path) -> None:
    with pytest.raises(ImportError) as exc:
        train(_manifest(tmp_path), Path("configs/training/classifier.yaml"), tmp_path / "out")
    assert "training" in str(exc.value)


@pytest.mark.skipif(TORCH_AVAILABLE, reason="torch installed — boundary not exercised")
def test_export_requires_torch(tmp_path: Path) -> None:
    with pytest.raises(ImportError):
        export(tmp_path / "ckpt.pt", tmp_path / "model.onnx")


def test_export_metadata_is_pure(tmp_path: Path) -> None:
    lm = LabelMap.from_species(["a", "b", "c"])
    meta = write_export_metadata(tmp_path / "classifier.onnx", label_map=lm, image_size=224)
    assert meta.exists()
    payload = json.loads(meta.read_text())
    assert payload["output"]["num_classes"] == 3
    assert payload["input"]["shape"] == [None, 3, 224, 224]
    assert payload["classes"] == ["a", "b", "c"]


def test_summarise_metrics_pure() -> None:
    lm = LabelMap.from_species(["a", "b", "c"])
    scores = np.eye(3)
    labels = np.array([0, 1, 2])
    summary = summarise_metrics(scores, labels, lm)
    assert summary["top1"] == 1.0
    assert set(summary["per_class"]) == {"a", "b", "c"}
    assert summary["calibration"]["expected_calibration_error"] is None
