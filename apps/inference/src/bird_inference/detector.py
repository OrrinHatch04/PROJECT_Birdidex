"""Bird detector interface and offline-friendly implementations.

The real detector wraps an ONNX model and needs the ``inference`` deps. For dry-run and
tests, :class:`MockDetector` returns preset boxes and :class:`WholeFrameFallbackDetector`
treats the whole frame as a single detection — a safe fallback when no detector model is
available. All detectors return ``list[BoundingBox]`` so downstream code is identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


@runtime_checkable
class DetectorProtocol(Protocol):
    def detect(self, frame: Any) -> list[BoundingBox]:
        ...


class MockDetector:
    """Return a fixed list of boxes — used for deterministic tests and dry-run."""

    def __init__(self, boxes: list[BoundingBox]) -> None:
        self._boxes = boxes

    def detect(self, frame: Any) -> list[BoundingBox]:  # noqa: ARG002 - frame ignored by design
        return list(self._boxes)


class WholeFrameFallbackDetector:
    """Fallback detector: emit one box covering the whole frame.

    Use when no detector model is available — classification still runs on the full
    image. Reads the frame shape when it is a numpy array; otherwise falls back to a
    provided default size.
    """

    def __init__(self, confidence: float = 0.5, default_size: tuple[int, int] = (224, 224)) -> None:
        self.confidence = confidence
        self.default_size = default_size

    def detect(self, frame: Any) -> list[BoundingBox]:
        shape = getattr(frame, "shape", None)
        if shape is not None and len(shape) >= 2:
            h, w = int(shape[0]), int(shape[1])
        else:
            w, h = self.default_size
        return [BoundingBox(0.0, 0.0, float(w), float(h), self.confidence)]


class BirdDetector:
    """ONNX Runtime detector wrapper (requires the ``inference`` group)."""

    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._session: Any = None

    def _load(self) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:  # pragma: no cover - requires inference deps
            raise ImportError(
                "onnxruntime required — install the 'inference' group: uv sync --group inference"
            ) from exc
        self._session = ort.InferenceSession(str(self._model_path))  # pragma: no cover

    def detect(self, frame: Any) -> list[BoundingBox]:  # pragma: no cover - requires model
        """TODO: pre-process frame, run session, post-process NMS results."""
        raise NotImplementedError("BirdDetector.detect not yet implemented")
