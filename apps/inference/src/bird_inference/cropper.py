"""Crop detected bounding boxes out of a frame.

Pure numpy so it works for tests and the dry-run pipeline without opencv/pillow. Boxes
are clamped to the frame bounds and degenerate (zero-area) boxes are skipped.
"""

from __future__ import annotations

from typing import Any

from bird_inference.detector import BoundingBox


def crop_box(frame: Any, box: BoundingBox) -> Any:
    """Return the sub-array of ``frame`` inside ``box`` (numpy HWC array in, array out)."""
    import numpy as np

    arr = np.asarray(frame)
    h, w = arr.shape[:2]
    x1 = max(0, min(int(round(box.x1)), w))
    y1 = max(0, min(int(round(box.y1)), h))
    x2 = max(0, min(int(round(box.x2)), w))
    y2 = max(0, min(int(round(box.y2)), h))
    if x2 <= x1 or y2 <= y1:
        return arr[0:0, 0:0]
    return arr[y1:y2, x1:x2]


def crop_boxes(frame: Any, boxes: list[BoundingBox]) -> list[Any]:
    """Crop every non-degenerate box; degenerate boxes are dropped."""
    crops: list[Any] = []
    for box in boxes:
        crop = crop_box(frame, box)
        if getattr(crop, "size", 0):
            crops.append(crop)
    return crops
