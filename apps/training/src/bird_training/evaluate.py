"""Model evaluation: top-k accuracy, per-class metrics, calibration check.

``summarise_metrics`` is pure numpy so it is unit-testable without torch/onnxruntime.
``evaluate`` loads an ONNX model and runs it over the test split, which requires the
``inference`` dependency group.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from bird_ml.labels import LabelMap
from bird_ml.metrics import per_class_prf, top_k_accuracy, weighted_f1

INSTALL_HINT_INFER = "install the 'inference' group:  uv sync --group inference"


def summarise_metrics(
    scores: np.ndarray, labels: np.ndarray, label_map: LabelMap
) -> dict[str, Any]:
    """Compute the standard metric bundle from a score matrix and label vector."""
    preds = scores.argmax(axis=1)
    n = len(label_map)
    return {
        "n_samples": int(len(labels)),
        "top1": top_k_accuracy(scores, labels, k=1),
        "top5": top_k_accuracy(scores, labels, k=5),
        "weighted_f1": weighted_f1(labels, preds, n),
        "per_class": {
            str(label_map.to_species(k)): v  # type: ignore[arg-type]
            for k, v in per_class_prf(labels, preds, n).items()
        },
        # TODO: expected calibration error once a calibration split is wired in.
        "calibration": {"expected_calibration_error": None},
    }


def evaluate(model_path: Path, manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    """Evaluate an ONNX classifier over the test split (requires inference deps)."""
    try:
        import onnxruntime as ort  # noqa: F401
    except ImportError as exc:  # pragma: no cover - requires inference deps
        raise ImportError(f"onnxruntime is required to evaluate — {INSTALL_HINT_INFER}") from exc
    raise NotImplementedError(  # pragma: no cover
        "evaluate() ONNX inference loop is a TODO — use summarise_metrics() with scores for now"
    )
