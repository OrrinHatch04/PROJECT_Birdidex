"""Camera abstraction Protocol for the cyberdeck.

TODO: Implement PiCameraAdapter for Raspberry Pi Camera Module 3.
TODO: Implement OpenCVCameraAdapter for USB webcam / dev testing.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CameraProtocol(Protocol):
    """Minimal camera interface required by the inference pipeline."""

    def capture_frame(self) -> Any:
        """Capture a single frame and return it as a numpy HWC uint8 array."""
        ...

    def release(self) -> None:
        """Release hardware resources."""
        ...
