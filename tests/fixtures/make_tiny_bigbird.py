"""Generate the tiny Big Bird zip fixture used by tests and acceptance checks.

Run with the vision group available:

    uv run python tests/fixtures/make_tiny_bigbird.py

The archive mimics a COCO-annotated UAV dataset: a handful of small images plus an
``annotations/instances.json`` with one species that overlaps ``class_index.json``
(Torresian Crow / Corvus orru) and one that does not.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

FIXTURE = Path(__file__).with_name("tiny_bigbird.zip")


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (256, 192), color).save(buffer, format="PNG")
    return buffer.getvalue()


def build(path: Path = FIXTURE) -> Path:
    crow = _png_bytes((40, 40, 40))
    other = _png_bytes((200, 120, 60))
    coco = {
        "categories": [
            {"id": 1, "name": "Corvus orru"},
            {"id": 2, "name": "Aquila audax uav"},
        ],
        "images": [
            {"id": 10, "file_name": "images/Corvus_orru/0001.png"},
            {"id": 11, "file_name": "images/Corvus_orru/0002.png"},
            {"id": 20, "file_name": "images/Aquila_audax_uav/0001.png"},
        ],
        "annotations": [
            {
                "id": 1,
                "image_id": 10,
                "category_id": 1,
                "bbox": [10, 12, 40, 44],
                "posture": "perched",
            },
            {"id": 2, "image_id": 11, "category_id": 1, "bbox": [20, 22, 30, 34]},
            {
                "id": 3,
                "image_id": 20,
                "category_id": 2,
                "bbox": [5, 6, 50, 60],
                "segmentation": [[1, 2, 3, 4]],
            },
        ],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bigbird/images/Corvus_orru/0001.png", crow)
        zf.writestr("bigbird/images/Corvus_orru/0002.png", crow)
        zf.writestr("bigbird/images/Aquila_audax_uav/0001.png", other)
        zf.writestr("bigbird/annotations/instances.json", json.dumps(coco))
    return path


if __name__ == "__main__":
    print(f"wrote {build()}")
