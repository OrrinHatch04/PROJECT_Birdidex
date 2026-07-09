from __future__ import annotations

import json
from pathlib import Path

import birdidex.audit as audit_module
import birdidex.profiles as profiles_module
from birdidex.audit import build_audit
from birdidex.images import image_records_path, write_metadata_jsonl
from birdidex.observations import (
    ObservationRecord,
    observation_json_schema,
)
from birdidex.profiles import build_profiles, load_species_profiles, lookup_profile
from birdidex.providers import ImageMetadataRecord


def write_class_index(path: Path) -> Path:
    payload = {
        "version": 1,
        "classes": [
            {
                "class_id": 0,
                "label": "galah",
                "common_name": "Galah",
                "scientific_name": "Eolophus roseicapilla",
                "known_regions": ["North Harbour Heritage Park"],
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


def _accepted_record(local_path: str) -> ImageMetadataRecord:
    return ImageMetadataRecord(
        class_id=0,
        label="galah",
        common_name="Galah",
        scientific_name="Eolophus roseicapilla",
        provider="inaturalist",
        provider_record_id="1:2",
        image_url="https://example.test/a.jpg",
        page_url=None,
        license_code="cc-by",
        rights_holder=None,
        attribution="Photographer / CC BY",
        width=1200,
        height=800,
        observed_on=None,
        latitude=None,
        longitude=None,
        raw_metadata={},
        local_path=local_path,
        sha256="abc",
        stored_width=1024,
        stored_height=683,
        stored_format="jpg",
        status="accepted",
    )


def test_profiles_leave_unknown_fields_empty(tmp_path: Path, monkeypatch) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"
    write_metadata_jsonl([_accepted_record("data/x.jpg")], image_records_path(images_root))

    monkeypatch.setattr(profiles_module, "profiles_dir", lambda: tmp_path / "profiles")

    profiles = build_profiles(class_index_path=class_index, images_root=images_root)

    assert len(profiles) == 2
    galah = next(p for p in profiles if p.class_id == 0)
    assert galah.representative_image_path == "data/x.jpg"
    assert galah.representative_image_attribution == "Photographer / CC BY"
    assert galah.habitat is None
    assert galah.diet is None
    assert galah.known_regions == ["North Harbour Heritage Park"]
    assert "class_index.json" in galah.data_sources

    combined = json.loads((tmp_path / "profiles" / "species_profiles.json").read_text())
    assert combined["n_profiles"] == 2
    assert (tmp_path / "profiles" / "000.galah.json").exists()

    loaded = load_species_profiles(tmp_path / "profiles" / "species_profiles.json")
    by_id = lookup_profile(loaded, class_id=0)
    by_label = lookup_profile(loaded, label="galah")
    assert by_id is not None
    assert by_id["common_name"] == "Galah"
    assert by_label is not None
    assert by_label["class_id"] == 0


def test_profiles_merge_curated_notes(tmp_path: Path, monkeypatch) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"
    write_metadata_jsonl([], image_records_path(images_root))

    profiles_root = tmp_path / "profiles"
    notes_dir = profiles_root / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "000.galah.json").write_text(
        json.dumps({"habitat": "open woodland", "diet": "seeds"}), encoding="utf-8"
    )
    monkeypatch.setattr(profiles_module, "profiles_dir", lambda: profiles_root)

    profiles = build_profiles(class_index_path=class_index, images_root=images_root)
    galah = next(p for p in profiles if p.class_id == 0)
    assert galah.habitat == "open woodland"
    assert galah.diet == "seeds"
    assert "curated_notes" in galah.data_sources


def test_observation_schema_and_roundtrip() -> None:
    schema = observation_json_schema()
    assert schema["required"] == ["observation_id", "captured_at_utc"]
    assert schema["properties"]["latitude"]["type"] == ["number", "null"]
    assert schema["additionalProperties"] is False

    record = ObservationRecord(
        observation_id="obs-1",
        captured_at_utc="2026-07-08T00:00:00+00:00",
        predicted_class_id=3,
        confidence=0.91,
        crop_path="data/images/crops/obs-1.jpg",
        top_k_predictions=[{"class_id": 3, "confidence": 0.91}],
    )
    data = record.to_dict()
    assert data["crop_path"] == "data/images/crops/obs-1.jpg"
    assert data["top_k_predictions"][0]["class_id"] == 3
    restored = ObservationRecord.from_dict({**data, "unexpected": "ignored"})
    assert restored.observation_id == "obs-1"
    assert restored.confidence == 0.91


def test_dataset_audit_flags_weak_and_missing(tmp_path: Path, monkeypatch) -> None:
    class_index = write_class_index(tmp_path / "class_index.json")
    images_root = tmp_path / "images"
    write_metadata_jsonl([_accepted_record("data/x.jpg")], image_records_path(images_root))
    monkeypatch.setattr(audit_module, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(audit_module, "species_profiles_path", lambda: tmp_path / "missing.json")

    audit = build_audit(class_index_path=class_index, images_root=images_root)

    assert audit["n_classes"] == 2
    assert audit["n_accepted"] == 1
    # Galah has one accepted image (< threshold) so it is weak coverage.
    assert "000.galah" in audit["weak_coverage_classes"]
    # Ambiguous class is reported as excluded.
    assert "001.unknown_sp" in audit["ambiguous_excluded_classes"]
    galah = next(row for row in audit["per_class"] if row["class_id"] == 0)
    assert galah["has_representative_image"] is True
