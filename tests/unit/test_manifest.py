"""Manifest schema, CSV round-trip, licence filtering, class balance, duplicates."""

from __future__ import annotations

import json
from pathlib import Path

from bird_data.csvio import MANIFEST_CSV_FIELDS, load_manifest_csv, save_manifest_csv
from bird_data.licensing import filter_open_licensed, is_open_license, normalise_license
from bird_data.manifest_build import class_counts, find_duplicates, parse_inat_observations

SAMPLE = Path(__file__).resolve().parents[1].parent / "data/seeds/inat_observations.sample.json"


def _records() -> list:
    return parse_inat_observations(json.loads(SAMPLE.read_text()))


def test_normalise_and_open_license() -> None:
    assert normalise_license("CC_BY") == "cc-by"
    assert is_open_license("cc0")
    assert is_open_license("cc-by-nc")
    assert not is_open_license("cc-by-nd")  # no-derivatives excluded
    assert not is_open_license(None)


def test_parse_inat_one_record_per_photo() -> None:
    records = _records()
    assert len(records) == 18  # sum of photos across observations
    r = records[0]
    assert r.source.value == "inaturalist"
    assert r.scientific_name == "Dacelo novaeguineae"
    assert r.extra["observation_id"] == "100001"


def test_license_filter_keeps_only_open() -> None:
    kept, rejected = filter_open_licensed(_records())
    assert all(is_open_license(r.license) for r in kept)
    assert len(rejected) == 2  # cc-by-nd + null licence in the fixture


def test_csv_round_trip_preserves_fields(tmp_path: Path) -> None:
    records = _records()
    path = tmp_path / "m.csv"
    save_manifest_csv(records, path)
    with path.open(newline="") as fh:
        import csv as _csv

        assert _csv.DictReader(fh).fieldnames == MANIFEST_CSV_FIELDS
    loaded = load_manifest_csv(path)
    assert len(loaded) == len(records)
    assert loaded[0].image_id == records[0].image_id
    assert loaded[0].scientific_name == records[0].scientific_name
    assert loaded[0].extra == records[0].extra


def test_class_counts_and_duplicates() -> None:
    records = _records()
    counts = class_counts(records)
    assert counts["Dacelo novaeguineae"] >= 1
    assert sum(counts.values()) == len(records)
    # fixture has no exact-duplicate image ids or urls
    assert find_duplicates(records) == {}


def test_duplicate_detection_flags_repeated_url() -> None:
    records = _records()
    dup = records[0].model_copy(update={"photo_url": records[1].photo_url})
    dups = find_duplicates([records[0], records[1], dup])
    assert any(k.startswith("photo_url:") for k in dups)
