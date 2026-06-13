"""OpenCV camera adapter (dev/USB webcam).

TODO: Add PiCameraAdapter for Raspberry Pi Camera Module.
"""

from __future__ import annotations

from typing import Any

from bird_device.camera_base import CameraProtocol


class OpenCVCamera:
    """Wraps cv2.VideoCapture as a CameraProtocol.

    TODO: Handle camera init failures gracefully.
    TODO: Add resolution/FPS config from configs/inference/runtime.yaml.
    """

    def __init__(self, device_index: int = 0) -> None:
        self._device_index = device_index
        self._cap: Any = None

    def _ensure_open(self) -> None:
        if self._cap is None:
            try:
                import cv2
                self._cap = cv2.VideoCapture(self._device_index)
            except ImportError as exc:
                raise ImportError("opencv-python required — install the 'inference' group") from exc

    def capture_frame(self) -> Any:
        self._ensure_open()
        ret, frame = self._cap.read()
        if not ret:
            raise RuntimeError(f"Failed to capture frame from device {self._device_index}")
        return frame

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


assert isinstance(OpenCVCamera, type) and issubclass(OpenCVCamera, object)
