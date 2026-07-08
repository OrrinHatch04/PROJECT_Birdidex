"""Split generation: determinism, no group leakage, and validation checks."""

from __future__ import annotations

import json
from pathlib import Path

from bird_core.schemas import DatasetSplit
from bird_data.manifest_build import parse_inat_observations
from bird_data.splits import (
    ValidationIssue,
    assign_splits,
    choose_group_field,
    split_records,
    validate_dataset,
)

SAMPLE = Path(__file__).resolve().parents[1].parent / "data/seeds/inat_observations.sample.json"


def _records() -> list:
    return parse_inat_observations(json.loads(SAMPLE.read_text()))


def test_group_field_prefers_observation_id() -> None:
    assert choose_group_field(_records()) == "observation_id"


def test_assignment_is_deterministic() -> None:
    a, _ = assign_splits(_records(), seed=42)
    b, _ = assign_splits(_records(), seed=42)
    assert [r.split for r in a] == [r.split for r in b]


def test_no_group_leakage_across_splits() -> None:
    assigned, field = assign_splits(_records(), seed=42)
    group_to_split: dict[str, set] = {}
    for r in assigned:
        gv = r.extra.get(field) or str(r.image_id)
        group_to_split.setdefault(gv, set()).add(r.split.value)
    assert all(len(v) == 1 for v in group_to_split.values())
    # validation confirms no leakage error
    issues = validate_dataset(assigned, group_field=field)
    assert not [i for i in issues if i.code == "leakage"]


def test_all_splits_populated_for_multi_group_classes() -> None:
    assigned, _ = assign_splits(_records(), seed=42)
    buckets = split_records(assigned)
    assert len(buckets[DatasetSplit.train]) > 0
    assert len(buckets[DatasetSplit.val]) > 0
    assert len(buckets[DatasetSplit.test]) > 0


def test_validation_flags_missing_license() -> None:
    records = _records()
    # Force a closed licence and check the error surfaces
    records[0].license = "cc-by-nd"
    assigned, field = assign_splits(records, seed=1)
    issues = validate_dataset(assigned, group_field=field)
    assert any(i.code == "missing_license" and i.level == "error" for i in issues)


def test_validation_flags_invalid_label() -> None:
    records = _records()
    records[0].scientific_name = "   "
    assigned, field = assign_splits(records, seed=1)
    issues = validate_dataset(assigned, group_field=field)
    assert any(i.code == "invalid_label" for i in issues)


def test_validation_issue_dataclass() -> None:
    issue = ValidationIssue("warning", "x", "msg")
    assert issue.level == "warning"
