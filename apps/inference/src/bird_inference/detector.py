"""Bird detector wrapper (ONNX Runtime).

TODO: Load detector ONNX from models/exports/detector.onnx.
TODO: Return bounding boxes as list[BBox] with confidence scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float


class BirdDetector:
    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._session: Any = None

    def _load(self) -> None:
        try:
            import onnxruntime as ort
            self._session = ort.InferenceSession(str(self._model_path))
        except ImportError as exc:
            raise ImportError("onnxruntime required — install the 'inference' group") from exc

    def detect(self, frame: Any) -> list[BoundingBox]:
        """TODO: Pre-process frame, run session, post-process NMS results."""
        raise NotImplementedError("BirdDetector.detect not yet implemented")
