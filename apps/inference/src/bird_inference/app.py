"""Inference app entry point.

TODO: Wire camera → detector → classifier → species_db → UI notification.
TODO: Expose a simple event loop that the cyberdeck_ui server polls.
"""

from __future__ import annotations

from bird_device.camera_base import CameraProtocol


def run_inference_loop(camera: CameraProtocol) -> None:
    """Run the capture-infer loop indefinitely (stub — not yet implemented).

    TODO: Implement frame capture, pre-process, detect, classify, lookup, notify UI.
    """
    raise NotImplementedError("run_inference_loop not yet implemented")
