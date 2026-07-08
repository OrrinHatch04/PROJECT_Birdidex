"""Export trained PyTorch checkpoints to ONNX, with a quantisation placeholder.

Raspberry Pi 5 is the deployment target, so exports use a static input size and a
dynamic batch axis, and a dynamic-quantisation hook is provided for CPU speed-ups.
The actual export needs torch; ``write_export_metadata`` is pure so the export contract
(input size, class count, opset) can be produced and tested without the heavy stack.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bird_ml.labels import LabelMap

INSTALL_HINT_TRAIN = "install the 'training' group:  uv sync --group training"
INSTALL_HINT_INFER = "install the 'inference' group:  uv sync --group inference"


def write_export_metadata(
    output_path: Path,
    *,
    label_map: LabelMap,
    image_size: int = 224,
    opset: int = 17,
) -> Path:
    """Write a sidecar JSON describing an ONNX export (pure — no torch)."""
    meta_path = output_path.with_suffix(".metadata.json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "onnx_file": output_path.name,
        "opset": opset,
        "input": {"name": "input", "shape": [None, 3, image_size, image_size], "dtype": "float32"},
        "output": {"name": "logits", "num_classes": len(label_map)},
        "classes": [str(s) for s in label_map.species_ids],
    }
    meta_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return meta_path


def export(
    checkpoint_path: Path,
    output_path: Path,
    *,
    label_map: LabelMap | None = None,
    image_size: int = 224,
    opset: int = 17,
) -> Path:
    """Export a PyTorch checkpoint to ONNX with a dynamic batch axis.

    Requires the ``training`` dependency group. Writes ``output_path`` and, when a label
    map is supplied, a metadata sidecar next to it.
    """
    try:
        import timm
        import torch
    except ImportError as exc:  # pragma: no cover - requires training deps
        raise ImportError(
            f"torch and timm are required for ONNX export — {INSTALL_HINT_TRAIN}"
        ) from exc

    ckpt: dict[str, Any] = torch.load(checkpoint_path, map_location="cpu")  # pragma: no cover
    model = timm.create_model(ckpt["backbone"], pretrained=False, num_classes=ckpt["num_classes"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.randn(1, 3, image_size, image_size)
    torch.onnx.export(
        model, dummy, str(output_path),
        input_names=["input"], output_names=["logits"], opset_version=opset,
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
    )
    if label_map is not None:
        write_export_metadata(output_path, label_map=label_map, image_size=image_size, opset=opset)
    return output_path


def quantize_dynamic(onnx_path: Path, output_path: Path) -> Path:
    """Apply ONNX Runtime dynamic quantisation for CPU/edge inference (placeholder hook).

    Requires the ``inference`` dependency group (onnxruntime). This is the documented
    quantisation entry point for the Pi target; the calibration/QAT path is a TODO.
    """
    try:
        from onnxruntime.quantization import QuantType
        from onnxruntime.quantization import quantize_dynamic as ort_quantize
    except ImportError as exc:  # pragma: no cover - requires inference deps
        raise ImportError(
            f"onnxruntime is required for quantisation — {INSTALL_HINT_INFER}"
        ) from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)  # pragma: no cover
    ort_quantize(str(onnx_path), str(output_path), weight_type=QuantType.QInt8)  # pragma: no cover
    return output_path  # pragma: no cover
