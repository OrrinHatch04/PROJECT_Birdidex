from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from birdidex.download import (
    ImageRejected,
    collect_images,
    process_image_bytes,
)
from birdidex.images import image_records_path, read_metadata_jsonl
from birdidex.providers import ImageMetadataRecord
from birdidex.taxonomy import TaxonClass


class MockResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.payload


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


def _dim_candidate(
    taxon: TaxonClass, record_id: str, url: str, width: int, height: int
) -> ImageMetadataRecord:
    return replace(
        _candidate(taxon, "inaturalist", record_id, url), width=width, height=height
    )


def test_skip_existing_does_not_redownload(tmp_path: Path) -> None:
    from birdidex.images import write_metadata_jsonl

    class_index = write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"
    galah = TaxonClass(0, "galah", "Galah", "Eolophus roseicapilla")

    # An image already downloaded in a previous run.
    prior = replace(
        _candidate(galah, "inaturalist", "1", "https://example.test/old.jpg"),
        sha256="deadbeef",
        phash="0" * 16,
        local_path="raw/000.galah/inaturalist_1.jpg",
        status="accepted",
    )
    write_metadata_jsonl([prior], image_records_path(images_root))

    downloaded: list[str] = []

    def fake_metadata(provider: str, taxon: TaxonClass, limit: int) -> list[ImageMetadataRecord]:
        if provider != "inaturalist":
            return []
        return [
            _candidate(taxon, provider, "1", "https://example.test/old.jpg"),  # already have it
            _candidate(taxon, provider, "2", "https://example.test/new.jpg"),  # fresh
        ]

    def fake_downloader(url: str) -> bytes:
        downloaded.append(url)
        return _png_bytes(url)

    summary = collect_images(
        class_index_path=class_index,
        images_root=images_root,
        provider_names=("inaturalist",),
        skip_existing=True,
        metadata_fetcher=fake_metadata,
        downloader=fake_downloader,
    )

    # Only the fresh photo was downloaded; the existing one was left untouched.
    assert downloaded == ["https://example.test/new.jpg"]
    assert summary.accepted == 1
    records = read_metadata_jsonl(image_records_path(images_root))
    ids = {(r.provider, r.provider_record_id) for r in records if r.status == "accepted"}
    assert ("inaturalist", "1") in ids  # preserved
    assert ("inaturalist", "2") in ids  # added


def test_min_source_edge_rejects_low_resolution(tmp_path: Path) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"

    def fake_metadata(provider: str, taxon: TaxonClass, limit: int) -> list[ImageMetadataRecord]:
        if provider != "inaturalist":
            return []
        return [
            _dim_candidate(taxon, "small", "https://example.test/small.jpg", 300, 240),
            _dim_candidate(taxon, "big", "https://example.test/big.jpg", 2000, 1500),
        ]

    downloaded: list[str] = []

    def fake_downloader(url: str) -> bytes:
        downloaded.append(url)
        return _png_bytes(url, size=(2000, 1500))

    summary = collect_images(
        class_index_path=class_index,
        images_root=images_root,
        provider_names=("inaturalist",),
        min_source_edge=800,
        metadata_fetcher=fake_metadata,
        downloader=fake_downloader,
    )

    assert downloaded == ["https://example.test/big.jpg"]  # low-res never fetched
    assert summary.accepted == 1
    records = read_metadata_jsonl(image_records_path(images_root))
    assert any("below_min_source_edge" in r.validation_issues for r in records)


def test_fetch_inaturalist_ranked_orders_filters_and_excludes() -> None:
    from birdidex.providers import fetch_inaturalist_ranked

    taxon = TaxonClass(0, "superb_fairywren", "Superb Fairywren", "Malurus cyaneus")

    def obs(oid: int, pid: int, faves: int, w: int, h: int) -> dict:
        return {
            "id": oid,
            "faves_count": faves,
            "taxon": {"name": "Malurus cyaneus", "preferred_common_name": "Superb Fairywren"},
            "photos": [
                {
                    "id": pid,
                    "url": f"https://static.inaturalist.org/{pid}/square.jpg",
                    "license_code": "CC-BY",
                    "original_dimensions": {"width": w, "height": h},
                }
            ],
        }

    payload = {
        "results": [
            obs(10, 100, 1, 2000, 1500),  # ok, few faves
            obs(20, 200, 5, 1800, 1200),  # ok, most faves -> first
            obs(30, 300, 9, 300, 300),  # tiny -> filtered out despite faves
        ]
    }

    class OneShotClient:
        def __init__(self, first: dict) -> None:
            self.calls = 0
            self.first = first

        def get(self, url: str, **kwargs: object) -> MockResponse:
            self.calls += 1
            return MockResponse(self.first if self.calls == 1 else {"results": []})

    ranked = fetch_inaturalist_ranked(
        taxon, client=OneShotClient(payload), live=True, limit=5, min_edge=800
    )
    assert [r.provider_record_id for r in ranked] == ["20:200", "10:100"]

    excluded = fetch_inaturalist_ranked(
        taxon,
        client=OneShotClient(payload),
        live=True,
        limit=5,
        min_edge=800,
        exclude_ids=frozenset({("inaturalist", "20:200")}),
    )
    assert [r.provider_record_id for r in excluded] == ["10:100"]


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
