"""Bird classifier wrapper (ONNX Runtime).

TODO: Load classifier ONNX from models/exports/classifier.onnx.
TODO: Return top-k (species_id, confidence) pairs using LabelMap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bird_core.ids import ModelClassId, SpeciesId
from bird_ml.labels import LabelMap


class BirdClassifier:
    def __init__(self, model_path: Path, label_map: LabelMap) -> None:
        self._model_path = model_path
        self._label_map = label_map
        self._session: Any = None

    def _load(self) -> None:
        try:
            import onnxruntime as ort
            self._session = ort.InferenceSession(str(self._model_path))
        except ImportError as exc:
            raise ImportError("onnxruntime required — install the 'inference' group") from exc

    def classify(self, crop: Any, top_k: int = 5) -> list[tuple[SpeciesId, float]]:
        """TODO: Pre-process crop, run session, return top-k species."""
        raise NotImplementedError("BirdClassifier.classify not yet implemented")
