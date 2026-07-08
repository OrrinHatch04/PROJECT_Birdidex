"""Inference app entry point.

Wires a single frame through the detect -> crop -> classify -> rerank pipeline. The
continuous capture loop is a thin wrapper over :func:`process_frame`; the heavy ONNX
models are optional, so the mock detector/classifier can drive the loop for dry-run.
"""

from __future__ import annotations

from typing import Any

from bird_device.camera_base import CameraProtocol

from bird_inference.classifier import ClassifierProtocol
from bird_inference.detector import DetectorProtocol
from bird_inference.pipeline import run_image_inference
from bird_inference.reranker import GeoTemporalReranker
from bird_inference.schema import ImageInferenceResult


def process_frame(
    frame: Any,
    *,
    image_id: str,
    detector: DetectorProtocol,
    classifier: ClassifierProtocol,
    reranker: GeoTemporalReranker | None = None,
    model_version: str | None = None,
) -> ImageInferenceResult:
    """Process a single captured frame into an inference result."""
    return run_image_inference(
        frame,
        image_id=image_id,
        detector=detector,
        classifier=classifier,
        reranker=reranker,
        model_version=model_version,
    )


def run_inference_loop(
    camera: CameraProtocol,
    *,
    detector: DetectorProtocol,
    classifier: ClassifierProtocol,
    reranker: GeoTemporalReranker | None = None,
    max_frames: int | None = None,
    model_version: str | None = None,
) -> None:
    """Capture-infer loop. ``max_frames`` bounds the loop (None = run until interrupted)."""
    count = 0
    try:
        while max_frames is None or count < max_frames:
            frame = camera.capture_frame()
            process_frame(
                frame,
                image_id=f"frame-{count}",
                detector=detector,
                classifier=classifier,
                reranker=reranker,
                model_version=model_version,
            )
            count += 1
    finally:
        camera.release()
