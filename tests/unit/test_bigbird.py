from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from birdidex.bigbird import audit_zip, import_zip


def write_class_index(path: Path) -> Path:
    payload = {
        "version": 1,
        "classes": [
            {
                "class_id": 5,
                "label": "torresian_crow",
                "common_name": "Torresian Crow",
                "scientific_name": "Corvus orru",
            },
            {
                "class_id": 6,
                "label": "galah",
                "common_name": "Galah",
                "scientific_name": "Eolophus roseicapilla",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _png(color: tuple[int, int, int]) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (200, 150), color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_zip(path: Path) -> Path:
    coco = {
        "categories": [
            {"id": 1, "name": "Corvus orru"},
            {"id": 2, "name": "Vanellus miles uav"},
        ],
        "images": [
            {"id": 10, "file_name": "images/Corvus_orru/0001.png"},
            {"id": 11, "file_name": "images/Vanellus_miles_uav/0001.png"},
        ],
        "annotations": [
            {"id": 1, "image_id": 10, "category_id": 1, "bbox": [1, 2, 3, 4], "posture": "perched"},
            {"id": 2, "image_id": 11, "category_id": 2, "bbox": [5, 6, 7, 8]},
        ],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bb/images/Corvus_orru/0001.png", _png((10, 10, 10)))
        zf.writestr("bb/images/Vanellus_miles_uav/0001.png", _png((90, 90, 90)))
        zf.writestr("bb/annotations/instances.json", json.dumps(coco))
    return path


def test_audit_reports_overlap_and_annotation_types(tmp_path: Path) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    zip_path = make_zip(tmp_path / "bigbird.zip")

    audit = audit_zip(zip_path, class_index_path=class_index)

    assert audit.image_count == 2
    assert audit.file_count == 3
    assert set(audit.species_names) == {"Corvus orru", "Vanellus miles uav"}
    assert audit.per_species_image_counts["Corvus orru"] == 1
    assert audit.annotation_types["boxes"] is True
    assert audit.annotation_types["posture"] is True
    assert audit.annotation_types["sex"] is False
    assert [row["class_id"] for row in audit.overlap] == [5]
    assert audit.overlap[0]["scientific_name"] == "Corvus orru"
    assert audit.estimated_extracted_bytes > 0


def test_import_only_overlapping_species_as_auxiliary(tmp_path: Path) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    zip_path = make_zip(tmp_path / "bigbird.zip")

    import birdidex.bigbird as bigbird_module

    # Redirect the auxiliary/records outputs into the temp dir.
    aux_root = tmp_path / "aux"
    records_path = tmp_path / "bigbird_records.jsonl"
    bigbird_module.bigbird_auxiliary_dir = lambda: aux_root  # type: ignore[assignment]
    bigbird_module.bigbird_records_path = lambda: records_path  # type: ignore[assignment]

    summary = import_zip(zip_path, class_index_path=class_index)

    assert summary.extracted_images == 1
    assert summary.classes_touched == 1
    assert summary.included_in_splits is False
    assert (aux_root / "005.torresian_crow" / "0001.png").exists()

    lines = [json.loads(line) for line in records_path.read_text().splitlines() if line]
    assert len(lines) == 1
    record = lines[0]
    assert record["view_type"] == "uav_top_down"
    assert record["dataset_role"] == "auxiliary"
    assert record["boxes"] == [[1.0, 2.0, 3.0, 4.0]]
