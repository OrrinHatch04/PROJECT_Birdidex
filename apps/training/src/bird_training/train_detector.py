"""Detector training entry point.

TODO: Implement using torch + bounding-box annotations from data/manifests/.
TODO: Consider YOLO-family or RT-DETR for edge-deployable latency targets.
"""

from __future__ import annotations

from pathlib import Path


def train(
    manifest_path: Path,
    config_path: Path,
    output_dir: Path,
) -> None:
    """Train a bird detector (stub — not yet implemented)."""
    raise NotImplementedError("train_detector.train not yet implemented")
