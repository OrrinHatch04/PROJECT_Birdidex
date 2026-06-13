"""Model evaluation: top-k accuracy, per-class metrics, calibration check.

TODO: Load ONNX export and run on held-out test split.
TODO: Output confusion matrix CSV and calibration curve plots.
"""

from __future__ import annotations

from pathlib import Path


def evaluate(model_path: Path, manifest_path: Path, output_dir: Path) -> None:
    """Evaluate a model checkpoint on the test split (stub — not yet implemented)."""
    raise NotImplementedError("evaluate.evaluate not yet implemented")
