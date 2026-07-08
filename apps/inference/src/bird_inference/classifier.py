"""Bird classifier interface and offline-friendly implementations.

:class:`BirdClassifier` wraps an ONNX model (needs the ``inference`` group).
:class:`MockClassifier` returns deterministic scores derived from the label map so the
inference pipeline, schema, and reranker can be tested without a trained model.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from bird_core.ids import SpeciesId
from bird_ml.labels import LabelMap


@runtime_checkable
class ClassifierProtocol(Protocol):
    def classify(self, crop: Any, top_k: int = 5) -> list[tuple[SpeciesId, float]]:
        ...


class MockClassifier:
    """Deterministic classifier for tests/dry-run.

    Scores are a stable pseudo-random function of the crop's mean pixel value (when a
    numpy array is given) and each species id, then softmax-normalised. This yields
    reproducible, plausibly-shaped top-k distributions with no model.
    """

    def __init__(self, label_map: LabelMap) -> None:
        self._label_map = label_map

    def _seed_from_crop(self, crop: Any) -> int:
        try:
            import numpy as np

            arr = np.asarray(crop)
            if arr.size:
                return int(abs(float(arr.mean())) * 1000) % 100000
        except Exception:  # noqa: BLE001 - fall back to a constant seed
            pass
        return 7

    def classify(self, crop: Any, top_k: int = 5) -> list[tuple[SpeciesId, float]]:
        import math

        seed = self._seed_from_crop(crop)
        raw: list[tuple[SpeciesId, float]] = []
        for sid in self._label_map.species_ids:
            h = hashlib.md5(f"{seed}:{sid}".encode()).hexdigest()  # noqa: S324 - not security
            raw.append((sid, int(h[:8], 16) / 0xFFFFFFFF))
        exp = [(sid, math.exp(v * 4)) for sid, v in raw]
        total = sum(v for _, v in exp)
        probs = sorted(((sid, v / total) for sid, v in exp), key=lambda kv: -kv[1])
        return probs[:top_k]


class BirdClassifier:
    """ONNX Runtime classifier wrapper (requires the ``inference`` group)."""

    def __init__(self, model_path: Path, label_map: LabelMap) -> None:
        self._model_path = model_path
        self._label_map = label_map
        self._session: Any = None

    def _load(self) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - requires inference deps
            raise ImportError(
                "onnxruntime required — install the 'inference' group: uv sync --group inference"
            ) from exc
        self._session = ort.InferenceSession(str(self._model_path))  # pragma: no cover

    def classify(  # pragma: no cover - requires model
        self, crop: Any, top_k: int = 5
    ) -> list[tuple[SpeciesId, float]]:
        """TODO: pre-process crop, run session, map argsort top-k via LabelMap."""
        raise NotImplementedError("BirdClassifier.classify not yet implemented")
