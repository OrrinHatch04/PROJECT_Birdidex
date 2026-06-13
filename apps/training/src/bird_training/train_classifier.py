"""Classifier training entry point.

TODO: Implement using timm + torch DataLoader over ImageManifestRecord dataset.
TODO: Log metrics to mlflow / tensorboard.
TODO: Save best checkpoint to models/checkpoints/.
"""

from __future__ import annotations

from pathlib import Path


def train(
    manifest_path: Path,
    config_path: Path,
    output_dir: Path,
) -> None:
    """Train a species classifier (stub — not yet implemented)."""
    raise NotImplementedError("train_classifier.train not yet implemented")
