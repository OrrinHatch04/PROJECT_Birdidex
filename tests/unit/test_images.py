from __future__ import annotations

import json
from pathlib import Path

from birdidex.images import (
    image_records_path,
    read_metadata_jsonl,
    scaffold_image_dataset,
    validate_no_extra_class_folders,
    write_metadata_jsonl,
)
from birdidex.providers import ImageMetadataRecord


def write_class_index(path: Path) -> Path:
    payload = {
        "version": 1,
        "classes": [
            {
                "class_id": 0,
                "label": "rainbow_bee_eater",
                "common_name": "Rainbow Bee-eater",
                "scientific_name": "Merops ornatus",
            },
            {
                "class_id": 1,
                "label": "galah",
                "common_name": "Galah",
                "scientific_name": "Eolophus roseicapilla",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def sample_record() -> ImageMetadataRecord:
    return ImageMetadataRecord(
        class_id=0,
        label="rainbow_bee_eater",
        common_name="Rainbow Bee-eater",
        scientific_name="Merops ornatus",
        provider="inaturalist",
        provider_record_id="1:2",
        image_url="https://example.test/image.jpg",
        page_url="https://example.test/page",
        license_code="cc-by",
        rights_holder="A. Person",
        attribution="A. Person / CC BY",
        width=1200,
        height=800,
        observed_on="2026-01-02",
        latitude=-27.0,
        longitude=153.0,
        raw_metadata={"id": 1},
        status="accepted",
    )


def test_scaffold_creates_only_class_index_folders(tmp_path: Path) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"

    scaffold_image_dataset(class_index_path=class_index, images_root=images_root)

    assert (images_root / "raw" / "000.rainbow_bee_eater").is_dir()
    assert (images_root / "splits" / "test" / "001.galah").is_dir()
    assert (
        validate_no_extra_class_folders(images_root=images_root, class_index_path=class_index)
        == []
    )

    extra = images_root / "raw" / "999.not_in_class_index"
    extra.mkdir()
    assert validate_no_extra_class_folders(
        images_root=images_root,
        class_index_path=class_index,
    ) == [extra]


def test_metadata_jsonl_roundtrip(tmp_path: Path) -> None:
    output = image_records_path(tmp_path / "images")
    write_metadata_jsonl([sample_record()], output)

    records = read_metadata_jsonl(output)

    assert len(records) == 1
    assert records[0].provider == "inaturalist"
    assert records[0].status == "accepted"
    assert records[0].raw_metadata == {"id": 1}
