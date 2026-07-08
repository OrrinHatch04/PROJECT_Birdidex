"""Torch dataset over an image manifest.

Importing this module is cheap, but constructing :class:`ManifestImageDataset` requires
the ``training``/``vision`` deps (torch + pillow) because it returns tensors. The manifest
parsing itself is pure so the sample list can be inspected without those deps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bird_core.schemas import DatasetSplit
from bird_data.csvio import load_manifest_csv
from bird_ml.labels import LabelMap

INSTALL_HINT = "install the 'training' group:  uv sync --group training"


def build_sample_list(
    manifest_path: Path, label_map: LabelMap, split: DatasetSplit
) -> list[tuple[Path, int]]:
    """Return ``[(local_path, class_index), ...]`` for a split (pure, no torch)."""
    records = load_manifest_csv(manifest_path)
    samples: list[tuple[Path, int]] = []
    for r in records:
        if r.split != split or r.local_path is None:
            continue
        try:
            idx = int(label_map.to_index(r.scientific_name))  # type: ignore[arg-type]
        except KeyError:
            continue
        samples.append((r.local_path, idx))
    return samples


def _require_deps() -> tuple[Any, Any, Any]:
    try:
        import numpy as np
        import torch
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - requires training deps
        raise ImportError(
            f"torch and pillow are required for the dataset — {INSTALL_HINT}"
        ) from exc
    return torch, Image, np


class ManifestImageDataset:  # pragma: no cover - requires training deps to instantiate
    """A ``torch.utils.data.Dataset``-compatible dataset built from a manifest split."""

    def __init__(
        self,
        manifest_path: Path,
        label_map: LabelMap,
        *,
        split: DatasetSplit,
        image_size: int = 224,
        train: bool = False,
    ) -> None:
        self._torch, self._Image, self._np = _require_deps()
        self.samples = build_sample_list(manifest_path, label_map, split)
        self.image_size = image_size
        self.train = train

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Any, int]:
        from bird_ml.transforms import center_crop, normalize_image

        path, label = self.samples[index]
        img = self._Image.open(path).convert("RGB").resize((self.image_size, self.image_size))
        arr = normalize_image(self._np.asarray(img))
        arr = center_crop(arr, self.image_size) if not self.train else arr
        tensor = self._torch.from_numpy(arr.transpose(2, 0, 1).copy()).float()
        return tensor, label
