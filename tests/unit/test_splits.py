from __future__ import annotations

import json
from pathlib import Path

import pytest

from birdidex.providers import ImageMetadataRecord
from birdidex.splits import assign_split_names, create_splits, validate_split_ratios


def write_class_index(path: Path) -> Path:
    payload = {
        "version": 1,
        "classes": [
            {
                "class_id": 0,
                "label": "galah",
                "common_name": "Galah",
                "scientific_name": "Eolophus roseicapilla",
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def make_record(index: int, image_path: Path, sha256: str | None = None) -> ImageMetadataRecord:
    return ImageMetadataRecord(
        class_id=0,
        label="galah",
        common_name="Galah",
        scientific_name="Eolophus roseicapilla",
        provider="fixture",
        provider_record_id=f"record-{index}",
        image_url=f"https://example.test/{index}.jpg",
        page_url=None,
        license_code="cc-by",
        rights_holder=None,
        attribution=None,
        width=100,
        height=100,
        observed_on=None,
        latitude=None,
        longitude=None,
        raw_metadata={},
        local_path=str(image_path),
        sha256=sha256,
        status="accepted",
    )


def test_split_ratio_sanity() -> None:
    validate_split_ratios(0.75, 0.15, 0.10)
    with pytest.raises(ValueError):
        validate_split_ratios(0.8, 0.3, 0.1)


def test_split_creation_uses_symlinks_and_keeps_sha_group_together(tmp_path: Path) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    local_dir = tmp_path / "local"
    local_dir.mkdir()
    paths = []
    for index in range(4):
        path = local_dir / f"{index}.jpg"
        path.write_bytes(f"image-{index}".encode())
        paths.append(path)

    records = [
        make_record(0, paths[0], sha256="same"),
        make_record(1, paths[1], sha256="same"),
        make_record(2, paths[2], sha256="unique-2"),
        make_record(3, paths[3], sha256="unique-3"),
    ]

    mapping = assign_split_names(records, train=0.5, val=0.25, test=0.25, seed=42)
    assert mapping["sha256:same"] in {"train", "val", "test"}

    summary = create_splits(
        records=records,
        class_index_path=class_index,
        images_root=tmp_path / "images",
        train=0.5,
        val=0.25,
        test=0.25,
        seed=42,
    )

    assert summary.total == 4
    assert summary.linked_or_copied == 4
    assert summary.duplicate_groups == 1
    assert any(
        (tmp_path / "images" / "splits" / split / "000.galah").iterdir()
        for split in ("train", "val", "test")
    )
