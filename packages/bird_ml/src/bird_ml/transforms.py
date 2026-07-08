"""Image pre-processing transforms for inference (no albumentations dependency).

TODO: Add albumentations-backed training augmentation pipeline.
TODO: Expose a consistent interface so training and inference use the same normalisation.
"""

from __future__ import annotations

from typing import Any


def normalize_image(image: Any, mean: tuple[float, float, float] = (0.485, 0.456, 0.406),
                    std: tuple[float, float, float] = (0.229, 0.224, 0.225)) -> Any:
    """Normalise a numpy HWC float32 image to ImageNet statistics.

    Requires numpy.
    """
    import numpy as np
    img = np.asarray(image, dtype=np.float32) / 255.0
    return (img - np.array(mean)) / np.array(std)


def center_crop(image: Any, size: int = 224) -> Any:
    """Center-crop a numpy HWC image to size×size."""
    h, w = image.shape[:2]
    top = (h - size) // 2
    left = (w - size) // 2
    return image[top:top + size, left:left + size]
