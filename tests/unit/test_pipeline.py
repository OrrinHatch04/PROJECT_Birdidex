from __future__ import annotations

import io
import json
import random
from pathlib import Path

import birdidex.pipeline as pipeline_module
import birdidex.profiles as profiles_module
from birdidex.pipeline import region_priors_path, run_pipeline
from birdidex.providers import ImageMetadataRecord, normalize_ebird_observations
from birdidex.taxonomy import TaxonClass


def _write_class_index(path: Path) -> Path:
    classes = [
        {
            "class_id": i,
            "label": f"clean_bird_{i}",
            "common_name": f"Clean Bird {i}",
            "scientific_name": f"Genus species{i}",
        }
        for i in range(6)
    ]
    classes.append(
        {
            "class_id": 99,
            "label": "gull_sp",
            "common_name": "Gull sp.",
            "scientific_name": "Larus sp.",
        }
    )
    path.write_text(json.dumps({"version": 1, "classes": classes}), encoding="utf-8")
    return path


def _png_bytes(seed: object, size: tuple[int, int] = (400, 300)) -> bytes:
    from PIL import Image

    rnd = random.Random(seed)
    pixels = bytes(rnd.getrandbits(8) for _ in range(size[0] * size[1] * 3))
    buffer = io.BytesIO()
    Image.frombytes("RGB", size, pixels).save(buffer, format="PNG")
    return buffer.getvalue()


def _inat_candidate(taxon: TaxonClass, n: int) -> ImageMetadataRecord:
    return ImageMetadataRecord(
        class_id=taxon.class_id,
        label=taxon.label,
        common_name=taxon.common_name,
        scientific_name=taxon.scientific_name or "",
        provider="inaturalist",
        provider_record_id=f"{taxon.class_id}:{n}",
        image_url=f"https://example.test/{taxon.class_id}_{n}.jpg",
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


def _patch_profiles(monkeypatch, tmp_path: Path) -> Path:
    profiles = tmp_path / "profiles"
    monkeypatch.setattr(profiles_module, "profiles_dir", lambda: profiles)
    monkeypatch.setattr(pipeline_module, "profiles_dir", lambda: profiles)
    return profiles


def test_pipeline_five_species_with_mocked_providers(tmp_path: Path, monkeypatch) -> None:
    class_index = _write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"
    _patch_profiles(monkeypatch, tmp_path)

    ebird_calls: list[str] = []

    def fake_ebird(taxon: TaxonClass, region: str):
        ebird_calls.append(taxon.folder_name)
        return normalize_ebird_observations(
            [{"locName": "Park A", "obsDt": "2026-03-01", "howMany": 3}],
            taxon,
            region=region,
            species_code=f"code{taxon.class_id}",
        )

    def fake_metadata(provider: str, taxon: TaxonClass, limit: int) -> list[ImageMetadataRecord]:
        if provider != "inaturalist":
            return []
        return [_inat_candidate(taxon, n) for n in range(3)]

    def fake_downloader(url: str) -> bytes:
        return _png_bytes(url)

    summary = run_pipeline(
        class_index_path=class_index,
        images_root=images_root,
        species_limit=3,
        per_class=3,
        target_accepted=3,
        region="seq",
        master=4242,
        ebird_fetcher=fake_ebird,
        metadata_fetcher=fake_metadata,
        downloader=fake_downloader,
    )

    assert len(summary.species_selected) == 3
    assert all("gull_sp" not in name for name in summary.species_selected)  # ambiguous excluded
    assert summary.ebird_priors_written == 3
    assert summary.accepted_images == 9  # 3 species x 3 accepted
    assert summary.profiles_built == 7  # profiles built for every class
    assert summary.errors == []
    assert summary.master_seed_used is True

    # eBird priors file written and normalized
    priors_lines = region_priors_path().read_text(encoding="utf-8").strip().splitlines()
    assert len(priors_lines) == 3
    first = json.loads(priors_lines[0])
    assert first["provider"] == "ebird"
    assert first["region_resolved"] == "AU-QLD"

    # Deterministic: same seed -> same species set
    again = run_pipeline(
        class_index_path=class_index,
        images_root=images_root,
        species_limit=3,
        per_class=3,
        target_accepted=3,
        master=4242,
        ebird_fetcher=fake_ebird,
        metadata_fetcher=fake_metadata,
        downloader=fake_downloader,
    )
    assert again.species_selected == summary.species_selected


def test_pipeline_stops_gracefully_on_ebird_error(tmp_path: Path, monkeypatch) -> None:
    class_index = _write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"
    _patch_profiles(monkeypatch, tmp_path)

    def exploding_ebird(taxon: TaxonClass, region: str):
        raise RuntimeError("ebird 429")

    def fake_metadata(provider: str, taxon: TaxonClass, limit: int) -> list[ImageMetadataRecord]:
        return [_inat_candidate(taxon, 0)] if provider == "inaturalist" else []

    summary = run_pipeline(
        class_index_path=class_index,
        images_root=images_root,
        species_limit=2,
        per_class=1,
        target_accepted=1,
        master=4242,
        ebird_fetcher=exploding_ebird,
        metadata_fetcher=fake_metadata,
        downloader=lambda url: _png_bytes(url),
    )

    # eBird failures are captured, not fatal; iNat images still collected.
    assert summary.ebird_priors_written == 0
    assert len(summary.errors) == 2
    assert all("ebird:" in err for err in summary.errors)
    assert summary.accepted_images == 2


def test_pipeline_dry_run_downloads_nothing(tmp_path: Path, monkeypatch) -> None:
    class_index = _write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"
    _patch_profiles(monkeypatch, tmp_path)

    def fake_metadata(provider: str, taxon: TaxonClass, limit: int) -> list[ImageMetadataRecord]:
        return [_inat_candidate(taxon, 0)] if provider == "inaturalist" else []

    def exploding_downloader(url: str) -> bytes:  # pragma: no cover - must not run
        raise AssertionError("dry run must not download")

    summary = run_pipeline(
        class_index_path=class_index,
        images_root=images_root,
        species_limit=2,
        per_class=1,
        target_accepted=1,
        master=4242,
        dry_run=True,
        fetch_ebird=False,
        metadata_fetcher=fake_metadata,
        downloader=exploding_downloader,
    )
    assert summary.dry_run
    assert summary.accepted_images == 2  # candidates counted, not downloaded
    raw_dirs = list((images_root / "raw").glob("*/*.jpg")) if (images_root / "raw").exists() else []
    assert raw_dirs == []
