from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from birdidex.download import (
    ImageRejected,
    collect_images,
    process_image_bytes,
)
from birdidex.images import image_records_path, read_metadata_jsonl
from birdidex.providers import ImageMetadataRecord
from birdidex.taxonomy import TaxonClass


def write_class_index(path: Path) -> Path:
    payload = {
        "version": 1,
        "classes": [
            {
                "class_id": 0,
                "label": "galah",
                "common_name": "Galah",
                "scientific_name": "Eolophus roseicapilla",
            },
            {
                "class_id": 1,
                "label": "unknown_sp",
                "common_name": "Unknown sp.",
                "scientific_name": "Aves sp.",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _png_bytes(seed: object, size: tuple[int, int] = (400, 300)) -> bytes:
    """Deterministic textured PNG.

    Flat-colour images all collapse to the same perceptual hash, so tests that exercise
    duplicate detection need real structure — hence pseudo-random pixels per seed.
    """
    import random

    from PIL import Image

    rnd = random.Random(seed)
    pixels = bytes(rnd.getrandbits(8) for _ in range(size[0] * size[1] * 3))
    buffer = io.BytesIO()
    Image.frombytes("RGB", size, pixels).save(buffer, format="PNG")
    return buffer.getvalue()


def _candidate(taxon: TaxonClass, provider: str, record_id: str, url: str) -> ImageMetadataRecord:
    return ImageMetadataRecord(
        class_id=taxon.class_id,
        label=taxon.label,
        common_name=taxon.common_name,
        scientific_name=taxon.scientific_name or "",
        provider=provider,
        provider_record_id=record_id,
        image_url=url,
        page_url="https://example.test/page",
        license_code="cc-by",
        rights_holder=None,
        attribution="Someone / CC BY",
        width=None,
        height=None,
        observed_on=None,
        latitude=None,
        longitude=None,
        raw_metadata={},
    )


def test_process_image_resizes_and_converts_to_jpeg() -> None:
    processed = process_image_bytes(
        _png_bytes("big", size=(2000, 1000)),
        max_edge=1024,
        image_format="jpg",
        quality=85,
    )
    assert processed.stored_format == "jpg"
    assert max(processed.stored_width, processed.stored_height) == 1024
    assert processed.original_width == 2000
    assert processed.data[:2] == b"\xff\xd8"  # JPEG SOI marker
    assert processed.sha256


def test_process_image_rejects_tiny_and_corrupt() -> None:
    with pytest.raises(ImageRejected) as small:
        process_image_bytes(_png_bytes("small", size=(64, 64)))
    assert small.value.reason == "image_too_small"

    with pytest.raises(ImageRejected) as corrupt:
        process_image_bytes(b"not-an-image")
    assert corrupt.value.reason == "corrupt_image"


def test_collect_images_downloads_validates_and_dedupes(tmp_path: Path) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"

    identical = _png_bytes("dup")
    distinct = _png_bytes("unique")
    payloads = {
        "https://example.test/a.jpg": identical,
        "https://example.test/b.jpg": identical,  # sha256 duplicate of a
        "https://example.test/c.jpg": distinct,
    }

    def fake_metadata(provider: str, taxon: TaxonClass, limit: int) -> list[ImageMetadataRecord]:
        if provider != "inaturalist":
            return []
        return [
            _candidate(taxon, provider, "1", "https://example.test/a.jpg"),
            _candidate(taxon, provider, "2", "https://example.test/b.jpg"),
            _candidate(taxon, provider, "3", "https://example.test/c.jpg"),
        ]

    def fake_downloader(url: str) -> bytes:
        return payloads[url]

    summary = collect_images(
        class_index_path=class_index,
        images_root=images_root,
        provider_names=("inaturalist",),
        per_class=10,
        target_accepted=10,
        metadata_fetcher=fake_metadata,
        downloader=fake_downloader,
    )

    # Ambiguous class (Aves sp.) is skipped entirely.
    assert summary.classes_processed == 1
    assert summary.accepted == 2
    assert summary.skipped_duplicate == 1

    records = read_metadata_jsonl(image_records_path(images_root))
    accepted = [r for r in records if r.status == "accepted"]
    assert len(accepted) == 2
    for record in accepted:
        assert record.local_path
        assert (images_root / "raw" / "000.galah").exists()
        assert record.stored_format == "jpg"
        assert record.phash

    dup = [r for r in records if "sha256_duplicate" in r.validation_issues]
    assert len(dup) == 1


def test_collect_images_dry_run_downloads_nothing(tmp_path: Path) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"

    def fake_metadata(provider: str, taxon: TaxonClass, limit: int) -> list[ImageMetadataRecord]:
        if provider != "inaturalist":
            return []
        return [_candidate(taxon, provider, "1", "https://example.test/a.jpg")]

    def exploding_downloader(url: str) -> bytes:  # pragma: no cover - must never run
        raise AssertionError("dry run must not download")

    summary = collect_images(
        class_index_path=class_index,
        images_root=images_root,
        provider_names=("inaturalist",),
        dry_run=True,
        metadata_fetcher=fake_metadata,
        downloader=exploding_downloader,
    )
    assert summary.dry_run
    records = read_metadata_jsonl(image_records_path(images_root))
    assert records and all(r.status == "candidate" for r in records)
    raw_dir = images_root / "raw" / "000.galah"
    assert not raw_dir.exists() or list(raw_dir.glob("*.jpg")) == []
