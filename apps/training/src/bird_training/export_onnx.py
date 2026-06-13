"""Export trained PyTorch checkpoints to ONNX format.

TODO: Implement torch.onnx.export with dynamic batch dimension.
TODO: Validate exported ONNX graph with onnxruntime before writing to models/exports/.
"""

from __future__ import annotations

from pathlib import Path


def export(checkpoint_path: Path, output_path: Path, opset: int = 17) -> None:
    """Export a PyTorch checkpoint to ONNX (stub — not yet implemented)."""
    raise NotImplementedError("export_onnx.export not yet implemented")
